# 📚 前端 API 对接文档 - 列表功能

**版本**: v1.1.0
**更新日期**: 2025-11-12
**Base URL**: `http://45.78.223.205:8000`
**API 文档**: http://45.78.223.205:8000/docs

---

## 🆕 新增 API 端点

### 1. 获取任务列表

#### 基本信息
- **端点**: `GET /tasks`
- **功能**: 获取租户的所有任务，支持分页、过滤、排序
- **认证**: 需要 `tenant_id` 参数

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|------|------|------|--------|------|------|
| `tenant_id` | string | ✅ | - | 租户 ID | 必须提供 |
| `page` | integer | ❌ | 1 | 页码（从 1 开始） | 1-10000 |
| `page_size` | integer | ❌ | 50 | 每页数量 | 1-100 |
| `status` | string | ❌ | null | 过滤状态 | pending, processing, completed, failed |
| `sort_by` | string | ❌ | created_at | 排序字段 | created_at, updated_at, status |
| `sort_order` | string | ❌ | desc | 排序方向 | asc, desc |

#### 请求示例

```bash
# 获取第 1 页（默认按创建时间倒序）
GET /tasks?tenant_id=tenant_76920508&page=1&page_size=20

# 过滤已完成的任务
GET /tasks?tenant_id=tenant_76920508&status=completed

# 按更新时间升序排序
GET /tasks?tenant_id=tenant_76920508&sort_by=updated_at&sort_order=asc
```

#### 响应格式

```typescript
interface TaskListResponse {
  tasks: Task[];
  pagination: PaginationInfo;
}

interface Task {
  task_id: string;
  tenant_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  doc_id: string;
  filename: string;
  created_at: string;  // ISO 8601 格式
  updated_at: string;  // ISO 8601 格式
  result?: {           // 仅 status=completed 时存在
    message: string;
    doc_id: string;
    filename: string;
    chunks_count: number;
  };
  error?: string;      // 仅 status=failed 时存在
}

interface PaginationInfo {
  total: number;        // 总数量
  page: number;         // 当前页
  page_size: number;    // 每页数量
  total_pages: number;  // 总页数
  has_next: boolean;    // 是否有下一页
  has_prev: boolean;    // 是否有上一页
}
```

#### 响应示例

```json
{
  "tasks": [
    {
      "task_id": "task-abc123",
      "tenant_id": "tenant_76920508",
      "status": "completed",
      "doc_id": "doc-001",
      "filename": "test.pdf",
      "created_at": "2025-11-12T10:00:00Z",
      "updated_at": "2025-11-12T10:02:30Z",
      "result": {
        "message": "Document processed successfully",
        "doc_id": "doc-001",
        "filename": "test.pdf",
        "chunks_count": 42
      }
    }
  ],
  "pagination": {
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

#### 错误响应

```json
{
  "detail": "Failed to retrieve tasks"
}
```

---

### 2. 获取文档列表

#### 基本信息
- **端点**: `GET /documents`
- **功能**: 获取租户的所有文档，支持分页、过滤、排序
- **认证**: 需要 `tenant_id` 参数
- **底层**: 使用 LightRAG 原生分页 API

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|------|------|------|--------|------|------|
| `tenant_id` | string | ✅ | - | 租户 ID | 必须提供 |
| `page` | integer | ❌ | 1 | 页码（从 1 开始） | 1-10000 |
| `page_size` | integer | ❌ | 50 | 每页数量 | 1-100 |
| `status_filter` | string | ❌ | null | 过滤状态 | pending, processing, preprocessed, processed, failed |
| `sort_field` | string | ❌ | created_at | 排序字段 | created_at, updated_at |
| `sort_direction` | string | ❌ | desc | 排序方向 | asc, desc |

#### 请求示例

```bash
# 获取第 1 页
GET /documents?tenant_id=tenant_76920508&page=1&page_size=20

# 过滤已处理的文档
GET /documents?tenant_id=tenant_76920508&status_filter=processed

# 按更新时间升序排序
GET /documents?tenant_id=tenant_76920508&sort_field=updated_at&sort_direction=asc
```

#### 响应格式

```typescript
interface DocumentListResponse {
  documents: Document[];
  pagination: PaginationInfo;
}

