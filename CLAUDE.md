# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Preference

  **Default Response Language**: Chinese (Simplified)
  - All responses, explanations, and documentation
  should be in Chinese
  - Thinking process can remain in English
  - Code comments and variable names should follow
  standard English conventions
  - Git commits should be in Chinese

## Project Overview

This is a **multi-tenant** multimodal RAG (Retrieval-Augmented Generation) API service built with FastAPI, combining RAG-Anything and LightRAG for document processing and intelligent querying.

**Key Architecture**: Multi-Tenant LightRAG + Multiple Parsers
- **Multi-tenant isolation**: Each tenant has isolated LightRAG instance (via workspace)
- **Instance pool management**: LRU cache (max 50 instances by default)
- **Shared resources**: LLM/Embedding functions shared across tenants
- **MinerU parser**: Powerful multimodal parsing (OCR, tables, equations) with high memory usage
- **Docling parser**: Lightweight fast parsing for simple documents
- **Direct LightRAG query**: Bypasses parsers for 95% of text queries, optimizing performance

## Branch Strategy

- **`main` branch** (唯一主分支)
  - 所有代码都在此分支开发和部署
  - 生产环境和开发环境通过不同的 docker-compose 文件区分
  - 新功能开发通过 Pull Request 流程合并

### 开发流程 (Pull Request Workflow)

1. **创建功能分支**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **开发和提交**
   ```bash
   git add .
   git commit -m "feat: 功能描述"
   ```

3. **推送到远端并创建 PR**
   ```bash
   git push origin feature/your-feature-name
   # 在 GitHub 上创建 Pull Request
   ```

4. **PR 合并后删除功能分支**
   ```bash
   git checkout main
   git pull origin main
   git branch -d feature/your-feature-name
   git push origin --delete feature/your-feature-name
   ```

## Deployment Commands

### 使用一键部署脚本（推荐）

```bash
./deploy.sh
# 会提示选择部署模式：
# 1) 生产模式 (Production)
# 2) 开发模式 (Development)
```

### 生产模式部署

```bash
# 启动服务
docker compose -f docker-compose.yml up -d

# 查看日志
docker compose -f docker-compose.yml logs -f

# 重启服务
docker compose -f docker-compose.yml restart

# 停止服务
docker compose -f docker-compose.yml down
```

### 开发模式部署（代码热重载）

```bash
# 启动服务（代码外挂，支持热重载）
docker compose -f docker-compose.dev.yml up -d

# 或使用快捷脚本
./scripts/dev.sh

# 查看日志
docker compose -f docker-compose.dev.yml logs -f

# 停止服务
docker compose -f docker-compose.dev.yml down
```

### Testing & Monitoring
```bash
# Monitor service health
./scripts/monitor.sh

# Backup data
./scripts/backup.sh

# Update deployment
./scripts/update.sh

# Performance monitoring
./scripts/monitor_performance.sh

# Concurrent performance test
./scripts/test_concurrent_perf.sh
```

## Remote Deployment

### Testing Server
- **Host**: 45.78.223.205
- **SSH Access**: `ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205`
- **Deployment Method**: Git-based deployment via GitHub
- **Environment**: 使用开发模式（docker-compose.dev.yml）支持代码热重载

### Deployment Workflow

**Three-Way Sync Architecture**:
```
Local Machine ──git push──> GitHub ──git pull──> Remote Server (45.78.223.205)
```

All code changes must be pushed to GitHub first to ensure synchronization across all three endpoints:
1. Local development machine
2. GitHub repository (central source of truth)
3. Testing server

### Deploying Code to Testing Server (45.78.223.205)

**推荐方式：通过 PR 合并后部署**

```bash
# 1. 本地开发：创建功能分支
git checkout -b feature/your-feature-name

# 2. 开发并提交
git add .
git commit -m "feat: 功能描述"
git push origin feature/your-feature-name

# 3. 在 GitHub 创建 PR 并合并到 main

# 4. SSH 到测试服务器并更新
ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205
cd ~/rag-api
git pull origin main

# 5. 代码变更立即生效（开发模式热重载）
# 仅在修改依赖或配置时需要重启：
docker compose -f docker-compose.dev.yml restart  # 仅在需要时
```

