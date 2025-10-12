# 异步任务处理方案（202 模式）

## 问题描述

当前实现是同步处理，用户上传文件后需要等待整个处理完成（可能几分钟）才会收到响应。

**问题：**
- HTTP 连接可能超时
- 用户体验差
- 无法处理真正的大文件

---

## 解决方案：异步任务队列

### 架构设计

```
用户上传文件
    ↓
立即返回 202 Accepted + task_id
    ↓
后台异步处理
    ↓
用户轮询任务状态
```

### 实现步骤

#### 1. 添加任务状态管理

```python
# main.py - 添加到文件开头

import asyncio
from typing import Dict, Any
from datetime import datetime
import uuid

# 简单的内存任务存储（生产环境应使用 Redis/数据库）
tasks: Dict[str, Dict[str, Any]] = {}

class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
```

#### 2. 修改上传端点返回 202

```python
@app.post("/insert")
async def insert_document(doc_id: str, file: UploadFile = File(...)):
    """
    异步上传文件并处理。立即返回任务 ID。
    """
    rag_instance = get_rag_instance()
    if not rag_instance:
        raise HTTPException(status_code=503, detail="RAG service is not ready.")
    
    # 保留原始文件名（仅用于日志）
    original_filename = file.filename
    
    # 安全地提取文件扩展名
    if original_filename:
        basename = os.path.basename(original_filename)
        file_extension = Path(basename).suffix.lower()
        if file_extension and not file_extension[1:].replace('_', '').replace('-', '').isalnum():
            file_extension = ""
    else:
        file_extension = ""
    
    # 使用 UUID 生成安全的临时文件名
    safe_filename = f"{uuid.uuid4()}{file_extension}"
    temp_file_path = f"/tmp/{safe_filename}"
    
    try:
        # 保存上传的文件到临时位置
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 验证文件大小
        file_size = os.path.getsize(temp_file_path)
        if file_size == 0:
            raise ValueError(f"Empty file: {original_filename}")
        
        max_file_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_file_size:
            raise ValueError(f"File too large: {original_filename}")
        
        # 生成任务 ID
        task_id = str(uuid.uuid4())
        
        # 初始化任务状态
        tasks[task_id] = {
            "task_id": task_id,
            "doc_id": doc_id,
            "filename": original_filename,
            "file_size": file_size,
            "status": TaskStatus.PENDING,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "result": None,
            "error": None
        }
        
        # 启动后台任务
        asyncio.create_task(
            process_document_background(task_id, temp_file_path, original_filename, rag_instance)
        )
        
        logger.info(f"Created task {task_id} for file: {original_filename}")
        
        # 立即返回 202 Accepted
        return JSONResponse(
            status_code=202,
            content={
                "message": "File uploaded successfully, processing started",
                "task_id": task_id,
                "doc_id": doc_id,
                "filename": original_filename,
                "status_url": f"/task/{task_id}"
            }
        )

    except ValueError as e:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=400, detail=f"Invalid document: {str(e)}")
    
    except Exception as e:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise HTTPException(status_code=500, detail=str(e))
```

#### 3. 后台处理函数

```python
async def process_document_background(task_id: str, temp_file_path: str, original_filename: str, rag_instance):
    """后台异步处理文档"""
    try:
        # 更新状态为处理中
        tasks[task_id]["status"] = TaskStatus.PROCESSING
        tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        logger.info(f"Task {task_id}: Starting processing...")
        
        # 处理文档
        await rag_instance.process_document_complete(
            file_path=temp_file_path,
            output_dir="./output"
        )
        
        # 更新状态为完成
        tasks[task_id]["status"] = TaskStatus.COMPLETED
        tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        tasks[task_id]["result"] = {
            "message": "Document processed successfully",
            "filename": original_filename
        }
        
        logger.info(f"Task {task_id}: Completed successfully")
        
    except Exception as e:
        # 更新状态为失败
        tasks[task_id]["status"] = TaskStatus.FAILED
        tasks[task_id]["updated_at"] = datetime.utcnow().isoformat()
        tasks[task_id]["error"] = str(e)
        
        logger.error(f"Task {task_id}: Failed - {e}", exc_info=True)
    
    finally:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Task {task_id}: Cleaned up temp file")
            except OSError as e:
                logger.warning(f"Task {task_id}: Failed to clean up - {e}")
```

#### 4. 任务状态查询端点

```python
@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return tasks[task_id]
```

#### 5. 可选：取消任务端点

```python
@app.delete("/task/{task_id}")
async def cancel_task(task_id: str):
    """取消任务（仅限 pending 状态）"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task = tasks[task_id]
    
    if task["status"] != TaskStatus.PENDING:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel task in {task['status']} status"
        )
    
    task["status"] = TaskStatus.FAILED
    task["error"] = "Task cancelled by user"
    task["updated_at"] = datetime.utcnow().isoformat()
    
    return {"message": "Task cancelled", "task_id": task_id}
```

---

## 客户端使用示例

### Python 客户端

