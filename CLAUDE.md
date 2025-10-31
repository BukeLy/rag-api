# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language Preference

**Default Response Language**: Chinese (Simplified)
- All responses, explanations, and documentation should be in Chinese
- Thinking process can remain in English
- Code comments and variable names should follow standard English conventions
- Git commits should be in Chinese

## Development Guidelines

### 🚨 第三方服务集成行为准则（Claude Code 必须严格遵守）

**场景**：集成任何第三方服务、库或框架时（如 LightRAG WebUI、MCP 服务器等）

**必须执行的步骤（按顺序）**：

1. **源码优先原则**（⚠️ 最高优先级）
   - ✅ **必做**：查看第三方服务的源码，确认环境变量、配置项的**准确命名**
   - ✅ **必做**：查看参数读取逻辑（如 `get_env_value()`, `os.getenv()` 等）
   - ❌ **禁止**：根据常识或文档猜测配置名称
   - ❌ **禁止**：假设配置命名符合"常规惯例"

2. **本地测试验证**（部署前必须完成）
   - ✅ **必做**：使用 `docker exec` 或 Python 脚本模拟环境变量读取
   - ✅ **必做**：验证**所有相关配置**（如 LLM + Embedding 必须一起检查）
   - ✅ **必做**：记录测试命令和结果
   - ❌ **禁止**：只测试部分配置就认为全部正确

3. **配置完整性检查**
   - ✅ **必做**：检查配置文件中的**所有相关环境变量**
   - ✅ **必做**：确认每个环境变量都有对应的源码依据
   - ✅ **必做**：检查是否有重复或冲突的配置
   - ❌ **禁止**：只修改部分配置就提交

4. **分步部署验证**
   - ✅ **必做**：提交前再次确认所有修改
   - ✅ **必做**：部署后验证容器内环境变量：`docker exec <container> env | grep <关键词>`
   - ✅ **必做**：查看服务启动日志，确认无错误
   - ✅ **必做**：进行实际功能测试（如上传文档、API 调用等）
   - ❌ **禁止**：假设配置修改后"应该能工作"

5. **错误记录与总结**
   - ✅ **必做**：每次遇到配置错误都记录到 CLAUDE.md 的 "Known Bugs and Fixes"
   - ✅ **必做**：记录错误原因、修复方案、验证方法、经验教训
   - ✅ **必做**：更新相关文档和配置注释
   - ❌ **禁止**：犯同样的错误两次

**用户明确要求时的处理**：
- 当用户说"确认好了再部署"时：
  - ✅ **必做**：严格执行上述所有步骤
  - ✅ **必做**：向用户报告每个步骤的验证结果
  - ✅ **必做**：等待用户明确确认后再部署
  - ❌ **禁止**：跳过任何验证步骤

**违反准则的后果**：
- 浪费用户时间
- 降低用户信任
- 需要多次往返调试
- 可能影响生产环境

**本准则的目标**：
- 一次性做对
- 减少调试时间
- 提高配置可靠性
- 积累可复用的经验

---

### BUG Documentation Policy

**⚠️ 重要准则**：每次发现 BUG 都必须记录在本文件的 "Known Bugs and Fixes" 章节中。

**记录内容应包括**：
1. **BUG 描述**：简洁说明问题现象
2. **根本原因**：分析为什么会出现这个问题
3. **修复方案**：如何解决这个问题
4. **发现日期**：便于追溯和统计
5. **相关文件**：涉及哪些配置或代码文件

**目的**：
- 避免重复犯错
- 积累项目经验
- 帮助新开发者快速了解常见问题

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

**SSH Access**:
- MacOS: `ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205`
- Windows: `ssh -i "C:\Users\jay.huang\Desktop\Scripts\chengjie.pem" root@45.78.223.205`

**部署流程**（通过 PR）：
```bash
# 1. 本地开发
git checkout -b feature/xxx
git commit -m "feat: xxx"
git push origin feature/xxx

# 2. GitHub 创建 PR 并合并到 main

# 3. 服务器更新（根据你的操作系统选择对应的 SSH 命令）
# MacOS:
ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205
# Windows:
ssh -i "C:\Users\jay.huang\Desktop\Scripts\chengjie.pem" root@45.78.223.205

cd ~/rag-api
git pull origin main
# 代码变更立即生效（开发模式热重载）
```