### Quick Deployment Commands

```bash
# 快速部署到测试服务器（PR 合并后）
git push && ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205 "cd ~/rag-api && git pull origin main"
```

**Important Notes**:
- 测试服务器使用**开发模式** (docker-compose.dev.yml) 支持热重载
- 代码变更 (src/, api/, main.py) **立即生效**，无需重新构建
- 始终先推送到 GitHub，再部署到测试服务器
- 禁止直接在测试服务器上提交代码
- SSH 密钥需要正确权限：`chmod 600 /Users/chengjie/Downloads/chengjie.pem`
- 所有开发通过功能分支 + PR 流程完成

## Configuration

Environment variables are managed through `.env` (copy from `env.example`):

### Required Configuration
- **ARK_API_KEY / ARK_BASE_URL / ARK_MODEL**: LLM for text generation and entity extraction
- **SF_API_KEY / SF_BASE_URL / SF_EMBEDDING_MODEL**: Embedding service (4096-dim vectors)
- **RERANK_MODEL**: Optional reranker model to improve retrieval relevance

### MinerU Modes
- **local**: Runs MinerU locally (requires GPU, high memory)
- **remote**: Uses remote MinerU API (recommended, saves resources)
  - Requires **MINERU_API_TOKEN** and **FILE_SERVICE_BASE_URL**
  - Model version: `pipeline` (stable) or `vlm` (faster, more accurate, recommended)

### External Storage Configuration

**Important**: LightRAG 1.4.9.4 uses **environment variables** for external storage configuration, not initialization parameters.

To enable external storage:

1. **Set storage toggle**:
   ```bash
   USE_EXTERNAL_STORAGE=true
   KV_STORAGE=RedisKVStorage
   VECTOR_STORAGE=PGVectorStorage
   GRAPH_STORAGE=Neo4JStorage
   ```

2. **Configure Redis** (for KV storage):
   ```bash
   REDIS_URI=redis://redis:6379/0  # URI format required
   REDIS_WORKSPACE=default          # Optional
   ```

3. **Configure PostgreSQL** (for vector storage):
   ```bash
   POSTGRES_HOST=postgres
   POSTGRES_PORT=5432
   POSTGRES_DATABASE=lightrag       # Note: POSTGRES_DATABASE not POSTGRES_DB
   POSTGRES_USER=lightrag
   POSTGRES_PASSWORD=your_password
   POSTGRES_WORKSPACE=default
   POSTGRES_MAX_CONNECTIONS=20
   ```

4. **Configure Neo4j** (for graph storage):
   ```bash
   NEO4J_URI=bolt://neo4j:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=your_password
   NEO4J_WORKSPACE=default
   ```

**Key Points**:
- ✅ Storage backends read connection info from environment variables
- ❌ Do NOT pass `*_cls_kwargs` parameters to LightRAG.__init__()
- 📝 See `env.example` for complete configuration template

### Performance Tuning

**Current configuration is optimized for EC2 persistent containers.**

#### Core Parameters
- **TOP_K**: Number of entities/relations to retrieve (default: 20, was 60)
- **CHUNK_TOP_K**: Number of text chunks to retrieve (default: 10, was 20)
- **MAX_ASYNC**: LLM concurrent requests (default: 8, optimized from 4)
- **DOCUMENT_PROCESSING_CONCURRENCY**: Concurrent document processing (1 for local, 10+ for remote)

#### Deployment-Specific Recommendations

**EC2/ECS Persistent Containers** (Current setup):
- `MAX_ASYNC=8`: Fully leverage persistent HTTP connections
- Worker warmup: Enabled in `src/rag.py:lifespan()` to reduce first query delay
- Expected performance: First query ~15s (after warmup), subsequent queries 6-11s
- Best for: Stable traffic (>5 req/hour), 7x24 services

**Fargate Auto-Scaling** (Alternative):
- `MAX_ASYNC=4`: Reduce cold start overhead
- Worker warmup: Still beneficial but less effective due to frequent container restarts
- Expected performance: First query ~35s, subsequent queries 10-15s
- Best for: Variable traffic, cost optimization for low-frequency usage