```python
import requests
import time

# 1. 上传文件（立即返回）
with open("large_document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/insert",
        params={"doc_id": "doc_001"},
        files={"file": f}
    )

if response.status_code == 202:
    task_info = response.json()
    task_id = task_info["task_id"]
    status_url = f"http://localhost:8000{task_info['status_url']}"
    
    print(f"✓ File uploaded, Task ID: {task_id}")
    print(f"  Processing started...")
    
    # 2. 轮询任务状态
    while True:
        status_response = requests.get(status_url)
        task_status = status_response.json()
        
        print(f"  Status: {task_status['status']}")
        
        if task_status["status"] == "completed":
            print(f"✓ Processing completed!")
            print(f"  Result: {task_status['result']}")
            break
        elif task_status["status"] == "failed":
            print(f"✗ Processing failed!")
            print(f"  Error: {task_status['error']}")
            break
        
        # 等待 2 秒后再次查询
        time.sleep(2)
else:
    print(f"✗ Upload failed: {response.json()}")
```

### Curl 示例

```bash
# 1. 上传文件
RESPONSE=$(curl -X POST "http://localhost:8000/insert?doc_id=doc_001" \
  -F "file=@large_document.pdf")

TASK_ID=$(echo $RESPONSE | jq -r '.task_id')
echo "Task ID: $TASK_ID"

# 2. 查询状态
while true; do
  STATUS=$(curl -s "http://localhost:8000/task/$TASK_ID" | jq -r '.status')
  echo "Status: $STATUS"
  
  if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
    break
  fi
  
  sleep 2
done

# 3. 获取最终结果
curl "http://localhost:8000/task/$TASK_ID" | jq
```

---

## 响应示例

### 上传成功（202 Accepted）

```json
{
  "message": "File uploaded successfully, processing started",
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "doc_id": "doc_001",
  "filename": "large_document.pdf",
  "status_url": "/task/a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 任务状态 - 处理中

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "doc_id": "doc_001",
  "filename": "large_document.pdf",
  "file_size": 52428800,
  "status": "processing",
  "created_at": "2025-10-13T03:00:00.000Z",
  "updated_at": "2025-10-13T03:00:05.000Z",
  "result": null,
  "error": null
}
```

### 任务状态 - 完成

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "doc_id": "doc_001",
  "filename": "large_document.pdf",
  "file_size": 52428800,
  "status": "completed",
  "created_at": "2025-10-13T03:00:00.000Z",
  "updated_at": "2025-10-13T03:02:30.000Z",
  "result": {
    "message": "Document processed successfully",
    "filename": "large_document.pdf"
  },
  "error": null
}
```

### 任务状态 - 失败

```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "doc_id": "doc_001",
  "filename": "large_document.pdf",
  "file_size": 52428800,
  "status": "failed",
  "created_at": "2025-10-13T03:00:00.000Z",
  "updated_at": "2025-10-13T03:01:15.000Z",
  "result": null,
  "error": "Unsupported file format: large_document.pdf"
}
```

---

## 生产环境优化

### 1. 使用持久化存储

当前示例使用内存存储任务状态，重启后丢失。生产环境应使用：

- **Redis**: 快速、支持过期
- **数据库**: PostgreSQL、MongoDB
- **任务队列**: Celery、RQ、Dramatiq

### 2. 任务清理策略

```python
import asyncio
from datetime import datetime, timedelta

async def cleanup_old_tasks():
    """定期清理旧任务（后台任务）"""
    while True:
        try:
            now = datetime.utcnow()
            expired_tasks = []
            
            for task_id, task in tasks.items():
                # 保留 24 小时
                created = datetime.fromisoformat(task["created_at"])
                if now - created > timedelta(hours=24):
                    expired_tasks.append(task_id)
            
            for task_id in expired_tasks:
                del tasks[task_id]
                logger.info(f"Cleaned up expired task: {task_id}")
            
        except Exception as e:
            logger.error(f"Task cleanup error: {e}")
        
        # 每小时运行一次
        await asyncio.sleep(3600)

# 在 lifespan 中启动
@asynccontextmanager
async def lifespan(app):
    # ... RAG 初始化 ...
    
    # 启动清理任务
    cleanup_task = asyncio.create_task(cleanup_old_tasks())
    
    yield
    
    # 关闭清理任务
    cleanup_task.cancel()
```

### 3. 限制并发任务数

```python
# 使用信号量限制并发
MAX_CONCURRENT_TASKS = 4
task_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

async def process_document_background(task_id: str, ...):
    async with task_semaphore:  # 限制并发
        # ... 处理逻辑 ...
```

---

## 优缺点对比

### 同步处理（当前）

**优点：**
- ✅ 实现简单
- ✅ 用户立即知道结果
- ✅ 无需额外端点

**缺点：**
- ❌ 长连接占用资源
- ❌ 可能超时
- ❌ 无法处理真正的大文件

### 异步处理（202）

**优点：**
- ✅ 快速响应（< 1 秒）
- ✅ 支持大文件
- ✅ 更好的资源利用
- ✅ 可以取消任务

**缺点：**
- ❌ 实现复杂
- ❌ 需要轮询
- ❌ 需要状态管理

---

## 建议

### 当前场景（< 100MB，< 30s 处理）
**保持同步处理即可** - 你当前的实现足够了

### 需要支持大文件或长时间处理
**使用异步任务** - 实现 202 模式

### 折中方案
添加配置开关，根据文件大小决定：
```python
# 小文件（< 10MB）同步处理
# 大文件（> 10MB）异步处理
if file_size < 10 * 1024 * 1024:
    # 同步处理
    await process_document(...)
    return {"status": "completed"}
else:
    # 异步处理
    task_id = create_background_task(...)
    return JSONResponse(status_code=202, content={"task_id": task_id})
```

---

© 2025 RAG API Project

