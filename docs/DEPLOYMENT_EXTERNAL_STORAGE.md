# 外部存储部署指南

## 📋 存储架构说明

RAG API 采用高性能外部存储架构：**DragonflyDB + Qdrant + Memgraph**。

### 存储组件

| 组件 | 用途 | 特点 |
|------|------|------|
| **DragonflyDB** | KV 存储 | • Redis 协议兼容<br/>• 高性能（25x Redis）<br/>• 自动快照备份 |
| **Qdrant** | 向量存储 | • 专业向量数据库<br/>• 无维度限制<br/>• 分布式扩展 |
| **Memgraph** | 图存储 | • 高性能图计算<br/>• Cypher 兼容<br/>• 实时分析 |

---

## 🚀 快速开始

### 前提条件

- Docker 和 Docker Compose 已安装
- 已克隆 rag-api 项目

### 一键部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/BukeLy/rag-api.git
cd rag-api

# 2. 配置环境变量
cp env.example .env
nano .env  # 填入你的 API 密钥

# 3. 运行一键部署脚本
chmod +x deploy.sh
./deploy.sh

# 选择模式 1（生产模式）
# 脚本会自动启动：
# - rag-api 服务
# - DragonflyDB
# - Qdrant
# - Memgraph
# - LightRAG WebUI

# 4. 验证服务
curl http://localhost:8000/
```

---

## 📝 环境变量配置

### 必需配置

在 `.env` 文件中配置以下参数：

```bash
# ====== 存储架构配置 ======
USE_EXTERNAL_STORAGE=true

# KV 存储：DragonflyDB（Redis 协议兼容）
KV_STORAGE=RedisKVStorage
REDIS_URI=redis://dragonflydb:6379/0

# 向量存储：Qdrant（无维度限制，支持 4096 维度）
VECTOR_STORAGE=QdrantVectorDBStorage
QDRANT_URL=http://qdrant:6333
# QDRANT_API_KEY=your_api_key  # 生产环境建议启用

# 图存储：Memgraph（比 Neo4j 快 50 倍）
GRAPH_STORAGE=MemgraphStorage
MEMGRAPH_URI=bolt://memgraph:7687
MEMGRAPH_USERNAME=  # Memgraph 默认无认证
MEMGRAPH_PASSWORD=

# ====== Embedding 维度配置（极其重要）======
# 必须与模型匹配：
# - Qwen3-Embedding-0.6B → 1024 维度（当前配置，配合 Rerank 效果好）
# - Qwen3-Embedding-8B → 4096 维度（更高精度，需更多资源）
EMBEDDING_DIM=1024

# ====== LLM 配置（功能导向命名）======
LLM_API_KEY=your_llm_api_key_here
LLM_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
LLM_MODEL=seed-1-6-250615

# ====== Embedding 配置（功能导向命名）======
EMBEDDING_API_KEY=your_embedding_api_key_here
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B  # 1024 维度
```

---

## 🐳 Docker 部署

### 生产模式

```bash
# 启动所有服务
docker compose -f docker-compose.yml up -d

# 查看日志
docker compose logs -f

# 验证服务状态
docker compose ps

# 预期输出：
# NAME                COMMAND             SERVICE          STATUS
# rag-api             "uv run uvicorn..." rag-api          Up (healthy)
# rag-dragonflydb     "dragonfly..."      dragonflydb      Up (healthy)
# rag-qdrant          "/qdrant/qdrant..." qdrant           Up (healthy)
# rag-memgraph        "docker-entry..."   memgraph         Up (healthy)
# lightrag-webui      "python -m..."      lightrag-webui   Up
```

### 开发模式（代码热重载）

```bash
# 启动开发环境
docker compose -f docker-compose.dev.yml up -d

# 查看日志
docker compose -f docker-compose.dev.yml logs -f rag-api
```

---

## ✅ 验证部署

### 1. 检查服务状态

```bash
# 健康检查
curl http://localhost:8000/

# 预期响应：
{
  "status": "running",
  "service": "RAG API",
  "version": "1.0.0",
  "architecture": "multi-tenant"
}
```

### 2. 检查存储连接

```bash
# 查看启动日志，应看到：
docker compose logs rag-api | grep "外部存储"

# 预期输出：
# 🔌 Using external storage backends:
#    - KV Storage: RedisKVStorage
#    - Vector Storage: QdrantVectorDBStorage
#    - Graph Storage: MemgraphStorage
#    DragonflyDB: redis://dragonflydb:6379/0
#    Qdrant: http://qdrant:6333
#    Memgraph: bolt://memgraph:7687
```

### 3. 测试存储连接

```bash
# 测试 DragonflyDB
docker compose exec dragonflydb redis-cli ping
# 预期输出：PONG

# 测试 Qdrant
curl http://localhost:6333/healthz
# 预期输出：{"status":"ok"}

# 测试 Memgraph
docker compose exec memgraph mgconsole --host 127.0.0.1 --port 7687 -c "RETURN 1;"
# 预期输出：1
```

### 4. 功能测试

```bash
# 上传测试文档
curl -X POST "http://localhost:8000/insert?tenant_id=test" \
  -F "file=@test.pdf"

