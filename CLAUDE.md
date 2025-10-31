# CLAUDE.md

## Language Preference
- **中文回复**，思考过程可用英文
- 代码注释和变量名使用英文
- Git commit 使用中文

## 🚨 第三方服务集成准则

**核心流程**（严格执行）：
1. **查源码**：确认环境变量准确命名，禁止猜测
2. **本地测试**：`docker exec` 验证所有相关配置
3. **完整检查**：确保无重复/冲突配置
4. **分步部署**：验证环境变量 → 检查日志 → 功能测试
5. **记录 BUG**：记录到 Known Bugs，避免重犯

**目标**：一次做对，减少调试时间

## Project Overview
**多租户 RAG API 服务**：FastAPI + LightRAG，支持 MinerU/Docling 多模态解析
- 租户隔离：独立 workspace + LRU 实例池（最多50个）
- Parser 选择：文本直插、图片/大文件用 MinerU、小文件用 Docling

## Deployment
```bash
# 一键部署（推荐）
./deploy.sh  # 选择生产/开发模式

# 生产模式
docker compose -f docker-compose.yml up -d

# 开发模式（热重载）
docker compose -f docker-compose.dev.yml up -d
```

**LightRAG WebUI**：http://localhost:9621/webui/ (多租户切换需修改 `.env` 中 `LIGHTRAG_WEBUI_WORKSPACE`)

**远程服务器**：45.78.223.205
- SSH: `ssh -i "C:\Users\jay.huang\Desktop\Scripts\chengjie.pem" root@45.78.223.205`
- 部署：PR 合并 → 服务器 `git pull` → 热重载生效

## Configuration (.env)

**核心配置**：
- **LLM/Embedding**: `ARK_*` (LLM) + `SF_*` (Embedding) + `EMBEDDING_DIM` (必须匹配模型)
- **MinerU**: `MINERU_MODE=remote`（推荐）+ `MINERU_API_TOKEN`
- **存储**: Redis (KV) + PostgreSQL (Vector) + Neo4j (Graph)
- **性能**: `TOP_K=20`, `CHUNK_TOP_K=10`, `MAX_ASYNC=8`

**多租户 API**：所有端点需 `?tenant_id=xxx` 参数

**架构要点**：
- Parser 选择：文本 None、图片 MinerU、PDF/Office 按大小选择
- 查询模式：`naive` 最快(15s)、`mix` 最慢
- 任务管理：异步后台处理，`BATCH_STORE` 精确追踪

## ⚠️ Critical Pitfalls

### 🚨 Embedding 维度配置陷阱
**核心原则**：`EMBEDDING_DIM` 必须与模型输出维度严格匹配

**推荐配置**：
- **1024 维度**（推荐）：`Qwen3-Embedding-0.6B` + Rerank，避免 pgvector 索引限制（最多 2000 维）
- **4096 维度**：`Qwen3-Embedding-8B`，需切换到 Qdrant（PostgreSQL 无法为 4096 创建索引）

**修改维度步骤**（⚠️ 必须删除 volume 重建数据库）：
```bash
docker compose down
docker volume rm rag-api_postgres_data rag-api_neo4j_data rag-api_redis_data
# 修改 .env 中 EMBEDDING_DIM 和 SF_EMBEDDING_MODEL
docker compose up -d
```

**陷阱**：
- Docker volume 前缀是**目录名** `rag-api_`（不是 `rag-api-dev_`）
- PostgreSQL 表结构在首次启动时创建，维度固定，重启不会改变
- 必须完全删除 volume 才能重新初始化

### 其他常见问题
- **multimodal_processed errors**: 删除 `./rag_local_storage`
- **MinerU 失败**: 验证 `FILE_SERVICE_BASE_URL` 或切换 `MINERU_MODE=remote`
- **查询慢 (75s+)**: 增加 `MAX_ASYNC` 或使用 `naive` 模式
- **Docker 网络错误**: `up -d --force-recreate`

## File Structure
- `main.py`: FastAPI 入口
- `api/`: 路由模块 (insert, query, task, tenant, files, monitor)
- `src/`: 核心逻辑 (rag, multi_tenant, mineru_client, logger, metrics)
- `rag_local_storage/`: LightRAG 工作目录（git-ignored）

## Known Bugs and Fixes

### BUG #1: Memgraph 环境变量配置错误（2025-10-31）
**问题**：多个同名环境变量 `MEMGRAPH=`，只有最后一个生效
**修复**：改用 `command:` 字段传递启动参数，不用 `environment`
**教训**：Docker Compose 同名环境变量会覆盖，多参数服务应用 `command`

### BUG #2: LightRAG WebUI API 配置命名错误（2025-10-31）
**问题**：使用 `OPENAI_*` 环境变量，但 LightRAG 读取的是 `LLM_BINDING_*`，导致 401 错误
**修复**：查看源码 `lightrag/api/config.py`，使用正确命名：
```yaml
- LLM_BINDING_API_KEY=${ARK_API_KEY}
- LLM_BINDING_HOST=${ARK_BASE_URL}
- EMBEDDING_BINDING_API_KEY=${SF_API_KEY}
- EMBEDDING_BINDING_HOST=${SF_BASE_URL}
```
**教训**：集成第三方服务必须查源码确认环境变量命名，禁止猜测。`docker compose restart` 不重载环境变量，必须 `up -d`

### BUG #3: 本地 MinerU 模式导致服务器宕机（2025-10-31）
**问题**：上传 2.7MB xlsx，LibreOffice 转换为 57MB PDF（膨胀 21 倍），MinerU 本地 OCR 导致 CPU 满载 43 分钟，系统失联
**根因**：`.env` 配置 `MINERU_MODE=local`，本地 VLM 模型处理大 PDF 资源耗尽
**修复**：改为 `MINERU_MODE=remote`
**教训**：
1. 配置错误影响巨大：`local` 模式仅适合开发，生产必须 `remote`
2. 文件转换隐藏成本：Office → PDF 可能膨胀 10-20 倍
3. 建议优化：Office 文档优先 Docling、添加任务超时(10min)、配置 Swap 空间

---

## Recent Optimizations (2025-10-30)
- **Query 增强**：8 个高级参数 + 流式端点 `/query/stream` (SSE)
- **任务追踪修复**：`BATCH_STORE` 替代前缀匹配，100% 准确
- **Parser 优化**：文本文件直插（返回 `None`），日志更准确
- **文档**：`docs/API_COMPARISON.md` 对比 LightRAG 官方 API，rag-api 提供不可替代价值

---

**最后更新**：2025-10-31
**核心教训**：
1. 维度配置是数据库初始化基石，修改需删除 volume 重建（Docker volume 前缀是**目录名**）
2. `MINERU_MODE=local` 导致 43 分钟宕机，生产必须 `remote`，Office 文件转换可能膨胀 10-20 倍