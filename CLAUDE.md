# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Preference

**Default Response Language**: Chinese (Simplified)
- All responses, explanations, and documentation should be in Chinese
- Thinking process can remain in English
- Code comments and variable names should follow standard English conventions
- Git commits should be in Chinese

## Project Overview

This is a **multi-tenant** multimodal RAG (Retrieval-Augmented Generation) API service built with FastAPI, combining RAG-Anything and LightRAG for document processing and intelligent querying.

**Key Architecture**: Multi-Tenant LightRAG + Multiple Parsers
- **Multi-tenant isolation**: Each tenant has isolated LightRAG instance (via workspace)
- **Instance pool management**: LRU cache (max 50 instances by default)
- **Shared resources**: LLM/Embedding functions shared across tenants
- **MinerU parser**: Powerful multimodal parsing (OCR, tables, equations) with high memory usage
- **Docling parser**: Lightweight fast parsing for simple documents
- **Direct LightRAG query**: Bypasses parsers for optimal query performance

## Branch Strategy

- **`main` branch** (唯一主分支)
  - 所有代码都在此分支开发和部署
  - 生产环境和开发环境通过不同的 docker-compose 文件区分
  - 新功能开发通过 Pull Request 流程合并

## Deployment Commands

### 一键部署脚本（推荐）
```bash
./deploy.sh
# 会提示选择：1) 生产模式 2) 开发模式
```

### 生产模式
```bash
docker compose -f docker-compose.yml up -d
docker compose -f docker-compose.yml logs -f
docker compose -f docker-compose.yml down
```

### 开发模式（代码热重载）
```bash
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml logs -f
docker compose -f docker-compose.dev.yml down
```

## LightRAG WebUI（知识图谱可视化）

项目集成了 LightRAG 官方 WebUI，与 rag-api 形成**互补关系**，完全兼容多租户架构。

**访问方式**：
- 本地：http://localhost:9621/webui/
- 测试服务器：http://45.78.223.205:9621/webui/

**多租户切换**：
- 修改 `.env` 中的 `LIGHTRAG_WEBUI_WORKSPACE=tenant_id`
- 重启 WebUI：`docker compose restart lightrag-webui`

详细文档：[docs/LIGHTRAG_WEBUI_INTEGRATION.md](docs/LIGHTRAG_WEBUI_INTEGRATION.md)

## Remote Deployment

**Testing Server**: 45.78.223.205
**SSH Access**: `ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205`

**部署流程**（通过 PR）：
```bash
# 1. 本地开发
git checkout -b feature/xxx
git commit -m "feat: xxx"
git push origin feature/xxx

# 2. GitHub 创建 PR 并合并到 main

# 3. 服务器更新
ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205
cd ~/rag-api
git pull origin main
# 代码变更立即生效（开发模式热重载）
```

## Configuration

Environment variables are managed through `.env` (copy from `env.example`).

### 核心配置

**LLM & Embedding**:
- `ARK_API_KEY / ARK_BASE_URL / ARK_MODEL`: LLM for text generation
- `SF_API_KEY / SF_BASE_URL / SF_EMBEDDING_MODEL`: Embedding (4096-dim)
- `EMBEDDING_DIM=4096`: **必须设置**（见下方关键陷阱）

**MinerU**:
- `MINERU_MODE=remote`: 使用远程 MinerU API（推荐）
- `MINERU_API_TOKEN` + `FILE_SERVICE_BASE_URL`: 远程模式必需

**External Storage**:
```bash
USE_EXTERNAL_STORAGE=true
KV_STORAGE=RedisKVStorage
VECTOR_STORAGE=PGVectorStorage
GRAPH_STORAGE=Neo4JStorage

# Redis
REDIS_URI=redis://redis:6379/0

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DATABASE=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your_password

# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_password
```

**Performance**:
- `TOP_K=20`: 减少实体检索数量（默认 60）
- `CHUNK_TOP_K=10`: 减少文本块检索（默认 20）
- `MAX_ASYNC=8`: LLM 并发请求数（默认 4）

## Multi-Tenant Usage

