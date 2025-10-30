# LightRAG WebUI 集成指南（多租户版）

本文档说明如何在多租户 RAG 系统中使用 LightRAG 官方 WebUI 进行知识图谱可视化和管理。

## 概述

LightRAG WebUI 是官方提供的图形界面工具，**完全兼容多租户架构**，可以：
- 📊 **可视化知识图谱**：交互式查看指定租户的实体、关系和文档结构
- 📁 **管理文档**：上传、查看和管理租户的已索引文档
- 🔍 **执行查询**：通过友好的 UI 进行 RAG 查询，支持多种查询模式
- 📥 **导出数据**：下载租户的知识图谱数据用于分析
- 🏢 **租户切换**：通过配置可视化不同租户的数据

## 架构设计

### 多租户外部存储共享架构

```
┌─────────────────────────┐         ┌─────────────────────────┐
│   RAG-API (多租户)      │         │  LightRAG WebUI         │
│  • tenant_a             │         │  • 可配置 workspace     │
│  • tenant_b             │         │  • 可视化指定租户       │
│  • tenant_c             │         │                         │
└───────────┬─────────────┘         └───────────┬─────────────┘
            │                                    │
            │     共享外部存储后端（workspace隔离） │
            └────────────────┬───────────────────┘
                             │
                ┌────────────▼────────────┐
                │   外部存储集群           │
                │   （workspace 数据隔离）│
                │                         │
                │  ┌───────────────────┐ │
                │  │ Redis (KV存储)    │ │
                │  │ • tenant_a:*      │ │
                │  │ • tenant_b:*      │ │
                │  │ • default:*       │ │
                │  └───────────────────┘ │
                │  ┌───────────────────┐ │
                │  │ Neo4j (图存储)    │ │
                │  │ • workspace隔离   │ │
                │  └───────────────────┘ │
                │  ┌───────────────────┐ │
                │  │PostgreSQL(向量)   │ │
                │  │ • workspace隔离   │ │
                │  └───────────────────┘ │
                └─────────────────────────┘
```

### 🔑 多租户关键特性

1. **Workspace 隔离**
   - 每个租户有独立的 `workspace`（对应 `tenant_id`）
   - WebUI 通过 `LIGHTRAG_WEBUI_WORKSPACE` 环境变量选择要可视化的租户
   - 数据在存储层面完全隔离（Redis key 前缀、Neo4j namespace、PostgreSQL workspace 字段）

2. **数据实时同步**
   - 两个服务连接同一套数据库，数据变更实时可见
   - 通过 rag-api 插入的数据立即在 WebUI 中可见（如果 workspace 匹配）

3. **独立部署**
   - WebUI 服务可独立启停，不影响 API 服务
   - 切换租户只需修改环境变量并重启 WebUI

4. **本地目录无关**
   - 数据存储在外部数据库，本地目录仅用于临时文件

## 快速开始

### 1. 确保外部存储已启动

```bash
# 检查外部存储服务状态
docker compose ps redis neo4j postgres

# 如果未启动，先启动外部存储
docker compose up -d redis neo4j postgres
```

### 2. 配置 WebUI Workspace

在 `.env` 文件中配置要可视化的租户：

```bash
# 默认可视化 "default" 租户的数据
LIGHTRAG_WEBUI_WORKSPACE=default

# 或切换到其他租户（例如 tenant_a）
# LIGHTRAG_WEBUI_WORKSPACE=tenant_a
```

### 3. 启动 WebUI 服务

```bash
# 启动所有服务（包括 WebUI）
docker compose up -d

# 或者单独启动 WebUI
docker compose up -d lightrag-webui

# 查看启动日志
docker compose logs -f lightrag-webui
```

### 4. 访问 WebUI

打开浏览器访问：

- **本地开发**：http://localhost:9621/webui/
- **远程服务器（dev）**：http://45.78.223.205:9621/webui/
- **API 文档**：http://localhost:9621/docs

### 5. 验证连接

打开 WebUI 后，你应该能看到：
- 通过 rag-api 上传到相同 workspace 的所有文档
- 该租户的所有已提取的实体和关系
- 可以执行查询并获得结果

## 多租户使用场景

### 场景 1：可视化默认租户数据

```bash
# .env 配置
LIGHTRAG_WEBUI_WORKSPACE=default

# 使用 rag-api 插入数据
curl -X POST "http://localhost:8000/insert?tenant_id=default" \
  -F "file=@document.pdf"

# 在 WebUI 中立即可见
# http://localhost:9621/webui/
```

### 场景 2：切换到特定租户

```bash
# 1. 修改 .env
LIGHTRAG_WEBUI_WORKSPACE=tenant_a

# 2. 重启 WebUI
docker compose restart lightrag-webui

# 3. 访问 WebUI 查看 tenant_a 的数据
# http://localhost:9621/webui/
```

### 场景 3：多个 WebUI 实例（高级）

如果需要同时可视化多个租户，可以运行多个 WebUI 实例：