## Configuration

Environment variables are managed through `.env` (copy from `env.example`).

### 核心配置

**LLM & Embedding**:
- `ARK_API_KEY / ARK_BASE_URL / ARK_MODEL`: LLM for text generation
- `SF_API_KEY / SF_BASE_URL / SF_EMBEDDING_MODEL`: Embedding model
- `EMBEDDING_DIM`: **必须与模型匹配**（默认 1024，见下方说明）

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

**核心原则**：`EMBEDDING_DIM` 必须与 Embedding 模型输出维度**严格匹配**

**推荐配置**（env.example 默认）：
- **Qwen3-Embedding-0.6B** → `EMBEDDING_DIM=1024`（轻量级，配合 Rerank 效果好）
- **Qwen3-Embedding-8B** → `EMBEDDING_DIM=4096`（高精度，需要更多资源）

**问题描述**：向量插入失败，报错 `expected 1024 dimensions, not 4096`（或反之）

**根本原因**（2025-10-30 调试 2+ 小时发现）：

1. **配置一致性要求**：
   - `.env` 中的 `EMBEDDING_DIM`
   - `docker-compose.yml` / `docker-compose.dev.yml` 中的环境变量
   - 实际使用的 Embedding 模型输出维度
   - 这三者**必须完全一致**

2. **LightRAG 从环境变量读取维度**：
   ```python
   # lightrag/kg/postgres_impl.py
   content_vector VECTOR({os.environ.get("EMBEDDING_DIM", 1024)})
   ```
   默认值是 1024。现在 docker-compose 文件已改为动态读取 `.env`：
   ```yaml
   - EMBEDDING_DIM=${EMBEDDING_DIM:-1024}
   ```

3. **Docker volume 名称陷阱**：
   - `docker-compose.dev.yml` 的项目名默认是**目录名** `rag-api`
   - Volume 前缀是 `rag-api_`（不是 `rag-api-dev_`）
   - 删除错误的 volume 名称导致数据库未重置！

4. **表结构持久化**：
   - PostgreSQL 表在首次启动时创建，维度固定
   - 即使修改 `EMBEDDING_DIM` 并重启，表结构不会改变
   - 必须**完全删除 volume** 才能重新初始化

**修改维度时的正确步骤**：

```bash
# 1. 停止所有服务
docker compose -f docker-compose.dev.yml down

# 2. 列出所有 volumes（确认正确的名称）
docker volume ls | grep -E "postgres|redis|neo4j"

# 3. 删除正确的 volumes（注意前缀是 rag-api_ 而非 rag-api-dev_）
docker volume rm rag-api_postgres_data rag-api_neo4j_data rag-api_redis_data rag-api_neo4j_logs

# 4. 修改 .env 文件设置正确的维度
# 例如切换到 4096 维度：
# EMBEDDING_DIM=4096
# SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B

# 5. 确认 .env 配置
grep -E "EMBEDDING_DIM|SF_EMBEDDING_MODEL" .env

# 6. 重新启动（这次会用正确的维度初始化）
docker compose -f docker-compose.dev.yml up -d

# 7. 验证数据库维度正确
docker exec rag-postgres-dev psql -U lightrag -d lightrag -c "
SELECT attrelid::regclass AS table_name,
       attname AS column_name,
       atttypmod AS dimensions
FROM pg_attribute
WHERE attrelid::regclass::text LIKE 'lightrag_vdb%'
AND attname = 'content_vector';
"
# 应该看到所有表都是你设置的维度（1024 或 4096）
```

### 🚨 pgvector 索引限制（重要）

**问题**：使用 PostgreSQL + pgvector 时遇到索引限制
```
ERROR: column cannot have more than 2000 dimensions for hnsw index
```

**原因**：
- pgvector 的 HNSW 和 IVFFlat 索引最多支持 **2000 维度**
- 如果使用 4096 维度模型（Qwen3-Embedding-8B），无法创建索引

**影响**：
- ✅ 数据可以正常插入和查询
- ⚠️ 查询性能会受影响（无索引加速）

