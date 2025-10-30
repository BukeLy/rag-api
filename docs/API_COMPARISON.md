# rag-api vs LightRAG 官方 API 对比

## 📋 概述

本文档详细对比 **rag-api** 和 **LightRAG 官方 API** 的功能差异，帮助用户选择合适的解决方案。

### 快速结论

- **rag-api**：生产级多租户 API 服务，强文档解析能力（MinerU/Docling），适合企业 SaaS 场景
- **LightRAG 官方 API**：轻量级单租户 API，功能丰富，适合个人/小团队快速集成

---

## 🎯 核心差异

| 维度 | rag-api | LightRAG 官方 API |
|------|---------|------------------|
| **定位** | 生产级 API 服务 | 研究原型 / 快速集成 |
| **多租户** | ✅ 原生支持（LRU 实例池） | ❌ 单 workspace |
| **文档解析** | ✅ MinerU + Docling（OCR/表格/公式） | ❌ 基础解析（无 OCR） |
| **部署方式** | ✅ Docker 一键部署 | ⚠️ 需手动配置 |
| **批量处理** | ✅ 单次 100 文件（`/batch`） | ❌ 无批量端点 |
| **生产运维** | ✅ 监控/日志/健康检查 | ⚠️ 基础健康检查 |
| **查询功能** | ⚠️ 基础（待增强） | ✅ 丰富（对话历史/自定义提示词） |

---

## 📊 详细端点对比

### 1. 文档上传

#### rag-api: `POST /insert`

**独特优势**：
- ✅ **MinerU 集成**：OCR、表格、公式提取（适合扫描件、复杂文档）
- ✅ **Docling 集成**：轻量级快速解析（适合简单文档）
- ✅ **智能路由**：根据文件类型/大小自动选择解析器
  - 图片（jpg/png）→ MinerU（OCR）
  - 纯文本（txt/md）→ 直接插入（跳过解析）
  - PDF/Office < 500KB → Docling（快速）
  - PDF/Office > 500KB → MinerU（强大）
- ✅ **Remote MinerU**：节省本地 GPU 资源，支持高并发（10+ 并发）
- ✅ **多租户隔离**：每个租户独立 workspace

**LightRAG 官方**: `/documents/upload`

**功能对比**：
- ⚠️ 仅基础文本解析（PDF/DOCX/TXT）
- ❌ 无 OCR 能力（无法处理扫描件）
- ❌ 无表格/公式提取
- ❌ 单 workspace（无多租户）

**可替代性结论**：❌ **不可替代**

**使用场景建议**：
- ✅ 需要处理扫描件/图片 → **使用 rag-api**
- ✅ 需要提取表格/公式 → **使用 rag-api**
- ✅ 多租户 SaaS 场景 → **使用 rag-api**
- ✅ 仅处理纯文本/简单 PDF + 单租户 → 可考虑 LightRAG 官方

---

### 2. 批量上传

#### rag-api: `POST /batch`

**独特优势**：
- ✅ **单次 100 文件**：一个 API 调用上传多个文件
- ✅ **统一追踪**：通过 `batch_id` 查询所有文件的处理状态
- ✅ **高并发处理**：Remote MinerU 模式支持 10+ 并发解析
- ✅ **多租户隔离**

**LightRAG 官方**: **无此功能**

**可替代性结论**：❌ **不可替代**（LightRAG 官方无批量端点）

**使用场景建议**：
- ✅ 需要批量导入文档 → **使用 rag-api**
- ✅ 需要批量追踪任务状态 → **使用 rag-api**

---

### 3. 标准查询

#### rag-api: `POST /query`

**优势**：
- ✅ **多租户隔离**：每个租户独立查询

**劣势**：⚠️ **功能较弱**（对比 LightRAG 官方）
- ❌ 缺少 `conversation_history`（对话历史）
- ❌ 缺少 `user_prompt`（自定义提示词）
- ❌ 缺少 `response_type`（响应格式控制）
- ❌ 缺少 `only_need_context`（仅返回上下文）
- ❌ 缺少 `hl_keywords` / `ll_keywords`（关键词提取）
- ❌ 缺少 token 限制参数

