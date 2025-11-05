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
- 管理任务存储（支持内存和 Redis 两种模式）
- 提供并发控制（Semaphore）
- 提供任务 CRUD 操作
- **存储模式**：
  - `memory`: 内存存储（默认，重启后数据丢失）
  - `redis`: Redis 持久化存储（生产推荐，支持容器重启和实例重建）
- **TTL 策略**：自动清理过期任务（completed=24h, failed=24h, pending/processing=6h）
- **降级机制**：Redis 不可用时自动降级到内存存储

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

1. **任务存储**:
   - 支持两种模式：`memory`（默认）和 `redis`（生产推荐）
   - 通过环境变量 `TASK_STORE_STORAGE` 配置
   - Redis 模式自动设置 TTL 清理过期任务
   - **多租户场景**：实例池 LRU=50，超过会驱逐，`memory` 模式任务会丢失，建议使用 `redis` 模式
2. **文件大小限制**: 默认 100MB，可在 `insert.py` 中修改。
3. **超时处理**: 客户端应实现超时和重试逻辑。
4. **并发数**: 默认根据 MinerU 模式动态配置（local=1, remote=10），可通过 `DOCUMENT_PROCESSING_CONCURRENCY` 调整。