所有 API 端点需要 `tenant_id` 参数：
```bash
POST /query?tenant_id=your_tenant_id
POST /insert?tenant_id=your_tenant_id
GET /task/{task_id}?tenant_id=your_tenant_id
```

**Tenant Management**:
- `GET /tenants/stats?tenant_id=xxx`: 租户统计
- `DELETE /tenants/cache?tenant_id=xxx`: 清理租户缓存
- `GET /tenants/pool/stats`: 实例池统计（管理员）

## Architecture Notes

### Parser Selection Logic (`src/rag.py:select_parser_by_file()`)
- **Text files (.txt, .md)**: 返回 `None`（直接插入 LightRAG，无需解析）
- **Images (.jpg, .png)**: MinerU（OCR 能力）
- **PDF/Office < 500KB**: Docling（快速）
- **PDF/Office > 500KB**: MinerU（强大）

### Query Endpoints (`api/query.py`)
- `POST /query`: 标准查询（支持 8 个高级参数）
- `POST /query/stream`: 流式查询（SSE 格式）
- 查询模式：`naive`（最快，15-20s）、`local`、`global`、`hybrid`、`mix`（最慢）

### Task Management (`api/task.py`, `api/task_store.py`)
- 异步后台处理（FastAPI BackgroundTasks）
- 状态：`pending` → `processing` → `completed`/`failed`
- `BATCH_STORE`：批量任务精确追踪（修复了前缀匹配 bug）

## ⚠️ Critical Pitfalls（关键陷阱）

### 🚨 Embedding 维度配置陷阱（极其重要）

**问题描述**：向量插入失败，报错 `expected 1024 dimensions, not 4096`

**根本原因**（2025-10-30 调试 2+ 小时发现）：

1. **LightRAG 从环境变量读取维度**：
   ```python
   # lightrag/kg/postgres_impl.py
   content_vector VECTOR({os.environ.get("EMBEDDING_DIM", 1024)})
   ```
   默认值是 **1024**，必须显式设置 `EMBEDDING_DIM=4096`。

2. **Docker volume 名称陷阱**：
   - `docker-compose.dev.yml` 的项目名默认是**目录名** `rag-api`
   - Volume 前缀是 `rag-api_`（不是 `rag-api-dev_`）
   - 删除错误的 volume 名称导致数据库未重置！

3. **表结构持久化**：
   - PostgreSQL 表在首次启动时创建，维度固定
   - 即使修改 `EMBEDDING_DIM` 并重启，表结构不会改变
   - 必须**完全删除 volume** 才能重新初始化

**正确的解决方案**：

```bash
# 1. 停止所有服务
docker compose -f docker-compose.dev.yml down

# 2. 列出所有 volumes（确认正确的名称）
docker volume ls | grep -E "postgres|redis|neo4j"

# 3. 删除正确的 volumes（注意前缀是 rag-api_ 而非 rag-api-dev_）
docker volume rm rag-api_postgres_data rag-api_neo4j_data rag-api_redis_data rag-api_neo4j_logs

# 4. 确认 docker-compose 配置正确
grep -A 5 "EMBEDDING_DIM" docker-compose.dev.yml
# 应该看到：
#   environment:
#     - EMBEDDING_DIM=4096

# 5. 重新启动（这次会用正确的维度初始化）
docker compose -f docker-compose.dev.yml up -d

# 6. 验证数据库维度正确
docker exec rag-postgres-dev psql -U lightrag -d lightrag -c "
SELECT attrelid::regclass AS table_name,
       attname AS column_name,
       atttypmod AS dimensions
FROM pg_attribute
WHERE attrelid::regclass::text LIKE 'lightrag_vdb%'
AND attname = 'content_vector';
"
# 应该看到所有表都是 4096 维度
```

### 🚨 pgvector 索引限制（重要）

**问题**：
```
ERROR: column cannot have more than 2000 dimensions for hnsw index
```

**原因**：
- pgvector 的 HNSW 和 IVFFlat 索引最多支持 **2000 维度**
- 我们使用 4096 维度，无法创建索引

**影响**：
- ✅ 数据可以正常插入和查询
- ⚠️ 查询性能会受影响（无索引加速）