**LightRAG 官方**: `POST /query`

**功能对比**：
- ✅ **支持多轮对话**（`conversation_history`）
- ✅ **自定义提示词**（`user_prompt`）
- ✅ **响应格式控制**（`response_type`：paragraph/list/json）
- ✅ **细粒度控制**（`max_entity_tokens`、`max_relation_tokens`）
- ❌ 单 workspace（无多租户）

**可替代性结论**：⚠️ **部分可替代**（单租户场景下官方功能更强）

**改进计划**：
- 🔄 **v2.0 计划**：为 rag-api 添加以上高级参数，对齐官方功能

**使用场景建议**：
- ✅ 多租户场景 → **使用 rag-api**
- ✅ 需要对话历史/自定义提示词 + 单租户 → 考虑 LightRAG 官方
- ⏳ 等待 rag-api v2.0 更新

---

### 4. 流式查询

#### rag-api: `POST /query/stream` ⏳（计划添加）

**优势**：
- ✅ **多租户隔离**
- ✅ **SSE 流式输出**（实时推送查询结果）

**LightRAG 官方**: `POST /query/stream`

**功能对比**：
- ✅ SSE 流式输出
- ❌ 单 workspace

**可替代性结论**：❌ **不可替代**（因为多租户）

**使用场景建议**：
- ✅ 多租户 + 需要流式输出 → **使用 rag-api**（v2.0）
- ✅ 单租户 + 需要流式输出 → 可考虑 LightRAG 官方

---

### 5. 任务状态查询

#### rag-api: `GET /task/{task_id}`

**优势**：
- ✅ **多租户隔离**（只能查询本租户的任务）

**LightRAG 官方**: `GET /documents/track_status/{track_id}`

**功能对比**：基本相同（异步任务追踪）

**可替代性结论**：⚠️ **单租户场景可替代**

**使用场景建议**：
- ✅ 多租户场景 → **使用 rag-api**
- ✅ 单租户场景 → 两者均可

---

### 6. 批量状态查询

#### rag-api: `GET /batch/{batch_id}`

**优势**：
- ✅ **批量任务统一追踪**
- ✅ **实时进度**（已完成/处理中/失败）

**LightRAG 官方**: **无此功能**

**可替代性结论**：❌ **不可替代**（LightRAG 官方无批量追踪）

**使用场景建议**：
- ✅ 使用 `/batch` 批量上传 → **必须使用 rag-api**

---

### 7. 文件下载服务

#### rag-api: `GET /files/{file_id}/{filename}`

**用途**：
- ✅ **Remote MinerU 依赖**：为远程 MinerU API 提供临时文件访问
- ✅ **自动清理**：过期文件自动删除

**LightRAG 官方**: **无此功能**

**可替代性结论**：❌ **不可替代**（Remote MinerU 必需）

**使用场景建议**：
- ✅ 使用 Remote MinerU 模式 → **必须使用 rag-api**

---

### 8. 租户管理

#### rag-api 租户管理端点

| 端点 | 功能 |
|------|------|
| `GET /tenants/stats` | 租户统计（任务数、实例状态） |
| `DELETE /tenants/cache` | 清理租户缓存（释放内存） |
| `GET /tenants/pool/stats` | 实例池统计（管理员接口） |

**LightRAG 官方**: **无此功能**（官方无多租户概念）

**可替代性结论**：❌ **不可替代**（多租户管理必需）

**使用场景建议**：
- ✅ 多租户 SaaS 场景 → **必须使用 rag-api**
- ✅ 需要租户级别统计/管理 → **必须使用 rag-api**

---

### 9. 监控与健康检查

#### rag-api 监控端点

| 端点 | 功能 |
|------|------|
| `GET /monitor/health` | 系统健康检查（CPU/内存/磁盘） |
| `GET /monitor/metrics` | 统一性能指标（系统/API/文档处理） |

