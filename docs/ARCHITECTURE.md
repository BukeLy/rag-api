# RAG API 架构设计文档

**版本**: 2.0  
**更新日期**: 2025-10-16  
**架构**: 单一 LightRAG + 多解析器

---

## 架构概述

RAG API 采用**单一 LightRAG 实例 + 多解析器**架构，实现读写分离和性能优化。

### 核心设计理念

1. **知识图谱中心化**：单一 LightRAG 实例作为核心
2. **职责分离**：插入用解析器，查询直接访问
3. **智能路由**：根据文件类型选择最优解析器
4. **资源优化**：95% 查询无需多模态能力

---

## 架构图

### 整体架构

```
                    FastAPI 应用层
                          ↓
        ┌─────────────────┴─────────────────┐
        ↓                                   ↓
    插入端点 (/insert)                  查询端点 (/query)
        ↓                                   ↓
    文件类型检测                      直接访问 LightRAG
        ↓                                   ↓
  ┌─────┴─────┐                    单一 LightRAG 实例
  ↓           ↓                     （知识图谱核心）
纯文本      复杂文档
  ↓           ↓
LightRAG   解析器选择
直接插入   ↓     ↓
        MinerU  Docling
          ↓     ↓
          LightRAG（共享）
```

### 数据流

#### 插入流程（文档 → 知识图谱）

```
用户上传文件
    ↓
文件类型判断
    ↓
┌────────────────────────────────┐
│ 纯文本 (.txt, .md)             │
│   → 直接读取                    │
│   → LightRAG.ainsert()          │ 极快（~1秒）
│   → 知识图谱                    │
└────────────────────────────────┘
    ↓（其他格式）
┌────────────────────────────────┐
│ 简单文档 (< 500KB PDF/Office)  │
│   → Docling 解析器              │ 快（~5-10秒）
│   → 转 Markdown                 │
│   → LightRAG.ainsert()          │
│   → 知识图谱                    │
└────────────────────────────────┘
    ↓（其他格式）
┌────────────────────────────────┐
│ 复杂文档（图片、大文件）         │
│   → MinerU 解析器               │ 强大（支持多模态）
│   → 提取图片/表格/公式           │
│   → 转 Markdown                 │
│   → LightRAG.ainsert()          │
│   → 知识图谱                    │
└────────────────────────────────┘
```

#### 查询流程（问题 → 答案）

```
用户查询
    ↓
直接访问 LightRAG
（绕过解析器）
    ↓
┌────────────────────┐
│ QueryParam 配置    │
│ - mode: naive/...  │
│ - top_k: 20        │
│ - enable_rerank    │
└────────────────────┘
    ↓
知识图谱检索
    ↓
┌─ Naive 模式 ────┐
│ 向量相似度检索   │ 最快（10-20秒）
└─────────────────┘
┌─ Local 模式 ────┐
│ 局部知识图谱     │ 精确（20-40秒）
└─────────────────┘
┌─ Global 模式 ───┐
│ 全局知识图谱     │ 完整（30-60秒）
└─────────────────┘
    ↓
Rerank 重排序（可选）
    ↓
LLM 生成答案
    ↓
返回结果
```

---

## 核心组件

### 1. LightRAG 实例（单例）

**定义位置**: `src/rag.py`

```python
global_lightrag_instance = LightRAG(
    working_dir="./rag_local_storage",
    llm_model_func=llm_model_func,
    embedding_func=embedding_func,
    llm_model_max_async=8,  # 并发优化
)
```

**职责**：
- 知识图谱存储和管理
- 向量检索
- 实体和关系提取
- 知识图谱查询

**共享方式**：
- MinerU 解析器通过 `lightrag` 参数传入
- Docling 解析器通过 `lightrag` 参数传入
- 查询通过 `get_lightrag_instance()` 直接访问

### 2. MinerU 解析器

**配置**: `src/rag.py`

```python
rag_instance_mineru = RAGAnything(
    config=RAGAnythingConfig(
        parser="mineru",
        enable_image_processing=True,
        enable_table_processing=True,
        enable_equation_processing=True,
    ),
    lightrag=global_lightrag_instance,  # 共享 LightRAG
    vision_model_func=vision_model_func,
)
```

**特点**：
- 强大的多模态解析能力
- 支持图片、表格、公式
- OCR 能力优秀
- 适合复杂文档

**使用场景**：
- 大文件（> 500KB）
- 图片文件
- 包含表格/公式的文档
- 手写文档

### 3. Docling 解析器

**配置**: `src/rag.py`

```python
rag_instance_docling = RAGAnything(
    config=RAGAnythingConfig(
        parser="docling",
        enable_image_processing=False,
        enable_table_processing=False,
        enable_equation_processing=False,
    ),
    lightrag=global_lightrag_instance,  # 共享 LightRAG
    vision_model_func=vision_model_func,
)
```

