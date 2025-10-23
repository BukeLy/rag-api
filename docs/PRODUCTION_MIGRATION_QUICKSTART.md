# 生产环境迁移 - 快速开始

**阅读时间**: 5 分钟
**面向人群**: 运维工程师、DevOps 工程师

---

## 📚 文档概览

本文档是 [PRODUCTION_MIGRATION_GUIDE.md](./PRODUCTION_MIGRATION_GUIDE.md) 的快速入门指南，帮助你快速理解迁移策略和下一步行动。

---

## 🎯 迁移目标

将 RAG API 从**单机文件存储**迁移到**云原生外部化存储**，支持水平扩展和高可用。

### 当前架构（main + dev 分支）

```
┌─────────────┐
│  FastAPI    │
│  容器       │
│  ↓          │
│ 文件存储    │  ← JSON/XML 文件（无法扩展）
│ (本地磁盘)  │
└─────────────┘
```

### 目标架构（main 分支生产环境）

```
┌─────────────┐
│  FastAPI    │
│  容器(s)    │  ← 可水平扩展（2-10 个容器）
└─────────────┘
       ↓
┌─────────────────────────────┐
│ ElastiCache │ Aurora │ Neo4j │  ← 外部化存储（AWS 托管）
│   Redis     │ PG    │ Aura  │
└─────────────────────────────┘
```

---

## 📈 迁移路线图（三阶段）

### ⚙️ 阶段 1：Docker Compose 外部化（1-2 周）

**目标**: 在 main 分支启用外部存储（Redis + PostgreSQL + Neo4j）

**操作**:
- 在 `docker-compose.yml` 中添加 Redis、PostgreSQL、Neo4j 服务
- 更新 `.env` 配置启用外部存储
- 运行数据迁移脚本

**适用环境**: EC2 或本地服务器（Docker Compose 部署）

**成本**: ~$10-50/月（EC2 + 自托管数据库）

