# RAG API 使用文档

完整的 API 使用指南，包括详细的配置、API 接口说明和故障排除。

## 目录

- [多租户架构](#多租户架构)
- [环境配置](#环境配置)
- [API 接口详解](#api-接口详解)
- [租户管理 API](#租户管理-api)
- [检索模式说明](#检索模式说明)
- [安全特性](#安全特性)
- [技术架构](#技术架构)
- [故障排除](#故障排除)
- [性能优化](#性能优化)

---

## 多租户架构

**重要**: RAG API 采用多租户架构,**所有 API 端点都需要提供 `tenant_id` 参数**。

### 核心概念

- **完全隔离**: 每个租户的文档和查询完全隔离,互不影响
- **Workspace 隔离**: 基于 LightRAG 的 workspace 机制实现命名空间隔离
- **实例池管理**: LRU 缓存策略,最多缓存 50 个租户实例
- **按需创建**: 首次请求时创建租户实例,后续请求复用缓存实例

### tenant_id 格式要求

- **长度**: 3-50 个字符
- **允许字符**: 字母、数字、下划线(_)、连字符(-)
- **示例**: `tenant_a`, `company_123`, `user-abc`

### 使用示例

```bash
# 租户 A 上传文档
curl -X POST "http://localhost:8000/insert?tenant_id=tenant_a&doc_id=doc_001" \
  -F "file=@document.pdf"

# 租户 A 查询(仅访问 tenant_a 的知识图谱)
curl -X POST "http://localhost:8000/query?tenant_id=tenant_a" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是人工智能?", "mode": "naive"}'

# 租户 B 上传文档(完全隔离)
curl -X POST "http://localhost:8000/insert?tenant_id=tenant_b&doc_id=doc_001" \
  -F "file=@report.docx"

# 租户 B 查询(仅访问 tenant_b 的知识图谱)
curl -X POST "http://localhost:8000/query?tenant_id=tenant_b" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是人工智能?", "mode": "naive"}'
```

**关键点**:
- tenant_a 和 tenant_b 的数据完全隔离
- 相同的 doc_id 可以在不同租户间使用
- 查询结果仅来自当前租户的知识图谱

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
- `tenant_id` (query, **required**): 租户 ID
- `doc_id` (query, required): 文档唯一标识
- `file` (body, required): 上传的文件
- `parser` (query, optional): 解析器选择(`auto`, `mineru`, `docling`),默认 `auto`

**支持的文件格式：**
- 文档：PDF, DOCX, TXT, MD
- 图片：PNG, JPG, JPEG
- 其他：根据 RAG-Anything 支持的格式

**请求示例：**

```bash
# 使用 curl
curl -X POST "http://localhost:8000/insert?tenant_id=tenant_a&doc_id=research_paper" \
  -F "file=@document.pdf"

# 指定解析器
curl -X POST "http://localhost:8000/insert?tenant_id=tenant_a&doc_id=doc_002&parser=mineru" \
  -F "file=@complex_document.pdf"

# 使用 Python requests
import requests

with open("document.pdf", "rb") as f:
    response = requests.post(
        "http://localhost:8000/insert",
        params={
            "tenant_id": "tenant_a",
            "doc_id": "doc_001"
        },
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

**参数：**
- `tenant_id` (query, **required**): 租户 ID

**请求体：**

```json
{
  "query": "你的问题",
  "mode": "naive"
}
```

**参数说明：**
- `query` (required): 查询问题
- `mode` (optional): 检索模式，默认 "naive"
  - `naive`: 向量检索（最快，推荐）
  - `local`: 聚焦上下文相关信息
  - `global`: 利用全局知识
  - `hybrid`: 结合 local 和 global
  - `mix`: 整合知识图谱和向量检索

**请求示例：**

```bash
# 使用 curl
curl -X POST "http://localhost:8000/query?tenant_id=tenant_a" \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是人工智能？", "mode": "naive"}'

# 使用 Python requests
import requests

response = requests.post(
    "http://localhost:8000/query",
    params={"tenant_id": "tenant_a"},
    json={
        "query": "什么是人工智能？",
        "mode": "naive"
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

## 租户管理 API

### 1. 获取租户统计信息

**端点：** `GET /tenants/stats`

**参数：**
- `tenant_id` (query, **required**): 租户 ID

**响应：**

```json
{
  "tenant_id": "tenant_a",
  "tasks": {
    "total": 10,
    "completed": 8,
    "failed": 1,
    "processing": 1,
    "pending": 0
  },
  "instance_cached": true
}
```

**请求示例：**

```bash
# 查看租户统计信息
curl "http://localhost:8000/tenants/stats?tenant_id=tenant_a"
```

---

### 2. 清理租户缓存

**端点：** `DELETE /tenants/cache`

**参数：**
- `tenant_id` (query, **required**): 租户 ID

**响应：**

```json
{
  "tenant_id": "tenant_a",
  "message": "Tenant cache cleared successfully"
}
```

**请求示例：**

```bash
# 手动清理租户实例缓存（释放内存）
curl -X DELETE "http://localhost:8000/tenants/cache?tenant_id=tenant_a"
```

**使用场景：**
- 长时间未使用的租户，手动清理释放内存
- 租户数据迁移后，清理旧实例
- 调试和测试

---

### 3. 获取实例池统计信息（管理员）

**端点：** `GET /tenants/pool/stats`

**无需 tenant_id**（管理员端点）

**响应：**

```json
{
  "total_instances": 3,
  "max_instances": 50,
  "tenants": ["tenant_a", "tenant_b", "tenant_c"]
}
```

**请求示例：**

```bash
# 查看实例池状态
curl "http://localhost:8000/tenants/pool/stats"
```

**使用场景：**
- 监控实例池状态
- 查看活跃租户列表
- 容量规划

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

### 核心组件（多租户模式）

```
┌──────────────────────────────────────────────────┐
│          FastAPI Application                     │
│  ┌────────────────────────────────────────────┐  │
│  │      Lifespan Management                   │  │
│  │  ┌──────────────────────────────────────┐  │  │
│  │  │   MultiTenantRAGManager              │  │  │
│  │  │   (LRU 缓存池，max 50 实例)           │  │  │
│  │  │                                      │  │  │
│  │  │  tenant_a → LightRAG(workspace=a)   │  │  │
│  │  │  tenant_b → LightRAG(workspace=b)   │  │  │
│  │  │  tenant_c → LightRAG(workspace=c)   │  │  │
│  │  │  ...                                 │  │  │
│  │  │                                      │  │  │
│  │  │  共享资源：                           │  │  │
│  │  │  - LLM 函数                          │  │  │
│  │  │  - Embedding 函数                    │  │  │
│  │  │  - Rerank 函数                       │  │  │
│  │  └──────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────┘
                     ↓
        ┌────────────────────────────┐
        │  外部存储（租户隔离）         │
        ├────────────────────────────┤
        │ Redis: tenant_a:*, b:*, .. │
        │ PostgreSQL: tenant_a:*, .. │
        │ Neo4j: tenant_a:*, b:*, .. │
        └────────────────────────────┘
```

### 依赖关系

- **LightRAG 1.4.9.4**
  - 知识图谱构建
  - 向量存储
  - 混合检索
  - **Workspace 隔离支持**

- **RAG-Anything**
  - 多模态文档解析
  - VLM 视觉理解
  - 内容分类和路由

### AI 模型

#### Embedding 模型
- **模型**: Qwen/Qwen3-Embedding-8B
- **维度**: 4096
- **用途**: 文档向量化、查询向量化

#### LLM 模型
- **模型**: seed-1-6-250615（豆包/火山引擎）
- **用途**:
  - 实体提取
  - 关系提取
  - 答案生成

#### Rerank 模型
- **模型**: Qwen/Qwen3-Reranker-8B
- **用途**: 检索结果重排序，提升相关性

#### Vision 模型
- **模型**: seed-1-6-250615（复用 LLM）
- **用途**: 图片描述、多模态理解

### 多租户架构特点

1. **完全隔离**: 基于 workspace 的命名空间隔离
2. **实例池管理**: LRU 缓存，最多 50 个实例
3. **按需创建**: 首次请求创建，后续复用
4. **共享资源**: LLM/Embedding 函数在租户间共享
5. **自动驱逐**: 超过限制时自动移除最旧实例

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

