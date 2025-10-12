# 项目结构说明

## 目录结构

```
rag-api/
├── main.py                 # FastAPI 应用主入口
├── pyproject.toml         # 项目配置和依赖
├── .env                   # 环境变量（不提交到 Git）
├── .gitignore            # Git 忽略文件配置
│
├── src/                  # 源代码
│   └── rag.py           # RAG 实例管理和生命周期
│
├── docs/                 # 文档
│   ├── USAGE.md         # 详细使用文档
│   ├── IMPROVEMENTS.md  # 技术改进说明
│   ├── OPTIONAL_ENHANCEMENTS.md  # 可选功能清单
│   └── PROJECT_STRUCTURE.md      # 本文件
│
├── scripts/             # 脚本工具
│   └── test_api.py     # API 测试脚本
│
├── rag_local_storage/  # RAG 数据存储（自动生成，不提交）
│   ├── vdb_*.json      # 向量数据库
│   ├── *.graphml       # 知识图谱
│   └── *.json          # 文档状态和缓存
│
└── output/             # 解析输出（自动生成，不提交）
    └── */              # 各文档的解析结果
```

## 文件说明

### 核心文件

#### `main.py`
- FastAPI 应用主文件
- 定义 API 端点：`/insert`, `/query`, `/`
- 实现文件上传、文档处理、查询功能
- 包含完整的错误处理和安全验证

**关键功能：**
- UUID 文件名生成（防路径遍历）
- 文件验证（空文件、大小限制）
- 分层错误处理（400/500 区分）
- MinerU 错误特殊处理

#### `src/rag.py`
- RAG 实例管理
- FastAPI lifespan 生命周期管理
- LLM、Embedding、Vision 模型配置
- 全局实例获取函数

**关键配置：**
- `embedding_dim=4096` (Qwen3-Embedding-8B)
- 显式 LightRAG 初始化
- 多模态处理启用

### 配置文件

#### `pyproject.toml`
```toml
[project]
name = "rag-api"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "raganything[all]>=1.2.8",
]
```

#### `.env` (需要创建)
```bash
ARK_API_KEY=your_ark_api_key
ARK_BASE_URL=your_ark_base_url
SF_API_KEY=your_sf_api_key
SF_BASE_URL=your_sf_base_url
```

### 文档文件

#### `docs/USAGE.md`
- 完整的使用指南
- API 接口详解
- 配置说明
- 故障排除
- 性能优化

#### `docs/IMPROVEMENTS.md`
- 安全性改进详解
- 错误处理优化
- 文件验证机制
- 防御性编程实践

#### `docs/OPTIONAL_ENHANCEMENTS.md`
- 可选功能清单
- 高级 API 端点
- 扩展功能参考

### 工具脚本

#### `scripts/test_api.py`
- 完整的 API 测试
- 功能验证
- 安全性测试
- 性能测试

**测试覆盖：**
- 正常文件上传
- 路径遍历攻击防护
- 空文件处理
- 查询功能

## 数据流

### 文档上传流程

```
用户上传文件
    ↓
POST /insert
    ↓
文件保存（UUID 文件名）
    ↓
文件验证（大小、空文件）
    ↓
RAG-Anything 处理
    ├→ MinerU 解析
    ├→ 内容分离（文本/多模态）
    ├→ VLM 处理（图片、表格、公式）
    └→ LightRAG 存储
        ├→ 向量数据库
        └→ 知识图谱
    ↓
返回成功响应
```

### 查询流程

```
用户查询
    ↓
POST /query
    ↓
RAG-Anything 查询
    ├→ 向量检索
    ├→ 图谱遍历
    ├→ VLM 增强（如有图片）
    └→ LLM 生成答案
    ↓
返回答案和引用
```

## 依赖关系

```
FastAPI Application
    │
    ├─> RAGAnything (1.2.8)
    │       │
    │       ├─> LightRAG (1.4.9.2)
    │       │       ├─> Vector Store
    │       │       └─> Knowledge Graph
    │       │
    │       └─> MinerU Parser
    │
    ├─> LLM Models
    │       ├─> seed-1-6-250615 (Text)
    │       └─> seed-1-6-250615 (Vision)
    │
    └─> Embedding
            └─> Qwen3-Embedding-8B (4096d)
```

## 存储说明

### `rag_local_storage/`

自动生成的 RAG 数据存储目录：

- `vdb_entities.json` - 实体向量数据库
- `vdb_relationships.json` - 关系向量数据库  
- `vdb_chunks.json` - 文本块向量数据库
- `graph_chunk_entity_relation.graphml` - 知识图谱
- `kv_store_*.json` - 文档、缓存等键值存储
- `doc_status.json` - 文档处理状态

**注意：** 
- 首次启动前删除此目录（避免版本兼容问题）
- 不要提交到 Git（已在 .gitignore）
- 大小随文档量增长

### `output/`

MinerU 解析的临时输出：

- 每个文档一个子目录
- 包含解析的图片、表格、公式
- 中间格式文件

**注意：**
- 可以定期清理
- 不要提交到 Git

## 开发工作流

### 1. 初始化开发环境

```bash
# 克隆项目
git clone <repository>
cd rag-api

# 创建 .env 文件
cp .env.example .env  # 如果有示例文件
# 或手动创建并填写 API 密钥

# 安装依赖
uv sync

# 清理旧数据
rm -rf ./rag_local_storage
```

### 2. 启动开发服务器

```bash
# 开发模式（自动重载）
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 查看日志
tail -f server.log
```

### 3. 测试

```bash
# 运行完整测试
uv run python scripts/test_api.py

# 手动测试上传
curl -X POST "http://localhost:8000/insert?doc_id=test" \
  -F "file=@test.pdf"

# 手动测试查询
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "测试查询", "mode": "mix"}'
```

### 4. 代码修改

```bash
# 修改 API 端点
# 编辑 main.py

# 修改 RAG 配置
# 编辑 src/rag.py

# 检查代码
uv run python -m py_compile main.py src/rag.py
```

### 5. 部署

```bash
# 生产模式
uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# 或使用 gunicorn
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

## 常见问题

### Q: 为什么 `rag_local_storage/` 很大？
**A:** 向量数据库和知识图谱随文档量增长。定期清理不需要的文档。

### Q: 可以删除 `output/` 吗？
**A:** 可以。这是临时解析输出，删除后不影响查询功能。

### Q: 如何备份知识库？
**A:** 备份整个 `rag_local_storage/` 目录。

### Q: 如何迁移到新服务器？
**A:** 
1. 复制项目文件
2. 复制 `.env` 文件
3. 复制 `rag_local_storage/` 目录
4. 运行 `uv sync`
5. 启动服务

---

© 2025 RAG API Project