interface Document {
  content_summary: string;     // 文档摘要
  content_length: number;      // 内容长度
  file_path: string;           // 文件路径
  status: 'pending' | 'processing' | 'preprocessed' | 'processed' | 'failed';
  created_at: string;          // ISO 8601 格式
  updated_at: string;          // ISO 8601 格式
  track_id: string;            // 追踪 ID
  chunks_count: number;        // 切片数量
  chunks_list: string[];       // 切片 ID 列表
  error_msg?: string;          // 错误信息（仅 failed 时）
  metadata?: Record<string, any>;  // 元数据
}
```

#### 响应示例

```json
{
  "documents": [
    {
      "content_summary": "# FAQ 知识库 - CDNW\n总记录数：2379 条...",
      "content_length": 2051440,
      "file_path": "faq_cdnw_knowledge_base.md",
      "status": "processed",
      "created_at": "2025-11-08T05:50:38.519825+00:00",
      "updated_at": "2025-11-08T16:17:31.017162+00:00",
      "track_id": "insert_20251108_135036_4876259e",
      "chunks_count": 544,
      "chunks_list": ["chunk-3977a2dd...", "..."],
      "error_msg": null,
      "metadata": {
        "processing_start_time": 1762581812,
        "processing_end_time": 1762618651
      }
    }
  ],
  "pagination": {
    "total": 1,
    "page": 1,
    "page_size": 20,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 3. 获取文档状态统计

#### 基本信息
- **端点**: `GET /documents/status_counts`
- **功能**: 获取各状态的文档数量统计
- **认证**: 需要 `tenant_id` 参数

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `tenant_id` | string | ✅ | 租户 ID |

#### 请求示例

```bash
GET /documents/status_counts?tenant_id=tenant_76920508
```

#### 响应格式

```typescript
interface StatusCountsResponse {
  status_counts: {
    pending: number;
    processing: number;
    preprocessed: number;
    processed: number;
    failed: number;
    all: number;  // 总数
  };
}
```

#### 响应示例

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

## 🔧 TypeScript 集成代码

### 类型定义（`src/types/rag-api.ts`）

```typescript
export interface PaginationInfo {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_prev: boolean;
}

export interface TaskInfo {
  task_id: string;
  tenant_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  doc_id: string;
  filename: string;
  created_at: string;
  updated_at: string;
  result?: {
    message: string;
    doc_id: string;
    filename: string;
    chunks_count: number;
  };
  error?: string;
}

export interface DocumentInfo {
  content_summary: string;
  content_length: number;
  file_path: string;
  status: 'pending' | 'processing' | 'preprocessed' | 'processed' | 'failed';
  created_at: string;
  updated_at: string;
  track_id: string;
  chunks_count: number;
  chunks_list: string[];
  error_msg?: string;
  metadata?: Record<string, any>;
}

export interface TaskListResponse {
  tasks: TaskInfo[];
  pagination: PaginationInfo;
}

export interface DocumentListResponse {
  documents: DocumentInfo[];
  pagination: PaginationInfo;
}

export interface StatusCountsResponse {
  status_counts: {
    pending: number;
    processing: number;
    preprocessed: number;
    processed: number;
    failed: number;
    all: number;
  };
}
```

### API 客户端（`src/lib/rag-api.ts`）

```typescript
import axios, { AxiosInstance } from 'axios';
import {
  TaskListResponse,
  DocumentListResponse,
  StatusCountsResponse,
  TaskInfo,
  DocumentInfo
} from '@/types/rag-api';

export class RAGAPIClient {
  private client: AxiosInstance;

  constructor(baseURL: string = 'http://45.78.223.205:8000') {
    this.client = axios.create({
      baseURL,
      timeout: 60000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * 获取任务列表
   */
  async listTasks(
    tenantId: string,
    options?: {
      page?: number;
      pageSize?: number;
      status?: 'pending' | 'processing' | 'completed' | 'failed';
      sortBy?: 'created_at' | 'updated_at' | 'status';
      sortOrder?: 'asc' | 'desc';
    }
  ): Promise<TaskListResponse> {
    const params: any = {
      tenant_id: tenantId,
      page: options?.page ?? 1,
      page_size: options?.pageSize ?? 50,
    };

    if (options?.status) params.status = options.status;
    if (options?.sortBy) params.sort_by = options.sortBy;
    if (options?.sortOrder) params.sort_order = options.sortOrder;

    const { data } = await this.client.get<TaskListResponse>('/tasks', { params });
    return data;
  }

  /**
   * 获取文档列表
   */
  async listDocuments(
    tenantId: string,
    options?: {
      page?: number;
      pageSize?: number;
      statusFilter?: 'pending' | 'processing' | 'preprocessed' | 'processed' | 'failed';
      sortField?: 'created_at' | 'updated_at';
      sortDirection?: 'asc' | 'desc';
    }
  ): Promise<DocumentListResponse> {
    const params: any = {
      tenant_id: tenantId,
      page: options?.page ?? 1,
      page_size: options?.pageSize ?? 50,
    };

    if (options?.statusFilter) params.status_filter = options.statusFilter;
    if (options?.sortField) params.sort_field = options.sortField;
    if (options?.sortDirection) params.sort_direction = options.sortDirection;

    const { data } = await this.client.get<DocumentListResponse>('/documents', { params });
    return data;
  }

  /**
   * 获取文档状态统计
   */
  async getDocumentStatusCounts(tenantId: string): Promise<StatusCountsResponse> {
    const { data } = await this.client.get<StatusCountsResponse>(
      '/documents/status_counts',
      { params: { tenant_id: tenantId } }
    );
    return data;
  }
}

// 导出单例
export const ragAPI = new RAGAPIClient();
```

### React 组件示例（`src/pages/KnowledgePage.tsx`）

```typescript
import React, { useState, useEffect } from 'react';
import { ragAPI } from '@/lib/rag-api';
import { TaskInfo, DocumentInfo, PaginationInfo } from '@/types/rag-api';

export const KnowledgePage: React.FC = () => {
  const [tenantId] = useState('tenant_76920508'); // 从上下文获取
  const [tasks, setTasks] = useState<TaskInfo[]>([]);
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [tasksPagination, setTasksPagination] = useState<PaginationInfo | null>(null);
  const [docsPagination, setDocsPagination] = useState<PaginationInfo | null>(null);
  const [statusCounts, setStatusCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);

  // 页面加载时获取数据
  useEffect(() => {
    const loadInitialData = async () => {
      if (!tenantId) return;

      try {
        setLoading(true);

        // 并行加载所有数据
        const [tasksResult, docsResult, countsResult] = await Promise.all([
          ragAPI.listTasks(tenantId, { page: 1, pageSize: 20 }),
          ragAPI.listDocuments(tenantId, { page: 1, pageSize: 20 }),
          ragAPI.getDocumentStatusCounts(tenantId),
        ]);

        setTasks(tasksResult.tasks);
        setTasksPagination(tasksResult.pagination);

        setDocuments(docsResult.documents);
        setDocsPagination(docsResult.pagination);

        setStatusCounts(countsResult.status_counts);
      } catch (error) {
        console.error('Failed to load initial data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadInitialData();
  }, [tenantId]);

  // 加载下一页任务
  const loadNextTasksPage = async () => {
    if (!tasksPagination?.has_next) return;

    try {
      const result = await ragAPI.listTasks(tenantId, {
        page: tasksPagination.page + 1,
        pageSize: 20,
      });
      setTasks(result.tasks);
      setTasksPagination(result.pagination);
    } catch (error) {
      console.error('Failed to load next tasks page:', error);
    }
  };

  // 过滤已完成的文档
  const loadCompletedDocuments = async () => {
    try {
      const result = await ragAPI.listDocuments(tenantId, {
        statusFilter: 'processed',
        page: 1,
        pageSize: 20,
      });
      setDocuments(result.documents);
      setDocsPagination(result.pagination);
    } catch (error) {
      console.error('Failed to load completed documents:', error);
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      {/* 状态统计 */}
      <div className="stats">
        <div>待处理: {statusCounts.pending}</div>
        <div>处理中: {statusCounts.processing}</div>
        <div>已完成: {statusCounts.processed}</div>
        <div>失败: {statusCounts.failed}</div>
      </div>

      {/* 任务列表 */}
      <div className="tasks">
        <h2>任务列表 ({tasksPagination?.total})</h2>
        {tasks.map(task => (
          <div key={task.task_id}>
            <span>{task.filename}</span>
            <span>{task.status}</span>
          </div>
        ))}
        {tasksPagination?.has_next && (
          <button onClick={loadNextTasksPage}>加载更多</button>
        )}
      </div>

      {/* 文档列表 */}
      <div className="documents">
        <h2>文档列表 ({docsPagination?.total})</h2>
        {documents.map((doc, idx) => (
          <div key={idx}>
            <span>{doc.file_path}</span>
            <span>{doc.status}</span>
            <span>{doc.chunks_count} chunks</span>
          </div>
        ))}
      </div>
    </div>
  );
};
```

---

## ⚠️ 注意事项

### 1. 分页限制
- **单页最大数量**: 100 条（`page_size <= 100`）
- **最大页码**: 10000 页
- **建议**: 使用默认的 50 条/页，性能最佳

### 2. 状态值差异
- **任务状态**: 4 种（pending, processing, completed, failed）
- **文档状态**: 5 种（pending, processing, **preprocessed**, processed, failed）
- 注意：文档多了 `preprocessed` 状态

### 3. 错误处理
```typescript
try {
  const result = await ragAPI.listTasks(tenantId);
} catch (error) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 500) {
      console.error('服务器错误:', error.response.data.detail);
    } else if (error.response?.status === 501) {
      console.error('功能未实现:', error.response.data.detail);
    }
  }
}
```

### 4. 性能优化建议
- **初始加载**: 使用 `pageSize=20` 快速展示
- **懒加载**: 滚动到底部时加载下一页
- **缓存**: 可以缓存 5 分钟，减少请求次数
- **并行请求**: 任务列表和文档列表可以并行加载

---

## 📊 完整示例：带分页的列表组件

```typescript
import React, { useState, useEffect, useCallback } from 'react';
import { ragAPI } from '@/lib/rag-api';
import { DocumentInfo, PaginationInfo } from '@/types/rag-api';

export const DocumentList: React.FC<{ tenantId: string }> = ({ tenantId }) => {
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [pagination, setPagination] = useState<PaginationInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const loadDocuments = useCallback(async (page: number) => {
    try {
      setLoading(true);
      const result = await ragAPI.listDocuments(tenantId, {
        page,
        pageSize: 20,
        statusFilter: statusFilter as any,
      });
      setDocuments(result.documents);
      setPagination(result.pagination);
      setCurrentPage(page);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  }, [tenantId, statusFilter]);

  useEffect(() => {
    loadDocuments(1);
  }, [loadDocuments]);

  const goToPage = (page: number) => {
    if (page < 1 || (pagination && page > pagination.total_pages)) return;
    loadDocuments(page);
  };

  return (
    <div>
      {/* 过滤器 */}
      <div className="filters">
        <select
          value={statusFilter || ''}
          onChange={e => setStatusFilter(e.target.value || undefined)}
        >
          <option value="">所有状态</option>
          <option value="processed">已完成</option>
          <option value="processing">处理中</option>
          <option value="failed">失败</option>
        </select>
      </div>

      {/* 列表 */}
      <div className="list">
        {loading ? (
          <div>加载中...</div>
        ) : (
          documents.map((doc, idx) => (
            <div key={idx} className="document-item">
              <h3>{doc.file_path}</h3>
              <p>状态: {doc.status}</p>
              <p>切片数: {doc.chunks_count}</p>
              <p>创建时间: {new Date(doc.created_at).toLocaleString()}</p>
            </div>
          ))
        )}
      </div>

      {/* 分页控件 */}
      {pagination && pagination.total_pages > 1 && (
        <div className="pagination">
          <button
            onClick={() => goToPage(currentPage - 1)}
            disabled={!pagination.has_prev}
          >
            上一页
          </button>
          <span>
            第 {pagination.page} 页 / 共 {pagination.total_pages} 页
            （共 {pagination.total} 条）
          </span>
          <button
            onClick={() => goToPage(currentPage + 1)}
            disabled={!pagination.has_next}
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
};
```

---

## 🚀 快速开始

### 1. 安装依赖
```bash
npm install axios
```

### 2. 复制类型定义
将上面的 TypeScript 类型复制到 `src/types/rag-api.ts`

### 3. 复制 API 客户端
将 `RAGAPIClient` 复制到 `src/lib/rag-api.ts`

### 4. 使用示例
```typescript
import { ragAPI } from '@/lib/rag-api';

// 获取任务列表
const tasks = await ragAPI.listTasks('tenant_76920508');

// 获取文档列表（已完成）
const docs = await ragAPI.listDocuments('tenant_76920508', {
  statusFilter: 'processed',
  page: 1,
  pageSize: 20
});

// 获取状态统计
const counts = await ragAPI.getDocumentStatusCounts('tenant_76920508');
console.log(`已完成: ${counts.status_counts.processed}`);
```

---

## 📞 支持

- **API 文档**: http://45.78.223.205:8000/docs
- **测试环境**: http://45.78.223.205:8000
- **测试 tenant_id**: `tenant_76920508`（已有数据）

如有问题请联系后端团队 🚀
