# RAG API

基于 RAG-Anything 和 LightRAG 的多模态文档检索增强生成 API。

## 特性

- ✅ **多模态文档处理**：PDF、DOCX、图片等
- ✅ **VLM 增强**：自动处理图片、表格、公式
- ✅ **智能检索**：支持 local、global、hybrid、mix 等模式
- ✅ **安全可靠**：UUID 文件名、精细化错误处理
- ✅ **异步处理**：高性能文档处理和查询

## 快速开始

### 1. 环境配置

创建 `.env` 文件：

```bash
ARK_API_KEY=your_ark_api_key
ARK_BASE_URL=your_ark_base_url
SF_API_KEY=your_sf_api_key
SF_BASE_URL=your_sf_base_url
```

### 2. 安装依赖

```bash
uv sync
```

### 3. 启动服务

```bash
# 首次启动前清理旧数据
rm -rf ./rag_local_storage

# 启动服务
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. 访问 API

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## API 端点

### 上传文档

```bash
curl -X POST "http://localhost:8000/insert?doc_id=my_doc" \
  -F "file=@document.pdf"
```

### 查询

```bash
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是人工智能？", "mode": "mix"}'
```

### 健康检查

```bash
curl http://localhost:8000/
```

## 项目结构

```
rag-api/
├── main.py              # FastAPI 应用主入口
├── src/
│   └── rag.py          # RAG 实例管理
├── docs/               # 📚 文档
│   ├── USAGE.md        # 详细使用文档
│   ├── IMPROVEMENTS.md # 技术改进说明
│   ├── OPTIONAL_ENHANCEMENTS.md  # 可选功能
│   └── PROJECT_STRUCTURE.md      # 项目结构说明
├── scripts/            # 🔧 工具脚本
│   └── test_api.py     # API 测试脚本
└── pyproject.toml      # 项目配置
```

详见 [项目结构说明](docs/PROJECT_STRUCTURE.md)

## 文档

- [详细使用文档](docs/USAGE.md) - API 使用、配置、故障排除
- [技术改进说明](docs/IMPROVEMENTS.md) - 安全性、错误处理改进
- [可选功能清单](docs/OPTIONAL_ENHANCEMENTS.md) - 高级功能参考

## 测试

```bash
# 运行测试脚本
uv run python scripts/test_api.py
```

## 技术栈

- **FastAPI** - Web 框架
- **RAG-Anything 1.2.8** - 多模态文档处理
- **LightRAG 1.4.9.2** - RAG 引擎
- **UV** - 包管理器

## 故障排除

### multimodal_processed 错误

```bash
rm -rf ./rag_local_storage
```

### Embedding 维度不匹配

确认 `src/rag.py` 中 `embedding_dim=4096`

详见 [使用文档](docs/USAGE.md#故障排除)

## 许可证

本项目仅供学习和内部使用。

---

© 2025 RAG API Project