**推荐方案**（按优先级）：
1. **使用 1024 维度模型**（`Qwen3-Embedding-0.6B` + Rerank）：避免索引限制
2. **切换到 Qdrant** 向量存储：无维度限制，支持 4096 维度 + HNSW 索引
3. 接受无索引的性能（中小规模数据可接受）
4. 等待 pgvector 未来版本支持更高维度索引

### 配置一致性检查清单

部署前必须确保模型与维度配置匹配：

**1. .env 文件**（选择一种配置）：

**选项 A - 轻量级（推荐）**：
```bash
EMBEDDING_DIM=1024
SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B  # 1024 维度
RERANK_MODEL=Qwen/Qwen2-7B-Instruct  # 配合 Rerank 提升质量
```

**选项 B - 高精度**：
```bash
EMBEDDING_DIM=4096
SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B  # 4096 维度
# 注意：PostgreSQL 无法为 4096 维度创建索引，建议使用 Qdrant
```

**2. docker-compose 文件**（已自动适配）：
```yaml
# docker-compose.yml 和 docker-compose.dev.yml
# ✅ 已修复：现在从 .env 动态读取
services:
  rag-api:
    environment:
      - EMBEDDING_DIM=${EMBEDDING_DIM:-1024}  # 从 .env 读取

  lightrag-webui:
    environment:
      - EMBEDDING_DIM=${EMBEDDING_DIM:-1024}  # 从 .env 读取
```

**3. 代码实现**（已正确实现）：
```python
# src/multi_tenant.py 和 src/rag.py
# ✅ 已正确：动态读取环境变量
embedding_dim = int(os.getenv("EMBEDDING_DIM", "1024"))
```

**4. 首次部署后验证**：
```bash
# 验证配置一致性
grep EMBEDDING_DIM .env
docker compose config | grep EMBEDDING_DIM

# 验证数据库维度
docker exec rag-postgres-dev psql -U lightrag -d lightrag -c "
SELECT attrelid::regclass AS table_name,
       atttypmod AS dimensions
FROM pg_attribute
WHERE attrelid::regclass::text LIKE 'lightrag_vdb%'
AND attname = 'content_vector';
"
# 应该看到所有表的维度与 .env 中配置一致
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

## Known Bugs and Fixes

### ❌ BUG #1: Memgraph 环境变量配置错误（2025-10-31）

**问题描述**：
在 `docker-compose.new-stack.yml` 中，Memgraph 配置使用了多个同名环境变量，导致只有最后一个生效。

**错误配置**（[docker-compose.new-stack.yml:131-139](docker-compose.new-stack.yml#L131-L139)）：
```yaml
environment:
  # 内存配置
  - MEMGRAPH="--memory-limit=1024"
  # 日志级别
  - MEMGRAPH="--log-level=WARNING"
  # 持久化配置
  - MEMGRAPH="--storage-snapshot-interval-sec=3600"
  - MEMGRAPH="--storage-wal-enabled=true"
  - MEMGRAPH="--storage-snapshot-on-exit=true"
entrypoint: ["/usr/lib/memgraph/memgraph"]
```

**根本原因**：
- Docker Compose 中，同名环境变量会相互覆盖
- 最终只有 `MEMGRAPH="--storage-snapshot-on-exit=true"` 生效
- 其他关键参数（内存限制、日志级别、快照间隔等）全部丢失
- 导致 Memgraph 容器反复重启，健康检查失败

**正确配置**：
```yaml
command: >
  --memory-limit=1024
  --log-level=WARNING
  --storage-snapshot-interval-sec=3600
  --storage-wal-enabled=true
  --storage-snapshot-on-exit=true