# 查询测试
curl -X POST "http://localhost:8000/query?tenant_id=test" \
  -H "Content-Type: application/json" \
  -d '{"query": "测试查询", "mode": "naive"}'
```

---

## 🔧 性能优化

### DragonflyDB 优化

```yaml
# docker-compose.yml
dragonflydb:
  command: >
    dragonfly
    --dir=/data
    --snapshot_cron="0 */6 * * *"  # 每 6 小时快照
    --maxmemory=2048mb              # 最大内存 2GB
    --keys_output_limit=1024
```

### Qdrant 优化

```yaml
# docker-compose.yml
qdrant:
  environment:
    # 性能优化配置
    - QDRANT__SERVICE__GRPC_PORT=6334
    - QDRANT__SERVICE__HTTP_PORT=6333
    - QDRANT__LOG_LEVEL=INFO
```

### Memgraph 优化

```yaml
# docker-compose.yml
memgraph:
  environment:
    - MEMGRAPH_LOG_LEVEL=INFO
  deploy:
    resources:
      limits:
        memory: 4G  # 生产环境可增加内存限制
```

---

## 📊 监控和维护

### 查看存储使用情况

```bash
# DragonflyDB 内存使用
docker compose exec dragonflydb redis-cli INFO memory

# Qdrant 集合信息
curl http://localhost:6333/collections

# Memgraph 图统计
docker compose exec memgraph mgconsole -c "SHOW STORAGE INFO;"
```

### 数据备份

```bash
# DragonflyDB 快照备份（自动每 6 小时）
docker compose exec dragonflydb redis-cli BGSAVE

# Qdrant 备份
docker run --rm -v rag-api_qdrant_data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/qdrant_$(date +%Y%m%d_%H%M%S).tar.gz /data

# Memgraph 备份
docker compose exec memgraph mgconsole -c "CREATE SNAPSHOT;"
```

### 日志查看

```bash
# 查看所有服务日志
docker compose logs -f

# 查看特定服务日志
docker compose logs -f dragonflydb
docker compose logs -f qdrant
docker compose logs -f memgraph
```

---

## 🐛 故障排查

### 问题 1：服务启动失败

```bash
# 查看详细错误日志
docker compose logs rag-api

# 检查容器状态
docker compose ps

# 检查端口占用
netstat -tulpn | grep -E "6379|6333|7687"
```

### 问题 2：存储连接失败

```bash
# 检查存储服务状态
docker compose ps dragonflydb qdrant memgraph

# 测试网络连接
docker compose exec rag-api ping dragonflydb
docker compose exec rag-api ping qdrant
docker compose exec rag-api ping memgraph

# 检查配置是否正确
docker compose exec rag-api env | grep -E "REDIS_URI|QDRANT_URL|MEMGRAPH_URI"
```

### 问题 3：Embedding 维度错误

```bash
# 如果遇到维度不匹配错误，需要清理数据重建：

# 停止服务
docker compose down

# 删除所有 volume（清空数据库）
docker volume rm rag-api_dragonflydb_data rag-api_qdrant_data rag-api_memgraph_data

# 修改 .env 中的 EMBEDDING_DIM
# EMBEDDING_DIM=1024  # 或 4096

# 重新启动
docker compose up -d
```

### 问题 4：Qdrant 启动慢

```bash
# Qdrant 首次启动可能需要 30-60 秒初始化存储

# 查看启动日志
docker compose logs -f qdrant

# 等待 healthcheck 通过
docker compose ps qdrant
# 应显示 "healthy" 状态
```

---

## 🔒 生产环境安全

### 1. 启用认证

```bash
# Qdrant API Key（生产环境推荐）
# .env
QDRANT_API_KEY=your_secure_api_key_here

# Memgraph 认证（可选）
MEMGRAPH_USERNAME=admin
MEMGRAPH_PASSWORD=secure_password_here
```

### 2. 网络隔离

```yaml
# docker-compose.yml
# 确保存储服务只在内网可见
dragonflydb:
  ports:
    - "127.0.0.1:6379:6379"  # 只绑定本地

qdrant:
  ports:
    - "127.0.0.1:6333:6333"

memgraph:
  ports:
    - "127.0.0.1:7687:7687"
```

### 3. 数据持久化

```yaml
# docker-compose.yml
volumes:
  dragonflydb_data:
    driver: local
  qdrant_data:
    driver: local
  memgraph_data:
    driver: local
```

---

## 📖 参考资料

- **DragonflyDB 文档**: https://www.dragonflydb.io/docs
- **Qdrant 文档**: https://qdrant.tech/documentation/
- **Memgraph 文档**: https://memgraph.com/docs
- **架构设计文档**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **使用指南**: [USAGE.md](./USAGE.md)

---

## 🆘 需要帮助？

如果遇到问题：
1. 查看详细日志：`docker compose logs -f`
2. 检查服务状态：`docker compose ps`
3. 查阅文档：`docs/ARCHITECTURE.md`
4. 提交 Issue：https://github.com/BukeLy/rag-api/issues

---

**最后更新**：2025-11-01
**架构版本**：DragonflyDB + Qdrant + Memgraph