**解决方案**：
1. 接受无索引的性能（中小规模数据可接受）
2. 考虑降维到 2000 以内（权衡精度损失）
3. 等待 pgvector 未来版本支持

### 配置一致性检查清单

部署前必须确保：

**1. .env 文件**：
```bash
EMBEDDING_DIM=4096
SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B  # 4096 维度模型
```

**2. docker-compose 文件**（两个文件都要检查）：
```yaml
# docker-compose.yml 和 docker-compose.dev.yml
services:
  rag-api:
    environment:
      - EMBEDDING_DIM=4096

  lightrag-webui:
    environment:
      - EMBEDDING_DIM=4096
```

**3. 代码硬编码**（`src/multi_tenant.py`）：
```python
def _create_embedding_func(self):
    return EmbeddingFunc(
        embedding_dim=4096,  # 确保与配置一致
        ...
    )
```

**4. 首次部署后验证**：
```sql
-- 部署后立即验证
SELECT attrelid::regclass AS table_name,
       atttypmod AS dimensions
FROM pg_attribute
WHERE attrelid::regclass::text LIKE 'lightrag_vdb%'
AND attname = 'content_vector';
-- 所有表的 dimensions 应该都是 4096
```

### 其他常见陷阱

1. **multimodal_processed errors**: 删除 `./rag_local_storage` 清除损坏状态
2. **Remote MinerU failures**: 验证 `FILE_SERVICE_BASE_URL` 是公网 IP:8000
3. **Memory issues with local MinerU**: 切换到 `MINERU_MODE=remote`
4. **Slow queries (75s+)**: 增加 `MAX_ASYNC` 或使用 `naive` 模式
5. **Docker network errors**: 修改 `depends_on`/`networks` 后必须 `up -d --force-recreate`
6. **LightRAG WebUI CMD vs ENTRYPOINT**: 只提供参数，不要重复 `python -m` 命令

## File Structure

```
rag-api/
├── main.py              # FastAPI app entry point
├── api/                 # API route modules
│   ├── insert.py        # Document insertion (multi-tenant)
│   ├── query.py         # Query endpoints (+ stream)
│   ├── task.py          # Task status endpoints
│   ├── tenant.py        # Tenant management
│   ├── files.py         # File service (remote MinerU)
│   ├── monitor.py       # Performance monitoring
│   └── models.py        # Pydantic models
├── src/                 # Core business logic
│   ├── rag.py           # Multi-tenant lifecycle
│   ├── multi_tenant.py  # Instance manager (LRU cache)
│   ├── tenant_deps.py   # Tenant dependency injection
│   ├── logger.py        # Unified logging
│   ├── metrics.py       # Performance metrics
│   ├── file_url_service.py        # Temporary file HTTP service
│   ├── mineru_client.py           # Remote MinerU API client
│   └── mineru_result_processor.py # MinerU result processor
├── scripts/             # Maintenance and test scripts
├── docs/                # Documentation
└── rag_local_storage/   # LightRAG working directory (git-ignored)
```

## Recent Optimizations (2025-10-30)

### Query Enhancement & Stream Support
- Added 8 advanced parameters aligned with LightRAG official API
- New endpoint: `POST /query/stream` (SSE format)
- Support for multi-turn dialogue, custom prompts, response format control

### Batch Task Tracking Fix
- Added `BATCH_STORE` to replace unreliable prefix matching
- 100% accurate batch task mapping

### Parser Selection Optimization
- Text files (.txt, .md) now return `None` (no parser needed)
- More accurate logging: `direct_insert` instead of misleading `mineru`

### Documentation
- Created `docs/API_COMPARISON.md`: Comprehensive comparison with LightRAG official API
- **Key finding**: All 17 rag-api endpoints have differentiated value
- rag-api provides irreplaceable value: multi-tenant, strong parsing, batch processing, production ops

---

**最后更新**：2025-10-30
**关键教训**：维度配置不是可以后改的普通参数，而是数据库初始化的基石。一旦数据库创建完成，修改维度等同于推倒重来。Docker volume 名称由项目名决定，不是配置文件名！