**特点**：
- 轻量级 Python 解析器
- 快速处理
- 资源占用低
- 不支持多模态

**使用场景**：
- 小文件（< 500KB）
- 纯文本 PDF
- Office 文档（DOCX、XLSX）

### 4. 智能路由

**实现位置**: `src/rag.py` - `select_parser_by_file()`

```python
def select_parser_by_file(filename: str, file_size: int) -> str:
    ext = os.path.splitext(filename)[1].lower()
    
    # 图片 → MinerU
    if ext in ['.jpg', '.png', ...]:
        return "mineru"
    
    # 纯文本 → 直接插入（不用解析器）
    if ext in ['.txt', '.md']:
        return "mineru"  # 标记，实际会直接插入
    
    # 小文件 → Docling
    if ext in ['.pdf', ...] and file_size < 500KB:
        return "docling"
    
    # 默认 → MinerU
    return "mineru"
```

---

## 性能优化策略

### 1. 读写分离

**核心思想**：
- 插入需要解析器（RAGAnything）
- 查询只需知识图谱（LightRAG）
- 95% 查询是纯文本，无需多模态

**实现**：
```python
# 插入：使用 RAGAnything（带解析器）
rag_instance = get_rag_instance(parser="auto")
await rag_instance.process_document_complete(...)

# 查询：直接使用 LightRAG（绕过解析器）
lightrag = get_lightrag_instance()
answer = await lightrag.aquery(query, param=QueryParam(...))
```

**效果**：
- 查询性能提升（绕过解析器层）
- 资源占用降低（无解析器开销）
- 并发冲突减少（读写分离）

### 2. MAX_ASYNC 优化

**参数调整**：
```bash
MAX_ASYNC=8  # 从 4 提升到 8
```

**影响**：
- **实体合并并发度翻倍**：同时处理 8 个实体（旧：4 个）
- **知识图谱构建加速**：Phase 1/2 处理更快
- **查询响应更稳定**：减少排队等待

**性能数据**：
- 并发查询从 75秒 → 22秒
- 实体合并日志显示 `async: 8`

### 3. 查询参数优化

**配置**：
```bash
TOP_K=20                # 从默认 60 减少（减少 66% 检索量）
CHUNK_TOP_K=10          # 从默认 20 减少
```

**效果**：
- 减少向量检索量
- 降低 LLM API 调用次数
- 查询响应时间优化

### 4. Rerank 重排序

**配置**：
```bash
RERANK_MODEL=Qwen/Qwen3-Reranker-8B
```

**效果**：
- 提升检索结果相关性
- 缓存命中率 88.4%
- 增加约 2-3秒响应时间

---

## 并发控制

### 文档插入并发

**Semaphore 控制**：
```python
# api/task_store.py
DOCUMENT_PROCESSING_CONCURRENCY = 1
DOCUMENT_PROCESSING_SEMAPHORE = asyncio.Semaphore(1)
```

**原因**：
- 防止多个 MinerU 进程同时运行（OOM 风险）
- 单队列处理，保证稳定性

### LightRAG 内部并发

**配置**：
```python
LightRAG(
    llm_model_max_async=8,  # LLM 最大并发
)
```

**参数说明**：
- **llm_model_max_async**: 控制实体/关系提取的并发度
- **max_parallel_insert**: 控制文档插入的并发度（默认 2）

---

## 性能指标

### 查询性能

| 查询模式 | 首次查询 | 缓存查询 | 说明 |
|---------|---------|---------|------|
| **Naive** | 25-26秒 | **3秒** ⚡ | 向量检索，最快 |
| **Local** | 30-40秒 | ~5-10秒 | 局部图谱 |
| **Global** | 40-60秒 | ~10-15秒 | 全局图谱 |
| **Mix** | 35-45秒 | ~8-12秒 | 混合模式 |

**推荐**：
- 日常查询：使用 `naive` 模式（最快）
- 精确查询：使用 `local` 模式
- 全面查询：使用 `mix` 模式

### 并发性能

| 场景 | 响应时间 | 说明 |
|------|---------|------|
| 并发插入+查询 | 22秒 | 旧架构 75秒 |
| 纯查询（无后台任务） | 15-19秒 | 稳定 |
| 10次连续查询平均 | 15.9秒 | 稳定 |

### 资源占用

| 指标 | 数值 | 说明 |
|------|------|------|
| 内存（RSS） | ~50MB | 极低 |
| CPU（处理时） | 70-85% | 正常 |
| CPU（空闲时） | 0% | 正常 |
| 进程数 | 2 | 主进程 + worker |

---

## 技术栈

### 后端框架
- **FastAPI**: Web 框架
- **Uvicorn**: ASGI 服务器
- **Python 3.10**: 运行环境