```

**修复方案**：
1. 移除 `environment` 和 `entrypoint` 字段
2. 使用 `command` 字段传递所有启动参数（参考 DragonflyDB 配置方式）

**教训**：
- Docker Compose 配置中不要使用重复的环境变量名
- 对于需要多个启动参数的服务，应使用 `command` 而非 `environment`
- 配置错误可能导致容器反复重启但日志中无明显错误信息

**相关 commit**:
- 修复提交：`0e2dd96` - fix(memgraph): 修复环境变量配置错误
- 涉及文件：`docker-compose.new-stack.yml`

---

### ❌ BUG #2: LightRAG WebUI API 配置环境变量命名错误（2025-10-31）

**问题描述**：
- WebUI 上传文档时出现 401 认证错误
- LLM 和 Embedding API 请求都发送到 OpenAI 官方 API
- 使用了错误的 API Key 或默认 base URL

**错误配置**（docker-compose.dev.yml）：
```yaml
# ❌ 错误：使用了不存在的环境变量名
- OPENAI_API_KEY=${ARK_API_KEY}
- OPENAI_BASE_URL=${ARK_BASE_URL}
- OPENAI_MODEL=${ARK_MODEL}
- EMBEDDING_OPENAI_API_KEY=${SF_API_KEY}
- EMBEDDING_OPENAI_BASE_URL=${SF_BASE_URL}
```

**根本原因**：
1. **环境变量命名不匹配**：
   - LightRAG WebUI 读取的是 `LLM_BINDING_*` 和 `EMBEDDING_BINDING_*`
   - 但配置文件使用了 `OPENAI_*` 和 `EMBEDDING_OPENAI_*`

2. **环境变量未生效**：
   - LightRAG 源码中使用 `get_env_value("LLM_BINDING_API_KEY")` 读取
   - 但容器中只有 `OPENAI_API_KEY`，导致读取失败
   - 最终使用默认值：base_url = "https://api.openai.com/v1"

3. **请求发送到错误的 API**：
   - 使用 ARK_API_KEY 但发送到 OpenAI 官方 API
   - 导致 401 错误："Incorrect API key provided"

**正确配置**（已验证）：
```yaml
# ✅ 正确：使用 LightRAG 源码中定义的环境变量名
# LLM 配置（使用 ARK）
- LLM_BINDING=openai
- LLM_BINDING_API_KEY=${ARK_API_KEY}
- LLM_BINDING_HOST=${ARK_BASE_URL}
- LLM_MODEL=${ARK_MODEL:-seed-1-6-250615}

# Embedding 配置（使用硅基流动）
- EMBEDDING_BINDING=openai
- EMBEDDING_BINDING_API_KEY=${SF_API_KEY}
- EMBEDDING_BINDING_HOST=${SF_BASE_URL}
- EMBEDDING_MODEL=${SF_EMBEDDING_MODEL:-Qwen/Qwen3-Embedding-0.6B}
- EMBEDDING_DIM=${EMBEDDING_DIM:-1024}
```

**验证方法**（源码确认）：
```python
# lightrag/api/config.py 第 404-409 行
args.llm_binding_host = get_env_value(
    "LLM_BINDING_HOST", get_default_host(args.llm_binding)
)
args.embedding_binding_host = get_env_value(
    "EMBEDDING_BINDING_HOST", get_default_host(args.embedding_binding)
)
args.llm_binding_api_key = get_env_value("LLM_BINDING_API_KEY", None)
args.embedding_binding_api_key = get_env_value("EMBEDDING_BINDING_API_KEY", "")
```

**修复步骤**：
1. ✅ 查看 LightRAG 源码确认正确的环境变量名
2. ✅ 使用 Docker exec 测试环境变量读取是否生效
3. ✅ 修改 docker-compose.dev.yml 使用正确命名
4. ⚠️ **关键**：必须 `docker compose up -d` 重新创建容器（`restart` 不会重新加载环境变量）
5. ✅ 验证容器内环境变量：`docker exec <container> env | grep BINDING`

**教训**：
1. **查源码优先**：集成第三方服务时，必须先查看其源码确认环境变量命名
2. **分步验证**：
   - 先本地测试环境变量命名（用 Python 脚本模拟）
   - 再部署到容器验证
   - 最后测试实际功能
3. **容器环境变量更新**：`docker compose restart` 不会重新加载 `.env`，必须 `up -d`
4. **全面检查**：LLM 和 Embedding 通常需要相同的配置模式，修改时要一起检查
5. **记录错误**：每次遇到配置问题都要记录到 CLAUDE.md，避免重复犯错

**相关文件**：
- `docker-compose.dev.yml`：WebUI 服务配置
- `lightrag/api/config.py`：LightRAG 环境变量读取逻辑

**发现日期**：2025-10-31

---

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
- 用户本地没有Docker