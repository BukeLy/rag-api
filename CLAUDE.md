# CLAUDE.md

## Language Preference
- **中文回复**，思考过程可用英文
- 代码注释和变量名使用英文
- Git commit 使用中文

## 🖥️ 本地环境说明
- **本地没有 Docker**：本地开发环境不使用 Docker，直接使用 Python 虚拟环境
- **测试环境**：需要在远程服务器上运行测试（服务器信息见 [DEPLOYMENT_PRIVATE.md](./DEPLOYMENT_PRIVATE.md)）
- **开发流程**：本地修改代码 → git push → 远程服务器 git pull → 自动热重载

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
- **BUG 实体**：13 个历史 BUG（问题、根因、修复、教训）
- **项目实体**：rag-api Project（架构、模块、依赖）

**最新 BUG 快速查询**：
```bash
# 查询最新的 BUG（如参考资料格式问题）
mcp__memory__search_nodes(query="Document Title One reference")
# 查询所有 BUG
mcp__memory__search_nodes(query="BUG")
# 查看特定 BUG 详情
mcp__memory__open_nodes(names=["BUG-13-LightRAG-Reference-Document-Title-One"])
```

### 3. **filesystem** - 文件系统操作
**使用场景**：批量文件操作、目录树结构、文件元数据

---

## 🤖 SubAgent (Task) 使用规则

### 何时必须使用 SubAgent 执行任务

**触发条件（满足任一）**：
1. ✅ **执行测试/命令会输出大量日志**
   - 示例：Docker 构建、测试脚本、性能测试、数据库迁移
   - 原因：避免主 Agent 上下文被日志污染

2. ✅ **需要多轮迭代的探索性任务**
   - 示例：调试问题、搜索代码、理解复杂系统
   - 原因：Sub Agent 可以自主探索，不占用主 Agent 对话轮次

3. ✅ **并行执行多个独立任务**
   - 示例：同时测试多个环境、批量数据处理
   - 原因：提升效率，避免串行等待

**使用方法**：
```python
Task(
    description="执行远程部署测试",
    prompt="在服务器 $PRODUCTION_SERVER 上执行以下操作：\n1. git pull\n2. 重启服务\n3. 测试 API 健康检查\n4. 返回测试结果摘要（不要返回完整日志）",
    subagent_type="general-purpose"
)
```

> 💡 **注意**：`$PRODUCTION_SERVER` 等敏感信息请查看 [DEPLOYMENT_PRIVATE.md](./DEPLOYMENT_PRIVATE.md)（仅本地）

**关键要求**：
- ❌ **禁止**在 prompt 中要求返回完整日志
- ✅ **必须**要求 SubAgent 返回摘要/结果
- ✅ **必须**明确告知 SubAgent 任务的最终目标

---

## 🧠 Memory MCP 强制使用规则（MUST FOLLOW）

### 📖 查询规则（何时必须查询）

#### 规则 1：集成/调试第三方服务前（MANDATORY）
**在以下场景必须先查询 Memory MCP**：
- ✅ 修改环境变量配置
- ✅ 调试服务连接/超时问题
- ✅ 集成新的第三方库
- ✅ 修改 API 调用方式
- ✅ 处理解析错误

**执行步骤**：
```bash
# 1. 查询相关 BUG
mcp__memory__search_nodes(query="{服务名} bug")

# 2. 查询核心 API（如果存在实体）
mcp__memory__open_nodes(names=["{服务名}"])

# 3. 使用 Context7 查询最新文档
mcp__context7__resolve-library-id(libraryName="{服务名}")
```

**例子**：
- 调试 MinerU 超时 → 查询 "MinerU timeout bug"
- 配置 LightRAG → 查询 "LightRAG environment bug"
- 修改 embedding 模型 → 查询 "embedding dimension bug"

#### 规则 2：遇到特定错误模式时（MANDATORY）
**错误关键词映射表**：

| 错误特征 | 查询命令 | 相关 BUG |
|---------|---------|---------|
| 超时（timeout, connection） | `search_nodes(query="timeout HTTP")` | BUG-6 |
| 文件未找到（not found, missing） | `search_nodes(query="file volume")` | BUG-5, BUG-9 |
| 认证失败（401, unauthorized） | `search_nodes(query="environment variable")` | BUG-2 |
| 状态卡住（pending, processing） | `search_nodes(query="batch status")` | BUG-7 |
| 维度错误（dimension, vector） | `search_nodes(query="embedding dimension")` | BUG-1 |
| 模式问题（local, remote） | `search_nodes(query="MINERU_MODE")` | BUG-3 |
| 命令失败（command not found） | `search_nodes(query="subprocess CLI")` | BUG-4 |
| 数据缺失（missing field） | `search_nodes(query="API response")` | BUG-8 |
| ZIP 解析失败（content_list） | `search_nodes(query="content_list filename")` | BUG-9 |
| 参考资料异常（Document Title One） | `search_nodes(query="Document Title reference")` | BUG-13 |

