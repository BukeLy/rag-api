# 🐛 前端 BUG 修复报告

**报告日期**: 2025-11-12
**修复版本**: v1.1.0
**部署环境**: 生产环境（45.78.223.205:8000）
**前端域名**: https://main.d2bxt3tjxqfsjq.amplifyapp.com

---

## 📋 问题概述

前端报告了两个核心问题，导致用户体验严重下降：

### 问题 1：跨域请求失败 ❌
- **现象**：所有 POST 请求被浏览器阻止
- **错误信息**：`Response to preflight request doesn't pass access control check`
- **影响**：无法调用 `/query`、`/insert` 等核心 API

### 问题 2：刷新页面后列表为空 ❌
- **现象**：用户上传文档后，刷新页面列表消失
- **影响**：无法查看历史上传的文档和任务

---

## 🔍 根本原因分析

### 问题 1：CORS 未配置
```
浏览器 → OPTIONS /query
后端 → 405 Method Not Allowed ❌

原因：FastAPI 未添加 CORSMiddleware
```

### 问题 2：缺少列表 API
```
前端刷新页面
  ↓
本地 state 清空
  ↓
尝试调用 GET /tasks 或 GET /documents ❌
  ↓
404 Not Found（API 不存在）
  ↓
列表显示为空
```

**OpenAPI 规范确认**：
- ❌ 后端没有 `GET /tasks` 端点（只有 `GET /task/{task_id}`）
- ❌ 后端没有 `GET /documents` 端点（只有 `GET /documents/status`）

---

## ✅ 修复方案

### 修复 1：添加 CORS 支持

**文件**：`main.py`

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://main.d2bxt3tjxqfsjq.amplifyapp.com",  # 前端生产域名
        "http://localhost:3000",  # 本地开发（React）
        "http://localhost:5173",  # 本地开发（Vite）
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    max_age=3600,  # 预检请求缓存 1 小时
)
```

**效果**：
- ✅ OPTIONS 预检请求返回 200 OK
- ✅ 浏览器允许跨域 POST/PUT/DELETE 请求
- ✅ 预检结果缓存 1 小时，减少请求次数

---

### 修复 2：添加列表 API

#### 2.1 任务列表 API

**端点**：`GET /tasks`

**功能**：
- ✅ 分页：`page`, `page_size`（最大 100）
- ✅ 过滤：`status`（pending/processing/completed/failed）
- ✅ 排序：`sort_by`（created_at/updated_at/status），`sort_order`（asc/desc）

**示例**：
```bash
GET /tasks?tenant_id=tenant_76920508&page=1&page_size=20&status=completed
```

#### 2.2 文档列表 API

**端点**：`GET /documents`

**功能**：
- ✅ 分页：`page`, `page_size`（最大 100）
- ✅ 过滤：`status_filter`（pending/processing/preprocessed/processed/failed）
- ✅ 排序：`sort_field`（created_at/updated_at），`sort_direction`（asc/desc）
- ✅ 使用 LightRAG 原生分页 API

**示例**：
```bash
GET /documents?tenant_id=tenant_76920508&page=1&page_size=20&status_filter=processed
```

#### 2.3 文档状态统计 API

**端点**：`GET /documents/status_counts`

**功能**：返回各状态的文档数量

**示例**：
```bash
GET /documents/status_counts?tenant_id=tenant_76920508
```

**响应**：
```json
{
  "status_counts": {
    "pending": 0,
    "processing": 0,
    "preprocessed": 0,
    "processed": 1,
    "failed": 0,
    "all": 1
  }
}
```

---

## 🧪 测试验证

### CORS 测试
```bash
# OPTIONS 预检请求
curl -X OPTIONS "http://45.78.223.205:8000/query" \
  -H "Origin: https://main.d2bxt3tjxqfsjq.amplifyapp.com" \
  -H "Access-Control-Request-Method: POST"