**文档**: [阶段 1 详细步骤](./PRODUCTION_MIGRATION_GUIDE.md#阶段-1docker-compose-外部化存储)

---

### ☁️ 阶段 2：AWS 托管服务（2-3 周）

**目标**: 迁移到 AWS 托管服务（降低运维负担）

**操作**:
- 创建 Aurora Serverless PostgreSQL 集群
- 创建 ElastiCache Redis 集群
- 注册 Neo4j Aura（或使用 EC2 自托管 Neo4j）
- 更新 `.env` 配置指向 AWS 服务

**适用环境**: EC2 + AWS 托管数据库

**成本**: ~$165-670/月（EC2 + AWS 托管服务）

**文档**: [阶段 2 详细步骤](./PRODUCTION_MIGRATION_GUIDE.md#阶段-2aws-托管服务迁移)

---

### 🚀 阶段 3：AWS ECS Fargate（3-4 周）

**目标**: 无状态容器化部署，支持自动扩缩容

**操作**:
- 将镜像推送到 ECR
- 创建 ECS 任务定义和服务
- 配置 ALB 负载均衡器
- 配置自动扩缩容策略

**适用环境**: AWS ECS Fargate（完全托管容器服务）

**成本**: ~$250-990/月（ECS + AWS 托管服务）

**文档**: [阶段 3 详细步骤](./PRODUCTION_MIGRATION_GUIDE.md#阶段-3迁移到-aws-ecs)

---

## 🛠️ 快速开始：阶段 1 实施

### 前置条件

- [x] Docker 和 Docker Compose 已安装
- [x] 已有 `.env` 文件（从 `env.example` 复制）
- [x] 当前服务运行正常（文件存储模式）

### Step 1: 生成密码

```bash
# 生成强密码
NEO4J_PASSWORD=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# 添加到 .env 文件
echo "NEO4J_PASSWORD=$NEO4J_PASSWORD" >> .env
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env
```

### Step 2: 更新 docker-compose.yml

参考完整配置：[阶段 1 docker-compose.yml](./PRODUCTION_MIGRATION_GUIDE.md#11-更新-docker-composeyml)

**关键变更**：
- 添加 `redis`、`neo4j`、`postgres` 服务
- 配置健康检查和持久化卷
- 更新应用依赖关系

### Step 3: 更新 .env 配置

在 `.env` 中添加：

```bash
# 启用外部存储
USE_EXTERNAL_STORAGE=true
KV_STORAGE=RedisKVStorage
VECTOR_STORAGE=PGVectorStorage
GRAPH_STORAGE=Neo4JStorage

# 数据库连接（Docker Compose 模式）
REDIS_HOST=redis
POSTGRES_HOST=postgres
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
```

### Step 4: 启动外部存储服务

```bash
# 仅启动数据库服务（测试连接）
docker compose up -d redis neo4j postgres

# 等待健康检查通过
docker compose ps

# 验证连接
./scripts/health_check.sh
```

### Step 5: 数据迁移（可选）

如果你已有旧数据需要迁移：

```bash
# 预演迁移（不实际写入）
python scripts/migrate_to_external_storage.py --dry-run

# 执行迁移
python scripts/migrate_to_external_storage.py --execute
```

### Step 6: 启动应用

```bash
# 启动完整服务
docker compose up -d

# 查看日志
docker compose logs -f rag-api

# 验证外部存储已启用
docker compose logs rag-api | grep "external storage"
```

### Step 7: 功能验证

```bash
# 测试文档插入
curl -X POST http://localhost:8000/insert \
  -F "doc_id=test_1" \
  -F "file=@test.txt"

# 测试查询
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "测试查询", "mode": "naive"}'

# 运行健康检查
./scripts/health_check.sh --verbose
```

---

## 🔍 故障排查

### 问题 1: Redis 连接失败

**症状**: `ConnectionError: Error connecting to Redis`

**解决方案**:
```bash
# 检查 Redis 容器状态
docker compose ps redis

# 查看 Redis 日志
docker compose logs redis

# 测试连接
docker compose exec redis redis-cli ping
```

### 问题 2: PostgreSQL 扩展未安装

**症状**: `ERROR: extension "vector" does not exist`

**解决方案**:
```bash
# 进入 PostgreSQL 容器
docker compose exec postgres psql -U lightrag -d lightrag

# 手动安装扩展
CREATE EXTENSION IF NOT EXISTS vector;

# 验证
\dx
```

### 问题 3: Neo4j 连接超时

**症状**: `ServiceUnavailable: Unable to connect to Neo4j`

**解决方案**:
```bash
# 检查 Neo4j 容器状态
docker compose ps neo4j

# 查看 Neo4j 日志（等待启动完成）
docker compose logs neo4j

# Neo4j 启动需要 30-60 秒，请耐心等待健康检查通过
```

---

## 📊 性能对比

### 阶段 1（Docker Compose 外部化）

| 指标 | 文件存储 | 外部存储（Docker） | 提升 |
|------|---------|-------------------|------|
| **查询速度** | 15-20秒 | 10-15秒 | ↓ 25% |
| **并发支持** | 单线程 | 多连接池 | ↑ 3x |
| **水平扩展** | ❌ | ⚠️ 有限（单机） | - |
| **数据一致性** | 文件锁 | ACID 事务 | ✅ |
| **备份恢复** | 手动 | 自动快照 | ✅ |

### 阶段 2（AWS 托管服务）

| 指标 | Docker 外部存储 | AWS 托管服务 | 提升 |
|------|----------------|-------------|------|
| **可用性** | 单点故障 | 99.95% SLA | ✅ |
| **运维负担** | 需手动管理 | 自动维护 | ↓ 90% |
| **水平扩展** | 有限 | 自动扩缩容 | ✅ |
| **成本** | $50/月 | $200/月 | ↑ 4x |

### 阶段 3（AWS ECS）

| 指标 | EC2 单机 | ECS Fargate | 提升 |
|------|---------|-------------|------|
| **自动扩缩容** | ❌ | ✅ (2-10容器) | ✅ |
| **负载均衡** | 手动 | ALB 自动 | ✅ |
| **部署速度** | 手动 | CI/CD 自动 | ↓ 80% |
| **QPS 支持** | ~10 | ~100+ | ↑ 10x |

---

## 🔗 相关文档

- **详细实施指南**: [PRODUCTION_MIGRATION_GUIDE.md](./PRODUCTION_MIGRATION_GUIDE.md)
- **架构设计文档**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **性能优化指南**: [OPTIMIZATION_GUIDE.md](./OPTIMIZATION_GUIDE.md)
- **LightRAG 实现原理**: [LIGHTRAG_IMPLEMENTATION_GUIDE.md](./LIGHTRAG_IMPLEMENTATION_GUIDE.md)

---

## 📞 支持

遇到问题？

1. 查看 [详细实施指南](./PRODUCTION_MIGRATION_GUIDE.md) 的故障排查章节
2. 运行健康检查脚本：`./scripts/health_check.sh --verbose`
3. 查看日志：`docker compose logs -f`
4. 联系 Backend Team

---

## ✅ 检查清单

在开始迁移前，确保：

- [ ] 已阅读完整的 [迁移指南](./PRODUCTION_MIGRATION_GUIDE.md)
- [ ] 已备份当前数据（`./rag_local_storage/`）
- [ ] 已生成强密码并添加到 `.env`
- [ ] 已更新 `docker-compose.yml`
- [ ] 已在 dev 分支测试过外部存储配置
- [ ] 已准备回滚方案（保留文件存储备份）

---

**下一步**: 阅读 [完整迁移指南](./PRODUCTION_MIGRATION_GUIDE.md) 开始实施！

**维护者**: Backend Team
**最后更新**: 2025-10-23