**流程**：
1. 遇到错误 → 提取关键词 → 查询 Memory
2. 如果找到相关 BUG → 应用历史修复方案
3. 如果未找到 → 调试完成后记录新 BUG

#### 规则 3：Git Commit 前（MANDATORY）
**在执行 `git commit` 前，必须查询**：
```bash
# 查询与本次修改相关的 BUG
mcp__memory__search_nodes(query="{修改涉及的关键词}")
```

**验证点**：
- [ ] 是否遵循了已知的修复模式
- [ ] 是否需要同步更新其他配置
- [ ] 是否有需要更新的记忆（见下文"更新规则"）

#### 规则 4：Docker/环境配置修改前（MANDATORY）
**修改以下文件前必须查询**：
- `docker-compose.yml` / `docker-compose.dev.yml`
- `.env` / `env.example`
- `Dockerfile` / `pyproject.toml`

**查询命令**：
```bash
mcp__memory__search_nodes(query="Docker volume environment")
mcp__memory__search_nodes(query="embedding dimension")
```

**验证点**：
- [ ] volume 挂载是否持久化（BUG-5）
- [ ] 环境变量命名是否正确（BUG-2）
- [ ] 是否需要删除 volume 重建（BUG-1）
- [ ] 生产/开发配置是否同步

---

### ✍️ 记录规则（何时必须记录）

#### 规则 1：解决新 BUG 后（MANDATORY）
**必须记录的条件（满足任一）**：
- ✅ 调试时间超过 30 分钟
- ✅ 根因不明显（需查源码/测试 API/查文档）
- ✅ 可能重复发生（配置错误、API 理解偏差）
- ✅ 影响生产环境（性能问题、服务中断）

**记录模板**：
```python
mcp__memory__create_entities(entities=[{
  "name": "BUG-{N}-{简短描述}",
  "entityType": "Bug",
  "observations": [
    "日期: YYYY-MM-DD",
    "问题: {现象描述}",
    "根因 1: {第一个根因}",
    "根因 2: {第二个根因}",
    "修复: {修复步骤}",
    "教训 1: {核心教训}",
    "教训 2: {次要教训}"
  ]
}])

mcp__memory__create_relations(relations=[{
  "from": "BUG-{N}-{简短描述}",
  "to": "{相关库/项目}",
  "relationType": "related_to"
}])
```

**记录要求**：
- ❌ 禁止冗长反思（超过 8 条 observations）
- ✅ 精简到核心（问题+根因+修复+教训）
- ✅ 使用关键词（方便未来查询）

#### 规则 2：发现第三方库的重要能力时（OPTIONAL）
**可选记录的场景**：
- 发现库的非显而易见能力（如 `MineruParser._read_output_files()`）
- 文档中难以找到的用法
- 可以避免重复造轮子的方法

**记录方式**：
```python
mcp__memory__add_observations(observations=[{
  "entityName": "{库名}",
  "contents": [
    "发现原生方法 {方法名}：{功能描述}",
    "签名: {方法签名}",
    "优势: {为什么应该用它}",
    "示例: {代码示例}"
  ]
}])
```

#### 规则 3：做出架构决策时（OPTIONAL）
**记录重大技术决策**：
```python
mcp__memory__create_entities(entities=[{
  "name": "{决策名称}",
  "entityType": "Architecture Decision",
  "observations": [
    "决策背景: {为什么需要决策}",
    "可选方案: {方案 A vs 方案 B}",
    "最终选择: {选了什么}",
    "理由: {为什么选这个}",
    "影响: {预期效果}"
  ]
}])
```

---

### 🔄 更新规则（何时必须更新）

#### 规则 1：每次 Git Commit 前必须检视记忆（MANDATORY）

**执行步骤**：
1. **查询相关记忆**：
   ```bash
   # 查询本次修改涉及的模块/服务
   mcp__memory__search_nodes(query="{修改关键词}")
   mcp__memory__open_nodes(names=["{相关实体}"])
   ```

2. **检视是否需要更新**：
   - ✅ 发现已有实体的新信息（如库的新方法、新配置参数）
   - ✅ 已有 BUG 的补充教训（如修复后发现新陷阱）
   - ✅ 架构决策的后续影响（如性能数据、生产验证结果）