```bash
# docker-compose.override.yml
services:
  lightrag-webui-tenant-a:
    extends: lightrag-webui
    container_name: lightrag-webui-tenant-a
    ports:
      - "9621:9621"
    environment:
      - WORKSPACE=tenant_a

  lightrag-webui-tenant-b:
    extends: lightrag-webui
    container_name: lightrag-webui-tenant-b
    ports:
      - "9622:9621"
    environment:
      - WORKSPACE=tenant_b
```

## 配置说明

### 核心环境变量

```bash
# --- Workspace 配置（必需，对应租户 ID）---
LIGHTRAG_WEBUI_WORKSPACE=default

# --- 存储后端配置（自动从 rag-api 配置继承）---
# 以下变量在 docker-compose.yml 中自动映射，无需手动配置
# - LIGHTRAG_KV_STORAGE
# - LIGHTRAG_VECTOR_STORAGE
# - LIGHTRAG_GRAPH_STORAGE
# - LIGHTRAG_DOC_STATUS_STORAGE

# --- 访问控制（可选）---
# API Key 认证（用于 API 端点访问）
LIGHTRAG_API_KEY=your_secret_api_key

# Web UI 登录账号（JSON 数组格式）
LIGHTRAG_AUTH_ACCOUNTS='[{"username": "admin", "password": "secure_password"}]'
```

### Docker Compose 配置

WebUI 服务已集成到 `docker-compose.yml`，核心配置如下：

```yaml
lightrag-webui:
  image: ghcr.io/hkuds/lightrag:latest
  container_name: lightrag-webui
  ports:
    - "9621:9621"
  environment:
    # 多租户关键配置
    - WORKSPACE=${LIGHTRAG_WEBUI_WORKSPACE:-default}
    # 存储后端自动映射
    - LIGHTRAG_KV_STORAGE=${KV_STORAGE:-JsonKVStorage}
    - LIGHTRAG_VECTOR_STORAGE=${VECTOR_STORAGE:-NanoVectorDB}
    - LIGHTRAG_GRAPH_STORAGE=${GRAPH_STORAGE:-NetworkXStorage}
  depends_on:
    redis:
      condition: service_healthy
    neo4j:
      condition: service_healthy
    postgres:
      condition: service_healthy
```

## 使用指南

### 文档管理

#### 1. 通过 rag-api 上传（推荐）

使用 rag-api 的强大解析能力上传文档：

```bash
# 单文件上传
curl -X POST "http://localhost:8000/insert?tenant_id=default" \
  -F "file=@document.pdf"

# 批量上传（最多 100 个文件）
curl -X POST "http://localhost:8000/batch?tenant_id=default" \
  -F "files=@doc1.pdf" \
  -F "files=@doc2.pdf" \
  -F "files=@doc3.pdf"
```

**优势**：
- 支持 MinerU（OCR/表格/公式）和 Docling（快速解析）
- 智能选择解析器
- 批量处理能力
- 异步任务管理

#### 2. 通过 WebUI 上传（简单场景）

在 WebUI 界面点击 "Upload" 按钮上传文档。

**适用场景**：
- 单个文档上传
- 简单文本或 PDF
- 快速测试

#### 3. 查看文档

- WebUI 会显示当前 workspace 的所有已索引文档
- 点击文档可查看详情和提取的实体

### 知识图谱可视化

#### 1. 查看实体和关系

- 导航到 "Graph" 页面
- 可以搜索特定实体
- 交互式查看实体之间的关系
- **注意**：只显示当前 workspace 的数据

#### 2. 过滤和搜索

- 按实体类型过滤
- 按关系类型过滤
- 搜索特定实体或文本

#### 3. 图谱统计

查看当前租户的知识图谱统计信息：
- 实体总数
- 关系总数
- 文档总数
- 图谱密度

### RAG 查询

#### 1. 执行查询

导航到 "Query" 页面，输入查询问题并选择查询模式：

| 模式 | 速度 | 适用场景 | 特点 |
|------|------|----------|------|
| `naive` | ⚡ 最快（15-20s） | 简单问答 | 直接文本匹配 |
| `local` | 🚀 快速（20-30s） | 特定主题深入 | 关注局部实体 |
| `global` | 🐢 较慢（30-50s） | 宏观分析 | 全局知识整合 |
| `hybrid` | ⚖️ 平衡（25-40s） | 平衡准确性和速度 | 混合策略 |
| `mix` | 🐌 最慢（50-80s） | 最全面分析 | 所有模式结合 |

**推荐**：
- 日常查询使用 `naive` 模式
- 复杂分析使用 `hybrid` 或 `global` 模式

#### 2. 查看结果

- 查询结果会显示相关文档和上下文
- 可以查看用于生成答案的源文档
- **数据来源**：仅限当前 workspace 的数据

### 数据导出

在 WebUI 中可以导出当前租户的知识图谱数据：
- 导出实体列表（CSV）
- 导出关系列表（CSV）
- 导出完整图结构（JSON 格式）

## 常见问题排查

### 问题 1：WebUI 看不到通过 rag-api 上传的文档

**原因**：Workspace 不匹配