**Lambda/Serverless** (Not recommended):
- Worker initialization delay (25-35s per cold start) significantly impacts user experience
- HTTP connection pooling ineffective due to short container lifetime
- See `docs/LIGHTRAG_WORKER_MECHANISM_SOURCE_CODE_ANALYSIS.md` for detailed analysis

## Architecture Notes

### Single LightRAG + Multiple Parsers Pattern

The system uses a **shared LightRAG instance** (`global_lightrag_instance` in `src/rag.py:26`) that all parsers write to:

1. **Document Insertion** (`/insert` endpoint in `api/insert.py`):
   - Routes through RAGAnything parsers (MinerU or Docling)
   - Parser selection: automatic based on file type/size, or manual
   - Text files (.txt, .md) bypass parsers and insert directly to LightRAG
   - Remote MinerU mode: uploads file to file service, calls remote API, processes markdown result

2. **Query** (`/query` endpoint in `api/query.py`):
   - **Directly accesses LightRAG** via `get_lightrag_instance()`
   - Bypasses all parsers for optimal query performance
   - Solves read/write concurrency conflicts
   - Query modes: `naive` (fastest, 15-20s), `local`, `global`, `hybrid`, `mix` (slowest, most comprehensive)

3. **Task Management** (`api/task.py`, `api/task_store.py`):
   - Async background processing with FastAPI BackgroundTasks
   - Task statuses: `pending`, `processing`, `completed`, `failed`
   - Shared in-memory `TASK_STORE` for status tracking
   - Semaphore-based concurrency control (`DOCUMENT_PROCESSING_SEMAPHORE`)

### File Service for Remote MinerU

When `MINERU_MODE=remote`, the system:
1. Uploads files to temporary HTTP-accessible storage (`src/file_url_service.py`)
2. Passes file URLs to remote MinerU API (`src/mineru_client.py`)
3. Polls for completion and processes markdown results (`src/mineru_result_processor.py`)
4. Auto-cleanup of temporary files after configurable retention period

### Parser Selection Logic

Implemented in `src/rag.py:select_parser_by_file()`:
- **Images (.jpg, .png)**: MinerU (OCR capability)
- **Text files (.txt, .md)**: Direct LightRAG insertion (no parser)
- **PDF/Office < 500KB**: Docling (fast)
- **PDF/Office > 500KB**: MinerU (powerful)

## Multi-Tenant Usage

**All API endpoints require `tenant_id` parameter:**

```bash
# Query
POST /query?tenant_id=your_tenant_id

# Document upload
POST /insert?tenant_id=your_tenant_id

# Task status
GET /task/{task_id}?tenant_id=your_tenant_id
```

### Tenant Isolation

- **Data isolation**: Each tenant's documents and queries are completely isolated
- **Workspace-based**: Uses LightRAG's native workspace mechanism
- **External storage**: Redis/PostgreSQL/Neo4j with tenant-specific namespaces
  - Redis: `tenant_a:kv_store`
  - PostgreSQL: `tenant_a:vectors`
  - Neo4j: `tenant_a:GraphDB`

### Tenant Management

- **GET /tenants/stats?tenant_id=xxx**: Get tenant statistics
- **DELETE /tenants/cache?tenant_id=xxx**: Clear tenant instance cache
- **GET /tenants/pool/stats**: Get instance pool statistics (admin)

## API Routes

All routes are organized in `api/` directory and registered via `api/__init__.py`:

- **Document Processing**: `api/insert.py`
  - `POST /insert?tenant_id=xxx`: Single document upload (returns task_id)
  - `POST /batch?tenant_id=xxx`: Batch document upload (up to 100 files)
  - `GET /batch/{batch_id}?tenant_id=xxx`: Check batch progress

- **Query**: `api/query.py`
  - `POST /query?tenant_id=xxx`: Query the knowledge graph

- **Task Management**: `api/task.py`
  - `GET /task/{task_id}?tenant_id=xxx`: Get task status

- **Tenant Management**: `api/tenant.py`
  - `GET /tenants/stats?tenant_id=xxx`: Get tenant statistics
  - `DELETE /tenants/cache?tenant_id=xxx`: Clear tenant cache
  - `GET /tenants/pool/stats`: Get instance pool statistics