### RAG 核心
- **LightRAG**: 知识图谱增强检索
- **RAG-Anything**: 多模态文档处理框架

### 解析器
- **MinerU VLM**: 统一多模态模型（< 1B 参数，高精度）
- **Docling**: 轻量级 Python 解析器

### AI 模型

| 类型 | 模型 | 提供商 | 用途 |
|------|------|--------|------|
| LLM | seed-1-6-250615 | 豆包/火山引擎 | 实体提取、答案生成 |
| Embedding | Qwen/Qwen3-Embedding-8B | 硅基流动 | 向量化（4096维） |
| Rerank | Qwen/Qwen3-Reranker-8B | 硅基流动 | 重排序 |
| Vision | seed-1-6-250615 | 豆包/火山引擎 | 图片描述 |

---

## 部署架构

### 开发环境

```
本地机器
  ├─ Python 虚拟环境（uv）
  ├─ FastAPI 服务（8000端口）
  └─ 本地存储
      ├─ rag_local_storage/（知识图谱）
      └─ output/（解析结果）
```

### 生产环境（Docker）

```
Docker 容器
  ├─ Python 3.10 环境
  ├─ FastAPI 服务（8000端口）
  ├─ 持久化卷
  │   ├─ rag_local_storage/（知识图谱）
  │   ├─ output/（解析结果）
  │   ├─ logs/（日志）
  │   └─ model_cache/（模型缓存）
  └─ Nginx 反向代理（可选）
```

---

## API 端点

### 文档插入

**端点**: `POST /insert`

**参数**：
- `doc_id`: 文档ID（查询参数）
- `file`: 文件上传（multipart/form-data）
- `parser`: 解析器选择（可选，默认 `auto`）

**响应**：
```json
{
  "task_id": "uuid",
  "status": "pending",
  "doc_id": "...",
  "filename": "...",
  "parser": "mineru|docling",
  "file_size": 1234
}
```

**解析器选择策略**：
- 纯文本 → 直接插入
- 小文件 (< 500KB) → Docling
- 大文件/复杂 → MinerU
- 用户指定 → 按指定

### 查询

**端点**: `POST /query`

**请求体**：
```json
{
  "query": "你的问题",
  "mode": "naive"
}
```

**查询模式**：
- `naive`: 向量检索（最快，推荐）
- `local`: 局部知识图谱
- `global`: 全局知识图谱
- `hybrid`: 混合模式
- `mix`: 全功能混合

**响应**：
```json
{
  "answer": "..."
}
```

### 任务状态

**端点**: `GET /task/{task_id}`

**响应**：
```json
{
  "task_id": "...",
  "status": "pending|processing|completed|failed",
  "doc_id": "...",
  "filename": "...",
  "created_at": "...",
  "updated_at": "...",
  "error": null,
  "result": {...}
}
```

---

## 配置说明

### 环境变量

#### 核心配置

```bash
# LLM 配置
ARK_API_KEY=...
ARK_BASE_URL=...
ARK_MODEL=seed-1-6-250615

# Embedding 配置
SF_API_KEY=...
SF_BASE_URL=...
SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B

# Rerank 配置
RERANK_MODEL=Qwen/Qwen3-Reranker-8B
```

#### 性能优化参数

```bash
# 查询优化
TOP_K=20                    # 检索数量（默认 60）
CHUNK_TOP_K=10              # 文本块数量（默认 20）
MAX_ASYNC=8                 # LLM 并发数（优化：从 4 提升到 8）
MAX_PARALLEL_INSERT=2       # 插入并发数

# Token 限制
MAX_ENTITY_TOKENS=6000
MAX_RELATION_TOKENS=8000
MAX_TOTAL_TOKENS=30000

# 文档处理并发
DOCUMENT_PROCESSING_CONCURRENCY=1
```

#### MinerU 远程 API（可选）

```bash
# 远程 MinerU 配置
MINERU_MODE=remote|local
MINERU_API_TOKEN=...
MINERU_MODEL_VERSION=vlm|pipeline
```

---

## 设计决策

### 为什么使用单一 LightRAG 实例？

**问题**：
- 旧架构：每个 RAGAnything 实例创建独立的 LightRAG
- 结果：多个 LightRAG 实例访问同一 working_dir
- 风险：读写冲突、资源浪费

**解决方案**：
- 创建单一 LightRAG 实例
- RAGAnything 实例共享这个 LightRAG
- 查询直接访问 LightRAG

**优势**：
- ✅ 避免多实例冲突
- ✅ 资源占用更低
- ✅ 读写逻辑清晰
- ✅ 性能更优

### 为什么查询绕过 RAGAnything？

**观察**：
- 95% 查询是纯文本
- 查询不需要文档解析能力
- RAGAnything 主要用于文档→知识图谱的转换

**决策**：
- 查询直接访问 LightRAG
- 绕过 RAGAnything 的解析器层
- 仅在需要多模态查询时使用 RAGAnything