**解决方案**：
```bash
# 1. 检查 rag-api 使用的 tenant_id
curl "http://localhost:8000/tenants/stats?tenant_id=your_tenant"

# 2. 确保 WebUI 的 WORKSPACE 与 tenant_id 一致
# 修改 .env
LIGHTRAG_WEBUI_WORKSPACE=your_tenant

# 3. 重启 WebUI
docker compose restart lightrag-webui
```

### 问题 2：WebUI 启动失败

**检查步骤**：

```bash
# 1. 查看日志
docker compose logs lightrag-webui

# 2. 检查外部存储连接
docker compose exec lightrag-webui curl http://redis:6379

# 3. 检查镜像是否正确拉取
docker pull ghcr.io/hkuds/lightrag:latest
```

### 问题 3：连接外部存储失败

**解决方案**：

```bash
# 1. 确认存储服务健康
docker compose ps redis neo4j postgres

# 2. 检查环境变量配置
docker compose exec lightrag-webui env | grep -E "REDIS|NEO4J|POSTGRES"

# 3. 检查网络连接
docker compose exec lightrag-webui ping redis
```

### 问题 4：数据不同步

**可能原因**：
- Workspace 不匹配（最常见）
- 外部存储配置不一致
- 缓存问题

**解决方案**：
```bash
# 1. 验证 workspace 配置
echo $LIGHTRAG_WEBUI_WORKSPACE  # 应该与 tenant_id 一致

# 2. 清除 WebUI 缓存
docker compose restart lightrag-webui

# 3. 检查存储后端配置是否一致
docker compose config | grep -A 10 lightrag-webui
```

### 问题 5：查询性能慢

**优化建议**：

1. **使用 naive 模式**：日常查询最快
2. **调整 rag-api 配置**：
   ```bash
   # .env
   MAX_ASYNC=8  # 增加并发
   TOP_K=20     # 减少检索数量
   ```
3. **启用 Rerank**：提高检索质量
4. **使用索引优化**：确保数据库索引正确配置

## 性能优化建议

### 1. WebUI 服务资源限制

```yaml
# docker-compose.yml
lightrag-webui:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 1G
```

### 2. 外部存储优化

- **Redis**：启用持久化，避免数据丢失
- **Neo4j**：配置适当的堆内存（推荐 2-4GB）
- **PostgreSQL**：启用 pgvector 索引优化

### 3. 网络优化

如果 WebUI 和 rag-api 部署在不同机器：
- 使用同一区域的数据库实例
- 配置 VPC 内网访问
- 启用数据库连接池

## 高级功能

### 自定义认证

```python
# 自定义认证逻辑（在 WebUI 配置中）
AUTH_ACCOUNTS='[
  {"username": "admin", "password": "admin123", "role": "admin"},
  {"username": "viewer", "password": "viewer123", "role": "readonly"}
]'
```

### API 编程访问

WebUI 的后端 API 也可以通过编程方式访问：

```python
import requests

# 查询接口
response = requests.post(
    "http://localhost:9621/query",
    json={"query": "What is RAG?", "mode": "naive"},
    headers={"X-API-Key": "your_api_key"}
)
print(response.json())
```

### 批量导出脚本

```bash
#!/bin/bash
# 导出所有租户的知识图谱数据

TENANTS=("default" "tenant_a" "tenant_b")

for tenant in "${TENANTS[@]}"; do
    echo "Exporting $tenant..."
    # 更新 .env
    sed -i "s/LIGHTRAG_WEBUI_WORKSPACE=.*/LIGHTRAG_WEBUI_WORKSPACE=$tenant/" .env
    # 重启 WebUI
    docker compose restart lightrag-webui
    sleep 10
    # 调用导出 API
    curl "http://localhost:9621/export/graph" -o "${tenant}_graph.json"
done
```

## 与 rag-api 的对比

| 特性 | rag-api | LightRAG WebUI |
|------|---------|----------------|
| **文档解析** | ✅ MinerU + Docling | ⚠️ 基础解析 |
| **批量处理** | ✅ 支持（100 文件） | ❌ 不支持 |
| **多租户** | ✅ 完整支持 | ⚠️ 单租户可视化 |
| **可视化** | ❌ 无 | ✅ 图谱可视化 |
| **编程接口** | ✅ RESTful API | ⚠️ 有限的 API |
| **性能优化** | ✅ 定制优化 | ⚠️ 标准性能 |
| **适用场景** | 生产环境、自动化 | 调试、演示、可视化 |

## 最佳实践

1. **文档导入**：使用 rag-api，享受强大的解析能力
2. **知识图谱可视化**：使用 WebUI，直观查看结果
3. **生产查询**：使用 rag-api，性能更优
4. **调试验证**：使用 WebUI，快速定位问题
5. **租户隔离**：通过 workspace 严格隔离不同租户数据
6. **定期备份**：导出知识图谱数据用于备份和分析

## 总结

LightRAG WebUI 与 rag-api 形成完美互补：
- **rag-api** 负责生产级的文档处理和查询服务
- **WebUI** 提供直观的可视化和调试能力
- **多租户架构** 通过 workspace 机制实现数据隔离
- **外部存储** 确保两者数据实时同步

通过合理使用两者，可以构建一个功能强大、易于管理的企业级 RAG 系统。