3. **执行更新**：
   ```python
   # 方式 1：追加观察（observations）
   mcp__memory__add_observations(observations=[{
     "entityName": "{实体名}",
     "contents": [
       "新发现: {描述}",
       "补充: {内容}",
       "验证: {测试结果}"
     ]
   }])

   # 方式 2：更新关系
   mcp__memory__create_relations(relations=[{
     "from": "{实体A}",
     "to": "{实体B}",
     "relationType": "{关系类型}"
   }])
   ```

**更新示例**：

**场景 1：发现库的新方法**
```python
# 本次 commit 使用了 MineruParser._read_output_files()
# 检视：Memory 中 RAG-Anything 实体是否已记录此方法？
mcp__memory__open_nodes(names=["RAG-Anything"])

# 如果需要补充新发现
mcp__memory__add_observations(observations=[{
  "entityName": "RAG-Anything",
  "contents": [
    "实战验证: _read_output_files() 在生产环境成功处理 remote API ZIP（56 items，50秒）",
    "性能: vlm_mode=full 完整流程耗时 50 秒"
  ]
}])
```

**场景 2：BUG 修复后补充教训**
```python
# 本次 commit 修复了 BUG #9
# 检视：是否有新的教训需要补充？
mcp__memory__open_nodes(names=["BUG-9-MinerU-ContentList-Filename-Mismatch"])

# 补充新发现
mcp__memory__add_observations(observations=[{
  "entityName": "BUG-9-MinerU-ContentList-Filename-Mismatch",
  "contents": [
    "测试验证: 生产环境处理 56 items 成功，图片路径自动转换",
    "性能数据: vlm_mode=full 50秒 vs vlm_mode=off 2分钟"
  ]
}])
```

**场景 3：环境配置变更**
```python
# 本次 commit 修改了 .env 环境变量
# 检视：是否需要更新 BUG-2 的记忆？
mcp__memory__add_observations(observations=[{
  "entityName": "BUG-2-LightRAG-WebUI-ENV-Naming",
  "contents": [
    "生产验证: LLM_BINDING_* 环境变量配置正确，LightRAG WebUI 工作正常"
  ]
}])
```

#### 规则 2：发现已有记忆过时时（MANDATORY）

**触发条件**：
- ❌ 发现 Memory 中的信息已过时（如库升级后 API 变化）
- ❌ 发现记忆与实际不符（如配置说明错误）
- ❌ 发现更好的解决方案（如更高效的实现方式）

**处理方式**：
```python
# 方式 1：删除过时观察
mcp__memory__delete_observations(deletions=[{
  "entityName": "{实体名}",
  "observations": ["{过时的观察}"]
}])

# 方式 2：添加更正信息
mcp__memory__add_observations(observations=[{
  "entityName": "{实体名}",
  "contents": [
    "更正: {正确信息}",
    "原因: {为什么之前的信息不准确}"
  ]
}])
```

---

### ⚠️ 违反规则的后果

**不查询的后果**：
- 🔴 重复犯错（43 分钟宕机、文件丢失、超时）
- 🔴 浪费时间（30-60 分钟调试）
- 🔴 重复造轮子（不使用原生方法）

**不记录的后果**：
- 🔴 知识流失（团队/未来的自己重复遇到）
- 🔴 调试时间累积

**不更新的后果**：
- 🔴 记忆过时（库升级后信息不准确）
- 🔴 错过最佳实践（修复后的新发现未沉淀）
- 🔴 性能数据缺失（无法优化决策）

---

## 🚨 核心规则（严格执行）

### 0. 开始任何操作前（NEW）
- ✅ **必须先查询 Memory MCP**：`mcp__memory__search_nodes(query="{任务关键词}")`
- ✅ **验证是否有相关 BUG**：如果找到，应用历史修复方案
- ✅ **查看相关库 API**：`mcp__memory__open_nodes(names=["{库名}"])`
- ✅ **查询最新文档**（如需要）：使用 Context7 MCP

