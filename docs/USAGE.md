# RAG API 使用文档

完整的 API 使用指南，包括详细的配置、API 接口说明和故障排除。

## 目录

- [环境配置](#环境配置)
- [API 接口详解](#api-接口详解)
- [检索模式说明](#检索模式说明)
- [安全特性](#安全特性)
- [技术架构](#技术架构)
- [故障排除](#故障排除)
- [性能优化](#性能优化)

---

## 环境配置

### 环境变量

创建 `.env` 文件：

```bash
# LLM API 配置
ARK_API_KEY=your_ark_api_key
ARK_BASE_URL=your_ark_base_url

# Embedding API 配置
SF_API_KEY=your_sf_api_key
SF_BASE_URL=your_sf_base_url
```

### 安装依赖

```bash
# 使用 uv 安装
uv sync

# 如果遇到网络超时
UV_HTTP_TIMEOUT=120 uv sync
```

### 首次启动

```bash
# 清理旧数据（避免版本兼容问题）
rm -rf ./rag_local_storage

# 启动服务
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# 后台运行
nohup uv run uvicorn main:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
```

---

## API 接口详解

### 1. 文档上传 `/insert`

**端点：** `POST /insert`

**参数：**
- `doc_id` (query, required): 文档唯一标识
- `file` (body, required): 上传的文件

**支持的文件格式：**
- 文档：PDF, DOCX, TXT
- 图片：PNG, JPG, JPEG
- 其他：根据 RAG-Anything 支持的格式

**请求示例：**

```bash
# 使用 curl
curl -X POST "http://localhost:8000/insert?doc_id=research_paper" \
  -F "file=@document.pdf"

# 使用 Python requests
import requests

with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/insert",
        params={"doc_id": "doc_001"},
        files={"file": f}
    )
print(response.json())
```

**成功响应：**

```json
{
  "message": "Document processed successfully",
  "doc_id": "research_paper",
  "filename": "document.pdf"
}
```

**错误响应：**

- `400 Bad Request`: 空文件、文件过大、不支持的格式
- `500 Internal Server Error`: 服务器内部错误
- `503 Service Unavailable`: RAG 服务未就绪

**错误示例：**

```json
// 空文件
{
  "detail": "Invalid document: Empty file: document.pdf"
}

// 文件过大
{
  "detail": "Invalid document: File too large: document.pdf (120000000 bytes, max: 104857600 bytes)"
}

// 不支持的格式
{
  "detail": "Unsupported file format: document.xyz"
}
```

---

### 2. 智能查询 `/query`

**端点：** `POST /query`

**请求体：**

```json
{
  "query": "你的问题",
  "mode": "mix"
}
```

**参数说明：**
- `query` (required): 查询问题
- `mode` (optional): 检索模式，默认 "mix"
  - `local`: 聚焦上下文相关信息
  - `global`: 利用全局知识
  - `hybrid`: 结合 local 和 global
  - `mix`: 整合知识图谱和向量检索（推荐）
  - `naive`: 基础搜索

**请求示例：**

```bash
# 使用 curl
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是人工智能？", "mode": "mix"}'

# 使用 Python requests
import requests

response = requests.post(
    "http://localhost:8000/query",
    json={
        "query": "什么是人工智能？",
        "mode": "mix"
    }
)
print(response.json())
```

**成功响应：**

```json
{
  "answer": "人工智能（AI）是计算机科学的一个分支...\n\n### References\n\n- [1] research_paper.pdf"
}
```

---

### 3. 健康检查 `/`

**端点：** `GET /`

**响应：**

```json
{
  "status": "RAG API is running"
}
```

---

## 检索模式说明

### Local Mode
- **特点：** 聚焦于查询的局部上下文
- **适用：** 需要精确定位特定段落
- **示例：** "这段话在哪一页？"

### Global Mode
- **特点：** 利用整个知识库的全局信息
- **适用：** 需要综合多个文档的信息
- **示例：** "总结所有文档的主要观点"

### Hybrid Mode
- **特点：** 结合 Local 和 Global 的优势
- **适用：** 平衡局部精确性和全局完整性
- **示例：** "比较不同文档中的数据"

### Mix Mode（推荐）
- **特点：** 整合知识图谱和向量检索
- **适用：** 大多数场景的最佳选择
- **示例：** 任何复杂查询

### Naive Mode
- **特点：** 简单的向量相似度搜索
- **适用：** 快速原型验证
- **示例：** 简单的关键词匹配

**性能对比：**

| 模式 | 准确性 | 速度 | 复杂度 | 推荐度 |
|------|--------|------|--------|--------|
| local | ⭐⭐⭐ | ⭐⭐⭐⭐ | 低 | ⭐⭐⭐ |
| global | ⭐⭐⭐⭐ | ⭐⭐⭐ | 中 | ⭐⭐⭐⭐ |
| hybrid | ⭐⭐⭐⭐ | ⭐⭐⭐ | 中 | ⭐⭐⭐⭐ |
| mix | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 高 | ⭐⭐⭐⭐⭐ |
| naive | ⭐⭐ | ⭐⭐⭐⭐⭐ | 低 | ⭐⭐ |

---

## 安全特性

### 1. 路径遍历攻击防护

**实现机制：**
```python
# 用户上传 ../../etc/passwd
# 实际保存为 /tmp/uuid-random.txt
```

**防护措施：**
- UUID 生成唯一文件名
- `os.path.basename()` 提取纯文件名
- 扩展名验证（只允许字母数字）

### 2. 文件验证

**检查项：**
- 空文件检测（0 字节）
- 文件大小限制（100MB）
- 扩展名验证

### 3. 错误处理层次

**客户端错误（400）：**
- 空文件
- 文件过大
- 不支持的格式
- 解析失败

**服务器错误（500）：**
- 内部处理错误
- 文件系统错误
- 未预期的异常

---

## 技术架构

### 核心组件

```
┌─────────────────────────────────────────┐
│          FastAPI Application            │
│  ┌──────────────────────────────────┐  │
│  │      Lifespan Management         │  │
│  │  ┌────────────────────────────┐  │  │
│  │  │   RAGAnything Instance     │  │  │
│  │  │                            │  │  │
│  │  │  ┌──────────────────────┐  │  │  │
│  │  │  │   LightRAG Engine    │  │  │  │
│  │  │  │  ┌────────────────┐  │  │  │  │
│  │  │  │  │ Vector Store   │  │  │  │  │
│  │  │  │  │ Knowledge Graph│  │  │  │  │
│  │  │  │  └────────────────┘  │  │  │  │
│  │  │  └──────────────────────┘  │  │  │
│  │  │                            │  │  │
│  │  │  VLM, Embedding, LLM      │  │  │
│  │  └────────────────────────────┘  │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

### 依赖关系

- **RAG-Anything 1.2.8**
  - 多模态文档解析
  - VLM 视觉理解
  - 内容分类和路由

- **LightRAG 1.4.9.2**
  - 知识图谱构建
  - 向量存储
  - 混合检索

### Embedding 模型

- **模型**: Qwen/Qwen3-Embedding-8B
- **维度**: 4096
- **用途**: 文档向量化、查询向量化

### LLM 模型

- **模型**: seed-1-6-250615
- **用途**: 
  - 文本生成
  - VLM 视觉理解
  - 知识图谱推理

---

## 故障排除

### 问题 1: multimodal_processed 错误

**症状：**
```
DocProcessingStatus.__init__() got an unexpected keyword argument 'multimodal_processed'
```

**原因：** 旧版本数据与新版本不兼容

**解决方案：**
```bash
rm -rf ./rag_local_storage
```

---

### 问题 2: Embedding 维度不匹配

**症状：**
```
shapes (0,3072) and (4096,) not aligned
```

**原因：** embedding_dim 配置错误

**解决方案：**

检查 `src/rag.py`:
```python
embedding_func = EmbeddingFunc(
    embedding_dim=4096,  # 必须是 4096
    ...
)
```

---

### 问题 3: 查询返回空结果

**症状：** 查询没有返回任何结果

**可能原因：**
1. LightRAG 未初始化
2. 文档未成功处理
3. 查询关键词不匹配

**解决方案：**

1. 确认 LightRAG 初始化：
```python
# src/rag.py
await rag_instance._ensure_lightrag_initialized()
```

2. 检查文档处理日志：
```bash
# 查看服务器日志
tail -f server.log
```

3. 尝试不同的查询模式：
```bash
# 尝试 naive 模式
curl -X POST "http://localhost:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "测试查询", "mode": "naive"}'
```

---

### 问题 4: 文件上传失败

**症状：** 上传返回 400 或 500 错误

**检查清单：**

1. **文件大小**
```bash
# 检查文件大小
ls -lh document.pdf
# 确保 < 100MB
```

2. **文件格式**
```bash
# 检查文件类型
file document.pdf
```

3. **服务器日志**
```bash
# 查看详细错误
tail -50 server.log
```

---

### 问题 5: 服务启动失败

**症状：** uvicorn 无法启动

**检查步骤：**

1. **环境变量**
```bash
# 检查 .env 文件
cat .env
```

2. **端口占用**
```bash
# 检查端口 8000
lsof -i :8000

# 杀死占用进程
kill -9 <PID>
```

3. **依赖安装**
```bash
# 重新安装依赖
uv sync --reinstall
```

---

## 性能优化

### 1. 并发处理

**当前配置：**
- 单文件处理
- 异步查询

**优化建议：**
```python
# 如需批量处理，使用
await rag.process_folder_complete(
    folder_path="./docs",
    max_workers=4  # 并发数
)
```

### 2. 缓存策略

**LLM 缓存：**
- 自动缓存 LLM 响应
- 相同查询直接返回

**查看缓存命中：**
```bash
# 查看日志中的 cache hit
grep "cache hit" server.log
```

### 3. 内存管理

**文件大小限制：**
```python
# main.py
max_file_size = 100 * 1024 * 1024  # 100MB

# 根据服务器内存调整
max_file_size = 200 * 1024 * 1024  # 200MB
```

### 4. 日志级别

**生产环境：**
```python
# main.py
logging.basicConfig(level=logging.WARNING)  # 减少日志
```

**开发环境：**
```python
logging.basicConfig(level=logging.INFO)  # 详细日志
```

---

## 监控建议

### 关键指标

1. **响应时间**
   - 文档上传: < 30s
   - 查询响应: < 5s

2. **成功率**
   - 文档处理: > 95%
   - 查询成功: > 99%

3. **资源使用**
   - CPU: < 80%
   - 内存: < 4GB
   - 磁盘: 根据文档量

### 日志监控

```bash
# 错误统计
grep "ERROR" server.log | wc -l

# 处理时间统计
grep "processed successfully" server.log

# 查询统计
grep "Query result" server.log | wc -l
```

---

## 部署建议

### 生产环境

```bash
# 使用 gunicorn + uvicorn
gunicorn main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile logs/access.log \
  --error-logfile logs/error.log
```

### Docker 部署

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制项目文件
COPY . .

# 安装依赖
RUN uv sync

# 暴露端口
EXPOSE 8000

# 启动服务
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 更多资源

- [技术改进说明](IMPROVEMENTS.md) - 安全性和错误处理详解
- [可选功能清单](OPTIONAL_ENHANCEMENTS.md) - 高级功能参考
- [RAG-Anything 文档](https://github.com/hkuds/rag-anything)
- [LightRAG 文档](https://github.com/hkuds/lightrag)

---

© 2025 RAG API Project