- **File Service**: `api/files.py`
  - `GET /files/{file_id}/{filename}`: Download temporary files (for remote MinerU)

- **Performance Monitoring**: `api/monitor.py`
  - System metrics collection via `src/metrics.py`

## Important Implementation Details

### Multi-Tenant Architecture

**Core Components**:
- `src/multi_tenant.py`: Multi-tenant instance manager (LRU cache)
- `src/tenant_deps.py`: FastAPI dependency for tenant identification
- `api/tenant.py`: Tenant management endpoints

**Lifespan Management** (`src/rag.py:lifespan()`):
- Initializes multi-tenant manager (lazy loading)
- No shared LightRAG instance created at startup
- Tenant instances created on-demand (first request)
- Starts file cleanup background task
- Starts performance monitoring

**Tenant Instance Lifecycle**:
1. First request: Create LightRAG instance with `workspace=tenant_id`
2. Subsequent requests: Reuse cached instance
3. Pool full: Remove oldest instance (LRU strategy)
4. Manual cleanup: `DELETE /tenants/cache?tenant_id=xxx`

### Logging
Unified logging via `src/logger.py` using loguru:
- Structured JSON logs for production
- Automatic log rotation based on `LOG_RETENTION_DAYS`
- Log level controlled by `LOG_LEVEL` env var

### Error Handling in Document Processing
`api/insert.py:process_document_task()` handles:
- **MineruExecutionError**: Unsupported file format
- **ValueError**: Empty files, validation errors
- **OSError**: File system errors
- Always cleans up temporary files in `finally` block

### Performance Optimizations Applied
1. Reduced `TOP_K` from 60 to 20 (fewer entities retrieved)
2. Reduced `CHUNK_TOP_K` from 20 to 10 (fewer text chunks)
3. Increased `MAX_ASYNC` from 4 to 8 (faster entity merging)
4. Enabled rerank for better relevance (adds 2-3s but improves quality)
5. Direct LightRAG query path (bypasses parser overhead)

## Cursor Rules

From `.cursor/rules/docs-rules.mdc`:
- All documentation files must be placed in `docs/` folder

## Common Pitfalls

1. **multimodal_processed errors**: Delete `./rag_local_storage` to clear corrupted state
2. **Remote MinerU failures**: Verify `FILE_SERVICE_BASE_URL` is set to public IP:8000, not localhost
3. **Memory issues with local MinerU**: Switch to `MINERU_MODE=remote` or reduce `DOCUMENT_PROCESSING_CONCURRENCY` to 1
4. **Slow queries (75s+)**: Increase `MAX_ASYNC` in `.env` or use `naive` query mode instead of `mix`
5. **Empty file uploads**: API returns 400 with detailed error message

## File Structure

```
rag-api/
├── main.py              # FastAPI app entry point
├── api/                 # API route modules
│   ├── __init__.py      # Router aggregation (includes tenant router)
│   ├── insert.py        # Document insertion endpoints (multi-tenant)
│   ├── query.py         # Query endpoints (multi-tenant)
│   ├── task.py          # Task status endpoints (multi-tenant)
│   ├── tenant.py        # Tenant management endpoints (NEW)
│   ├── files.py         # File service endpoints
│   ├── monitor.py       # Performance monitoring endpoints
│   ├── models.py        # Pydantic models
│   └── task_store.py    # In-memory task tracking (tenant-isolated)
├── src/                 # Core business logic
│   ├── rag.py           # Multi-tenant lifecycle management
│   ├── multi_tenant.py  # Multi-tenant instance manager (NEW)
│   ├── tenant_deps.py   # Tenant dependency injection (NEW)
│   ├── logger.py        # Unified logging
│   ├── metrics.py       # Performance metrics collection
│   ├── file_url_service.py        # Temporary file HTTP service
│   ├── mineru_client.py           # Remote MinerU API client
│   └── mineru_result_processor.py # MinerU result processor
├── scripts/             # Maintenance and test scripts
├── docs/                # Documentation (per Cursor rules)
└── rag_local_storage/   # LightRAG working directory (git-ignored)
```