**查询规则详见**：[Memory MCP 强制使用规则](#-memory-mcp-强制使用规则must-follow)

### 1. 第三方库集成
- ✅ **必须查源码**：确认 API 签名、环境变量命名
- ✅ **优先使用原生能力**：不重新发明轮子（如 `MineruParser._read_output_files()`）
- ✅ **用 curl 测试 API**：先验证响应结构，再写解析代码
- ❌ **禁止猜测**：不猜测 API 参数、环境变量名、响应格式

#### curl 调用 API 的正确姿势（MANDATORY）
**❌ 错误做法**：在 `-d` 参数中直接使用多行 JSON + 命令替换
```bash
# ❌ 会报错: curl: option : blank argument where content is expected
curl -X POST "https://api.example.com/v1/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"model\": \"xxx\",
    \"messages\": [{
      \"content\": [{\"image_url\": {\"url\": \"data:image/png;base64,$(cat file.txt)\"}}]
    }]
  }"
```

**✅ 正确做法 1**：使用 jq 构建 JSON + 文件传递
```bash
# 1. 读取 base64 内容
base64_content=$(cat /tmp/image_base64.txt)

# 2. 使用 jq 构建 JSON（自动处理转义和格式）
jq -n \
  --arg model "deepseek-ai/DeepSeek-OCR" \
  --arg text "请转换表格" \
  --arg base64 "$base64_content" \
  '{
    model: $model,
    messages: [{
      role: "user",
      content: [
        {type: "text", text: $text},
        {type: "image_url", image_url: {url: ("data:image/png;base64," + $base64)}}
      ]
    }],
    max_tokens: 1000
  }' > /tmp/payload.json

# 3. 使用 @filename 传递 JSON（避免命令行长度限制）
curl -s -X POST "https://api.siliconflow.cn/v1/chat/completions" \
  -H "Authorization: Bearer $SF_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/payload.json | python3 -m json.tool
```

**✅ 正确做法 2**：使用单行 JSON（仅适用于简单情况）
```bash
# 仅当 JSON 简单且无命令替换时使用
curl -X POST "https://api.example.com" \
  -H "Content-Type: application/json" \
  -d '{"key":"value","foo":"bar"}'
```

**核心原则**：
- ❌ **禁止在 `-d` 参数中直接使用多行 JSON**：shell 换行符处理会导致解析失败
- ❌ **禁止在双引号内使用命令替换构建大型 JSON**：参数长度限制 + 转义复杂
- ✅ **必须使用 jq 构建 JSON**：自动处理转义、格式化、变量替换
- ✅ **必须使用 `@filename` 传递 JSON**：避免命令行长度限制
- ✅ **先验证 JSON 格式**：`jq . /tmp/payload.json` 确保格式正确
- 🈲 **不允许使用"python3 -m json.tool"**: 本地用的uv所以global没有安装Python以外的其他东西. 

### 2. Git Commit 前置检查
**必须完成以下检查**：
0. ✅ **Memory MCP 检视与更新（NEW）**：
   - 查询相关记忆：`mcp__memory__search_nodes(query="{本次改动关键词}")`
   - 检查是否需要更新：
     - 修复了已记录的 BUG → 补充验证结果和性能数据
     - 发现库新特性 → 添加到库实体的 observations
     - 优化了已有方案 → 更新原有记录
     - 解决新 BUG（调试 >30 分钟）→ 创建新 BUG 实体并记录
     - 修改了架构 → 添加到项目实体或更新关系
   - 执行更新命令：`mcp__memory__add_observations()` 或 `mcp__memory__create_entities()`
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

**远程服务器部署**：
- SSH 连接和服务器信息详见 [DEPLOYMENT_PRIVATE.md](./DEPLOYMENT_PRIVATE.md)（仅本地）
- 部署流程：PR 合并 → 服务器 `git pull` → 热重载生效（开发模式）

## Configuration (.env)

**核心配置**：
- **LLM**: `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL` (功能导向命名)
- **Embedding**: `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIM` (必须匹配模型)
- **Rerank**: `RERANK_API_KEY`, `RERANK_BASE_URL`, `RERANK_MODEL`
- **DeepSeek-OCR**: `DS_OCR_API_KEY`, `DS_OCR_BASE_URL`, `DS_OCR_MODEL` (独立配置)
- **MinerU**: `MINERU_MODE=remote`（推荐）+ `MINERU_API_TOKEN` + `MINERU_HTTP_TIMEOUT=60`
- **存储**: DragonflyDB (KV) + Qdrant (Vector) + Memgraph (Graph)
- **性能**: `TOP_K=20`, `CHUNK_TOP_K=10`, `MAX_ASYNC=16`, `LLM_TIMEOUT=60`

**多租户 API**：
- 所有端点需 `?tenant_id=xxx` 参数
- 支持租户级配置热重载（无需重启服务）
- 租户配置 API: `/tenants/{id}/config` (GET/PUT/DELETE/refresh)
- 存储方式可配置：
  - `TENANT_CONFIG_STORAGE=local` - 本地文件存储（默认，适合开发/测试）
  - `TENANT_CONFIG_STORAGE=redis` - Redis 存储（生产环境）
- **注意**：租户配置不会降级到全局配置，避免 API key 混用

## File Structure
- `main.py`: FastAPI 入口
- `api/`: 路由模块 (insert, query, task, tenant, tenant_config, files, monitor)
- `src/`: 核心逻辑 (rag, multi_tenant, tenant_config, config, mineru_client, logger, metrics)
- `rag_local_storage/`: LightRAG 工作目录（git-ignored）
- `test_tenant_config.sh`: 租户配置热重载测试脚本

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