# 响应：200 OK ✅
# access-control-allow-origin: https://main.d2bxt3tjxqfsjq.amplifyapp.com
```

### 列表 API 测试（真实 tenant_id）
```bash
# 文档列表
curl "http://45.78.223.205:8000/documents?tenant_id=tenant_76920508&page=1&page_size=5"

# 响应：1 个文档（faq_cdnw_knowledge_base，544 chunks）✅

# 状态统计
curl "http://45.78.223.205:8000/documents/status_counts?tenant_id=tenant_76920508"

# 响应：processed: 1 ✅
```

---

## 📊 影响范围

### 前端需要更新的代码

**文件**：`src/lib/rag-api.ts`

添加新方法：
```typescript
// 列出任务
async listTasks(
  tenantId: string,
  page = 1,
  pageSize = 50,
  status?: 'pending' | 'processing' | 'completed' | 'failed'
): Promise<{tasks: TaskInfo[], pagination: PaginationInfo}> {
  const params: any = { tenant_id: tenantId, page, page_size: pageSize };
  if (status) params.status = status;

  const { data } = await this.client.get('/tasks', { params });
  return data;
}

// 列出文档
async listDocuments(
  tenantId: string,
  page = 1,
  pageSize = 50,
  statusFilter?: string
): Promise<{documents: DocumentInfo[], pagination: PaginationInfo}> {
  const params: any = { tenant_id: tenantId, page, page_size: pageSize };
  if (statusFilter) params.status_filter = statusFilter;

  const { data } = await this.client.get('/documents', { params });
  return data;
}

// 获取文档状态统计
async getDocumentStatusCounts(tenantId: string): Promise<{status_counts: Record<string, number>}> {
  const { data } = await this.client.get('/documents/status_counts', {
    params: { tenant_id: tenantId }
  });
  return data;
}
```

**文件**：`src/pages/KnowledgePage.tsx`

页面加载时获取列表：
```typescript
useEffect(() => {
  if (!tenantId) return;

  const loadInitialData = async () => {
    try {
      // 加载任务列表
      const tasksResult = await ragAPI.listTasks(tenantId, 1, 50);
      setTasks(tasksResult.tasks);

      // 加载文档列表
      const docsResult = await ragAPI.listDocuments(tenantId, 1, 50);
      setDocuments(docsResult.documents);

      // 加载状态统计
      const counts = await ragAPI.getDocumentStatusCounts(tenantId);
      setStatusCounts(counts.status_counts);
    } catch (error) {
      console.error('Failed to load initial data:', error);
    }
  };

  loadInitialData();
}, [tenantId]);
```

---

## ⚠️ 注意事项

### 1. 分页限制
- **单页最大数量**：100 条
- **最大页码**：10000 页
- **原因**：当前在内存中分页，过大会影响性能

### 2. 性能考虑
- 任务列表：当任务数 > 10000 时，建议前端限制查询范围
- 文档列表：使用 LightRAG 原生分页，性能较好

### 3. 状态值
- **任务状态**：`pending`, `processing`, `completed`, `failed`
- **文档状态**：`pending`, `processing`, `preprocessed`, `processed`, `failed`
- 注意：文档多了一个 `preprocessed` 状态

---

## 🎯 前端行动项

- [ ] **立即可做**：删除本地 localStorage 缓存逻辑（不再需要）
- [ ] **必须完成**：添加 `listTasks()` 和 `listDocuments()` 方法到 `rag-api.ts`
- [ ] **必须完成**：在页面加载时调用列表 API
- [ ] **建议添加**：显示文档状态统计（pending: 2, processed: 10）
- [ ] **建议添加**：分页控件（当文档/任务超过 50 条时）

---

## 📞 联系方式

如有问题，请联系后端团队：
- **部署环境**：http://45.78.223.205:8000
- **API 文档**：http://45.78.223.205:8000/docs
- **测试 tenant_id**：`tenant_76920508`（已验证有数据）

---

**修复完成时间**：2025-11-12 23:40 UTC
**部署状态**：✅ 已部署生产环境
**验证状态**：✅ 已用真实数据验证
