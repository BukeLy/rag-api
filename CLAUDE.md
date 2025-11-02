# CLAUDE.md

## Language Preference
- **中文回复**，思考过程可用英文
- 代码注释和变量名使用英文
- Git commit 使用中文

## 🧰 MCP Servers 使用指南

**已接入的 MCP Servers**：

### 1. **context7** - 库文档检索
**使用场景**：查看第三方库（RAG-Anything、LightRAG、MinerU）的最新文档和 API

**使用方法**：
```bash
# 1. 解析库 ID
mcp__context7__resolve-library-id(libraryName="RAG-Anything")
# 2. 获取文档
mcp__context7__get-library-docs(context7CompatibleLibraryID="/hkuds/rag-anything", topic="parser methods")
```

### 2. **memory** - 知识图谱
**使用场景**：查询项目历史 BUG、库的核心 API、架构决策

**使用方法**：
```bash
# 搜索 BUG
mcp__memory__search_nodes(query="MinerU timeout")
# 搜索库的方法
mcp__memory__search_nodes(query="RAG-Anything MineruParser")
# 查看实体详情
mcp__memory__open_nodes(names=["RAG-Anything", "LightRAG"])
```

**已记录内容**：
- **库实体**：RAG-Anything, LightRAG, MinerU（核心 API、方法签名、配置参数）
- **BUG 实体**：9 个历史 BUG（问题、根因、修复、教训）
- **项目实体**：rag-api Project（架构、模块、依赖）

### 3. **filesystem** - 文件系统操作
**使用场景**：批量文件操作、目录树结构、文件元数据

---

## 🚨 核心规则（严格执行）

### 1. 第三方库集成
- ✅ **必须查源码**：确认 API 签名、环境变量命名
- ✅ **优先使用原生能力**：不重新发明轮子（如 `MineruParser._read_output_files()`）
- ✅ **用 curl 测试 API**：先验证响应结构，再写解析代码
- ❌ **禁止猜测**：不猜测 API 参数、环境变量名、响应格式

### 2. Git Commit 前置检查
**必须完成以下检查**：
1. ✅ 生产/开发环境配置同步（`diff` 两个 docker-compose 文件）
2. ✅ `.env` 示例文件同步
3. ✅ 本地测试通过

### 3. Docker 配置
- Docker volume 前缀是**目录名**（如 `rag-api_postgres_data`），不是项目名
- 修改 embedding 维度需删除 volume 重建：`docker volume rm rag-api_postgres_data`
- `docker compose restart` 不重载环境变量，必须 `up -d`
- 开发模式部署：`git pull` 即可（代码热重载），不需要 `--build`
- 生产模式部署：`docker compose up -d --build`（重新构建镜像）

### 4. 第三方 API 调用
- ✅ **必须显式设置超时**：写入环境变量，可配置
- ✅ **Batch API 状态聚合**：从子项聚合，不能直接获取
- ✅ **追踪数据流**：修复 API 解析后，确保所有下游代码路径同步更新

### 5. 环境配置陷阱
- ❌ **禁止 `MINERU_MODE=local` 用于生产**：本地 VLM 模型资源耗尽，仅开发用
- ❌ **禁止猜测环境变量名**：LightRAG 使用 `LLM_BINDING_*`，不是 `OPENAI_*`
- ✅ **持久化存储**：`/tmp` 目录容器重启后清空，需挂载为 Docker volume

---

## Project Overview
**多租户 RAG API 服务**：FastAPI + LightRAG + RAG-Anything
- 租户隔离：独立 workspace + LRU 实例池（最多 50 个）
- Parser 选择：文本直插、图片/大文件用 MinerU、小文件用 Docling
- VLM 模式：off（最快）/ selective / full（最慢）

## Deployment
```bash
# 一键部署（推荐）
./deploy.sh  # 选择生产/开发模式

# 开发模式（热重载）
docker compose -f docker-compose.dev.yml up -d

# 生产模式
docker compose -f docker-compose.yml up -d
```

**LightRAG WebUI**：http://localhost:9621/webui/

**远程服务器**：45.78.223.205
- SSH (macOS): `ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205`
- 部署：PR 合并 → 服务器 `git pull` → 热重载生效（开发模式）

## Configuration (.env)

**核心配置**：
- **LLM/Embedding**: `ARK_*` (LLM) + `SF_*` (Embedding) + `EMBEDDING_DIM` (必须匹配模型)
- **MinerU**: `MINERU_MODE=remote`（推荐）+ `MINERU_API_TOKEN` + `MINERU_HTTP_TIMEOUT=60`
- **存储**: Redis (KV) + PostgreSQL (Vector) + Neo4j (Graph)
- **性能**: `TOP_K=20`, `CHUNK_TOP_K=10`, `MAX_ASYNC=8`

**多租户 API**：所有端点需 `?tenant_id=xxx` 参数

## File Structure
- `main.py`: FastAPI 入口
- `api/`: 路由模块 (insert, query, task, tenant, files, monitor)
- `src/`: 核心逻辑 (rag, multi_tenant, mineru_client, logger, metrics)
- `rag_local_storage/`: LightRAG 工作目录（git-ignored）

## ⚠️ Critical Pitfalls

### Embedding 维度配置
- `EMBEDDING_DIM` 必须与模型输出维度严格匹配
- 推荐：1024 维（`Qwen3-Embedding-0.6B`），避免 pgvector 限制
- 修改维度：删除 volume → 修改 `.env` → 重新启动

### MinerU 模式
- ❌ 生产禁止 `local` 模式：43 分钟宕机案例
- ✅ 生产必须 `remote` 模式

### Docker Volume
- 前缀是目录名（如 `rag-api_postgres_data`），不是项目名
- 必须同时在 `services.*.volumes` 和顶层 `volumes` 中定义

### 环境变量重载
- `docker compose restart` 不重载环境变量
- 修改 `.env` 后必须 `docker compose up -d`

---

## 查询历史 BUG 和库 API

**使用 Memory MCP 查询**：
```bash
# 查询所有 BUG
mcp__memory__search_nodes(query="BUG")

# 查询特定问题
mcp__memory__search_nodes(query="MinerU timeout")
mcp__memory__search_nodes(query="embedding dimension")

# 查询库的核心方法
mcp__memory__search_nodes(query="RAG-Anything MineruParser")
mcp__memory__search_nodes(query="LightRAG insert methods")

# 查看完整实体
mcp__memory__open_nodes(names=["RAG-Anything", "LightRAG", "MinerU"])
```

**记录内容包含**：
- 9 个历史 BUG：问题、根因、修复步骤、核心教训
- RAG-Anything：核心类、方法签名、VLM 模式、配置参数
- LightRAG：insert/query 方法、API 端点、配置参数
- MinerU：CLI/API 用法、输出格式、backend 类型

---

**最后更新**：2025-11-02