**效果**：
- 查询性能提升
- 资源占用降低
- 架构更清晰

### 为什么 MAX_ASYNC 从 4 提升到 8？

**问题分析**：
- 75秒慢查询的瓶颈：50 个实体合并
- 每个实体合并 1-8 秒
- 并发度 4 → 需要 ~13 轮（50/4）

**优化**：
- 提升到 8 → 只需 ~7 轮（50/8）
- 减少约 50% 的轮次

**风险**：
- LLM API 并发压力增加
- 但 OpenAI 兼容接口通常支持高并发
- 测试验证：无明显副作用

**结果**：
- 并发查询从 75秒 → 22秒
- 知识图谱构建更快

---

## 未来扩展

### 1. 外部持久化存储

**当前**：本地文件存储（`./rag_local_storage`）

**未来**：
- **Neo4j**: 知识图谱存储
- **PostgreSQL**: 向量数据库（pgvector）
- **Redis**: 缓存和任务队列

**优势**：
- 无状态容器化
- 水平扩展
- 高可用

**实现示例**：
```python
rag = LightRAG(
    working_dir="...",
    graph_storage="Neo4JStorage",  # 替换为 Neo4j
    vector_storage="...",          # 替换为 PostgreSQL
)
```

### 2. 查询服务独立扩展

**当前**：单一服务（插入 + 查询）

**未来**：
```
负载均衡器
    ↓
┌───────┴────────┐
↓                ↓
插入服务（1个）   查询服务（N个）
↓                ↓
    共享存储
    ├─ Neo4j
    ├─ PostgreSQL
    └─ Redis
```

**优势**：
- 查询服务可独立扩展（stateless）
- 插入服务保持单例（避免冲突）
- 资源分配更灵活

### 3. 多模态查询支持

**当前**：仅支持文本查询

**未来**：
```python
# 支持图片+文本查询
await rag.aquery_with_multimodal(
    query="这张图片里有什么？",
    image_data=base64_image,
    mode="hybrid"
)
```

**场景**：
- 图片相似度搜索
- 文档内容对比
- 多模态问答

---

## 监控和维护

### 关键监控指标

1. **性能指标**
   - 查询响应时间（P50、P95、P99）
   - 插入处理时间
   - 并发查询性能

2. **资源指标**
   - 内存占用（RSS）
   - CPU 占用
   - 磁盘 I/O

3. **业务指标**
   - 查询成功率
   - 缓存命中率
   - 任务失败率

### 日志监控

**关键日志**：
```bash
# 查看架构启动
docker compose logs rag-api | grep "Architecture"

# 查看性能指标
docker compose logs rag-api | grep "Query:"

# 查看 Rerank 状态
docker compose logs rag-api | grep -i rerank

# 查看任务处理
docker compose logs rag-api | grep "Task"
```

### 健康检查

**端点**: `GET /`

**响应**：
```json
{
  "status": "running",
  "service": "RAG API",
  "version": "1.0.0"
}
```

---

## 故障排查

### 查询返回 null

**可能原因**：
- LightRAG 实例未初始化
- 知识图谱为空

**检查**：
```bash
# 查看启动日志
docker compose logs rag-api | grep "LightRAG"

# 检查知识图谱文件
ls -lh rag_local_storage/
```

### 查询很慢（> 30秒）

**可能原因**：
- 后台有文档插入任务
- 知识图谱很大
- Rerank 超时

**检查**：
```bash
# 查看后台任务
curl http://localhost:8000/tasks/active

# 查看日志
docker compose logs rag-api --tail=100 | grep "Task"
```

### 内存占用高

**可能原因**：
- 知识图谱过大
- MinerU 进程未清理
- 内存泄漏

**检查**：
```bash
# 查看容器资源
docker stats rag-api

# 查看进程
docker compose exec rag-api ps aux
```

---

## 参考资料

- **LightRAG 官方文档**: https://github.com/hkuds/lightrag
- **RAG-Anything 官方文档**: https://github.com/hkuds/rag-anything
- **MinerU API 文档**: https://mineru.net/apiManage/docs
- **性能分析报告**: [PERFORMANCE_ANALYSIS.md](./PERFORMANCE_ANALYSIS.md)
- **测试报告**: [../test_results.md](../test_results.md)

---

## 总结

RAG API 采用**单一 LightRAG + 多解析器**架构，通过读写分离和并发优化，实现：

1. ✅ **性能提升**：并发查询改善 70.6%（75秒 → 22秒）
2. ✅ **资源优化**：内存占用降低 91%（560MB → 50MB）
3. ✅ **架构清晰**：职责分离，便于维护和扩展
4. ✅ **功能完整**：支持多模态、智能路由、异步处理

**设计哲学**：简单、高效、可扩展。