**LightRAG 官方**: `GET /health`

**功能对比**：
- **rag-api**：
  - ✅ 完整系统指标（CPU/内存/磁盘/网络）
  - ✅ API 性能监控（响应时间/吞吐量/错误率）
  - ✅ 文档处理性能（解析时间/成功率）
  - ✅ 告警系统
- **LightRAG 官方**：
  - ⚠️ 基础健康检查（仅返回状态）

**可替代性结论**：❌ **不可替代**（生产环境运维必需）

**使用场景建议**：
- ✅ 生产环境部署 → **使用 rag-api**（完整监控）
- ✅ 研究/测试环境 → 可考虑 LightRAG 官方

---

## 📈 总结对比表

| 端点 | rag-api | LightRAG 官方 | 可替代性 | 差异化价值 |
|------|---------|--------------|---------|-----------|
| **文档上传** | `POST /insert` | `/documents/upload` | ❌ 不可替代 | MinerU/Docling/多租户 |
| **批量上传** | `POST /batch` | **无** | ❌ 不可替代 | rag-api 独有 |
| **标准查询** | `POST /query` | `/query` | ⚠️ 部分可替代 | 多租户（功能待增强） |
| **流式查询** | `POST /query/stream` ⏳ | `/query/stream` | ❌ 不可替代 | 多租户 |
| **任务状态** | `GET /task/{id}` | `/documents/track_status/{id}` | ⚠️ 单租户可替代 | 多租户隔离 |
| **批量状态** | `GET /batch/{id}` | **无** | ❌ 不可替代 | rag-api 独有 |
| **文件服务** | `GET /files/*` | **无** | ❌ 不可替代 | Remote MinerU 必需 |
| **租户管理** | `GET /tenants/*` | **无** | ❌ 不可替代 | 多租户管理必需 |
| **监控** | `GET /monitor/*` | `GET /health` | ❌ 不可替代 | 生产运维必需 |

### 关键结论

1. **0 个端点可以删除**：所有 rag-api 端点都有差异化价值
2. **核心优势**：多租户架构、强文档解析、批量处理、生产运维
3. **待改进**：查询功能需要增强（对齐官方高级参数）

---

## 🎯 使用场景决策树

```
需要 RAG 服务？
  ├─ 是多租户 SaaS 场景？
  │   └─ 是 → **使用 rag-api**（唯一选择）
  │
  ├─ 需要处理扫描件/图片/表格/公式？
  │   └─ 是 → **使用 rag-api**（MinerU 能力）
  │
  ├─ 需要批量上传文档？
  │   └─ 是 → **使用 rag-api**（`/batch` 端点）
  │
  ├─ 需要生产级监控/日志？
  │   └─ 是 → **使用 rag-api**（完整运维）
  │
  └─ 单租户 + 简单文档 + 快速集成？
      └─ 是 → **考虑 LightRAG 官方 API**
```

---

## 🔄 rag-api v2.0 改进计划

### 查询功能增强

**目标**：对齐 LightRAG 官方的高级参数

**新增参数**：
```python
class QueryRequest(BaseModel):
    query: str
    mode: str = "naive"

    # 新增（v2.0）
    conversation_history: Optional[List[Dict]] = None  # 对话历史
    user_prompt: Optional[str] = None  # 自定义提示词
    response_type: Optional[str] = "paragraph"  # paragraph/list/json
    only_need_context: bool = False  # 仅返回上下文
    hl_keywords: Optional[List[str]] = None  # 高级关键词
    ll_keywords: Optional[List[str]] = None  # 低级关键词
    max_entity_tokens: Optional[int] = None  # 实体上下文 token 限制
    max_relation_tokens: Optional[int] = None  # 关系上下文 token 限制
```

**时间线**：2-3 周内完成

---

## 📞 联系与反馈

如有疑问或建议，请：
- 提交 Issue：https://github.com/BukeLy/rag-api/issues
- 邮件联系：buledream233@gmail.com

---

**最后更新**：2025-10-30
