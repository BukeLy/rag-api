# API 模块说明

## 目录结构

```
api/
├── __init__.py       # API 路由初始化和注册
├── models.py         # 数据模型定义（TaskStatus, TaskInfo, QueryRequest）
├── task_store.py     # 任务存储和并发控制
├── insert.py         # 文档插入路由（/insert）
├── query.py          # 查询路由（/query）
└── task.py           # 任务状态查询路由（/task/{task_id}）
```

## 模块职责

### `models.py`
- 定义 API 使用的数据模型
- `TaskStatus`: 任务状态枚举（pending, processing, completed, failed）
- `TaskInfo`: 任务信息模型
- `QueryRequest`: 查询请求模型

### `task_store.py`
- 管理任务存储（内存字典）
- 提供并发控制（Semaphore）
- 提供任务 CRUD 操作

### `insert.py`
- 处理文档上传（`POST /insert`）
- 异步任务调度
- 文件验证（空文件、大小限制）
- 后台文档处理

### `query.py`
- 处理 RAG 查询（`POST /query`）
- 支持多种查询模式（local, global, hybrid, mix）

### `task.py`
- 查询任务状态（`GET /task/{task_id}`）
- 返回任务详细信息（状态、结果、错误）

## API 端点

### 1. 上传文档
```http
POST /insert?doc_id={doc_id}
Content-Type: multipart/form-data

file: <文件>
```

**响应** (202 Accepted):
```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "pending",
  "message": "Document upload accepted. Processing in background.",
  "doc_id": "doc_001",
  "filename": "test.pdf"
}
```

### 2. 查询任务状态
```http
GET /task/{task_id}
```

**响应** (200 OK):
```json
{
  "task_id": "xxx-xxx-xxx",
  "status": "completed",
  "doc_id": "doc_001",
  "filename": "test.pdf",
  "created_at": "2025-10-14T20:00:00",
  "updated_at": "2025-10-14T20:02:30",
  "result": {
    "message": "Document processed successfully",
    "doc_id": "doc_001",
    "filename": "test.pdf"
  }
}
```

### 3. 查询 RAG
```http
POST /query
Content-Type: application/json

{
  "query": "什么是人工智能？",
  "mode": "mix"
}
```

**响应** (200 OK):
```json
{
  "answer": "人工智能是..."
}
```

## 异步处理流程

```
客户端上传文件
    ↓
接收文件并验证（同步）
    ↓
创建任务记录 → 返回 task_id (202)
    ↓
后台任务队列
    ↓
等待信号量（并发控制）
    ↓
MinerU 处理文档
    ↓
更新任务状态 (completed/failed)
    ↓
客户端轮询任务状态
```

## 并发控制

使用 `asyncio.Semaphore(1)` 限制同时处理的文档数量：
- **目的**: 防止多个 MinerU 进程同时运行导致 OOM
- **策略**: 同一时间只允许 1 个文档处理任务
- **效果**: 其他任务排队等待，但不会阻塞 HTTP 连接

## 注意事项

1. **任务存储**: 当前使用内存字典，重启后数据丢失。生产环境建议使用 Redis。
2. **文件大小限制**: 默认 100MB，可在 `insert.py` 中修改。
3. **超时处理**: 客户端应实现超时和重试逻辑。
4. **并发数**: 当前限制为 1，可根据服务器内存调整。

