# RAG API 生产环境迁移指南

**版本**: 1.0
**更新日期**: 2025-10-23
**目标**: 从文件存储迁移到外部化存储，最终部署到 AWS ECS

---

## 📋 目录

1. [迁移概览](#迁移概览)
2. [阶段 1：Docker Compose 外部化存储](#阶段-1docker-compose-外部化存储)
3. [阶段 2：AWS 托管服务迁移](#阶段-2aws-托管服务迁移)
4. [阶段 3：迁移到 AWS ECS](#阶段-3迁移到-aws-ecs)
5. [数据迁移脚本](#数据迁移脚本)
6. [回滚方案](#回滚方案)
7. [监控和验证](#监控和验证)

---

## 迁移概览

### 架构演进路线

```
┌─────────────────────────────────────────────────────────────┐
│ 当前架构（dev + main 分支）                                  │
│ ┌─────────────┐                                             │
│ │  FastAPI    │                                             │
│ │  容器       │                                             │
│ │  ↓          │                                             │
│ │ 文件存储    │                                             │
│ │ (JSON/XML)  │                                             │
│ └─────────────┘                                             │
└─────────────────────────────────────────────────────────────┘
                      ↓ 阶段 1（1-2 周）
┌─────────────────────────────────────────────────────────────┐
│ Docker Compose 外部化（main 分支）                           │
│ ┌─────────────┐    ┌──────┐  ┌────────┐  ┌────────┐        │
│ │  FastAPI    │───→│Redis │  │Neo4j   │  │Postgres│        │
│ │  容器       │    └──────┘  └────────┘  └────────┘        │
│ └─────────────┘                                             │
│                     Docker Compose 本地网络                  │
└─────────────────────────────────────────────────────────────┘
                      ↓ 阶段 2（2-3 周）
┌─────────────────────────────────────────────────────────────┐
│ AWS 托管服务                                                 │
│ ┌─────────────┐                                             │
│ │  FastAPI    │                                             │
│ │  EC2 容器   │                                             │
│ └─────────────┘                                             │
│       ↓                                                      │
│ ┌─────────────────────────────────────────┐                 │
│ │ ElastiCache  │ Aurora    │ Neo4j Aura   │                 │
│ │ Redis        │ Serverless│ (Managed)    │                 │
│ └─────────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
                      ↓ 阶段 3（3-4 周）
┌─────────────────────────────────────────────────────────────┐
│ AWS ECS Fargate（无状态容器）                                │
│                                                              │
│      ALB（负载均衡）                                         │
│            ↓                                                 │
│   ┌────────────────┐                                        │
│   │  ECS Service   │                                        │
│   │  ┌──────────┐  │                                        │
│   │  │ Task 1   │  │   ← 自动扩缩容（2-10 个容器）          │
│   │  │ Task 2   │  │                                        │
│   │  │ Task ...│  │                                        │
│   │  └──────────┘  │                                        │
│   └────────────────┘                                        │
│            ↓                                                 │
│ ┌─────────────────────────────────────────┐                 │
│ │ ElastiCache  │ Aurora    │ Neo4j Aura   │                 │
│ │ Redis        │ Serverless│              │                 │
│ └─────────────────────────────────────────┘                 │
└─────────────────────────────────────────────────────────────┘
```

### 分支策略

| 分支 | 存储方式 | 用途 | 更新频率 |
|------|---------|------|---------|
| **dev** | 文件存储 | 开发环境，快速迭代 | 每天 |
| **main** | 外部存储 | 生产环境，稳定部署 | 每周 |

---

## 阶段 1：Docker Compose 外部化存储

**时间**: 1-2 周
**目标**: 在 main 分支启用外部存储服务（Redis + Neo4j + PostgreSQL）
**环境**: Docker Compose 本地部署（EC2 或本地服务器）

### 1.1 更新 docker-compose.yml

在 `docker-compose.yml` 中添加外部存储服务：

```yaml
version: '3.8'

services:
  # ==================== 应用服务 ====================
  rag-api:
    build:
      context: .
      dockerfile: Dockerfile
      cache_from:
        - type=registry,ref=rag-api-rag-api:latest
    container_name: rag-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      # 持久化输出文件（保留）
      - ./output:/app/output
      # 持久化日志（保留）
      - ./logs:/app/logs
      # 注意：移除 rag_local_storage 挂载，使用外部数据库
    environment:
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
      # 外部存储配置
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USERNAME=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD}
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=lightrag
      - POSTGRES_USER=lightrag
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    depends_on:
      redis:
        condition: service_healthy
      neo4j:
        condition: service_healthy
      postgres:
        condition: service_healthy
    networks:
      - rag-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  # ==================== Redis（KV 存储 + 缓存）====================
  redis:
    image: redis:7-alpine
    container_name: rag-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: >
      redis-server
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rag-network

  # ==================== Neo4j（图存储）====================
  neo4j:
    image: neo4j:5-community
    container_name: rag-neo4j
    restart: unless-stopped
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_server_memory_heap_initial__size=512m
      - NEO4J_server_memory_heap_max__size=1G
      - NEO4J_server_memory_pagecache_size=512m
      # 允许从容器外访问
      - NEO4J_server_default__listen__address=0.0.0.0
    healthcheck:
      test: ["CMD", "cypher-shell", "-u", "neo4j", "-p", "${NEO4J_PASSWORD}", "RETURN 1"]
      interval: 30s
      timeout: 10s
      retries: 5
    networks:
      - rag-network

  # ==================== PostgreSQL（向量存储）====================
  postgres:
    image: pgvector/pgvector:pg16
    container_name: rag-postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/init_postgres.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      - POSTGRES_DB=lightrag
      - POSTGRES_USER=lightrag
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_INITDB_ARGS=--encoding=UTF-8 --lc-collate=C --lc-ctype=C
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U lightrag -d lightrag"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - rag-network

  # ==================== Nginx 反向代理（生产环境）====================
  nginx:
    image: nginx:alpine
    container_name: rag-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./deploy/ssl:/etc/nginx/ssl:ro
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - rag-api
    networks:
      - rag-network
    profiles:
      - production

# ==================== 持久化卷 ====================
volumes:
  redis_data:
    driver: local
  neo4j_data:
    driver: local
  neo4j_logs:
    driver: local
  postgres_data:
    driver: local

# ==================== 网络 ====================
networks:
  rag-network:
    driver: bridge
```

### 1.2 创建 PostgreSQL 初始化脚本

创建 `scripts/init_postgres.sql`：

```sql
-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证扩展
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- 创建索引（加速向量搜索）
-- 注意：这些表由 LightRAG 自动创建，此处仅用于文档说明
-- CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings USING ivfflat (vector vector_cosine_ops);
```

### 1.3 更新 .env 配置

在 `.env` 文件中添加外部存储配置：

```bash
# ==================== 外部存储配置 ====================

# Redis（KV 存储 + 缓存）
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0

# Neo4j（图存储）
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password_here  # 修改为强密码

# PostgreSQL（向量存储）
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your_secure_password_here  # 修改为强密码

# ==================== LightRAG 存储配置 ====================

# 启用外部存储（生产环境）
USE_EXTERNAL_STORAGE=true

# KV 存储类型：JsonKVStorage（默认）或 RedisKVStorage
KV_STORAGE=RedisKVStorage

# 向量存储类型：NanoVectorDB（默认）或 PGVectorStorage
VECTOR_STORAGE=PGVectorStorage

# 图存储类型：NetworkXStorage（默认）或 Neo4JStorage
GRAPH_STORAGE=Neo4JStorage
```

### 1.4 更新 src/rag.py（支持外部存储）

在 `src/rag.py` 中添加外部存储支持：

```python
import os
from lightrag import LightRAG

# 读取外部存储配置
use_external_storage = os.getenv("USE_EXTERNAL_STORAGE", "false").lower() == "true"
kv_storage = os.getenv("KV_STORAGE", "JsonKVStorage")
vector_storage = os.getenv("VECTOR_STORAGE", "NanoVectorDB")
graph_storage = os.getenv("GRAPH_STORAGE", "NetworkXStorage")

# 根据配置创建 LightRAG 实例
if use_external_storage:
    logger.info("🔌 Using external storage backends:")
    logger.info(f"   - KV Storage: {kv_storage}")
    logger.info(f"   - Vector Storage: {vector_storage}")
    logger.info(f"   - Graph Storage: {graph_storage}")

    # 准备存储配置
    storage_kwargs = {}

    # Redis KV 存储配置
    if kv_storage == "RedisKVStorage":
        storage_kwargs["kv_storage"] = "RedisKVStorage"
        storage_kwargs["kv_storage_cls_kwargs"] = {
            "host": os.getenv("REDIS_HOST", "localhost"),
            "port": int(os.getenv("REDIS_PORT", "6379")),
            "db": int(os.getenv("REDIS_DB", "0"))
        }

    # PostgreSQL 向量存储配置
    if vector_storage == "PGVectorStorage":
        storage_kwargs["vector_storage"] = "PGVectorStorage"
        storage_kwargs["vector_storage_cls_kwargs"] = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "database": os.getenv("POSTGRES_DB", "lightrag"),
            "user": os.getenv("POSTGRES_USER", "lightrag"),
            "password": os.getenv("POSTGRES_PASSWORD", "")
        }

    # Neo4j 图存储配置
    if graph_storage == "Neo4JStorage":
        storage_kwargs["graph_storage"] = "Neo4JStorage"
        storage_kwargs["graph_storage_cls_kwargs"] = {
            "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            "user": os.getenv("NEO4J_USERNAME", "neo4j"),
            "password": os.getenv("NEO4J_PASSWORD", "")
        }

    global_lightrag_instance = LightRAG(
        working_dir="./rag_local_storage",  # 仅用于临时文件
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        llm_model_max_async=max_async,
        **storage_kwargs  # 应用外部存储配置
    )
else:
    logger.info("📁 Using local file storage (default)")
    global_lightrag_instance = LightRAG(
        working_dir="./rag_local_storage",
        llm_model_func=llm_model_func,
        embedding_func=embedding_func,
        llm_model_max_async=max_async,
    )
```

### 1.5 部署步骤

#### Step 1: 生成密码

```bash
# 生成强密码
openssl rand -base64 32 > .secrets
NEO4J_PASSWORD=$(head -n 1 .secrets)
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# 更新 .env 文件
echo "NEO4J_PASSWORD=$NEO4J_PASSWORD" >> .env
echo "POSTGRES_PASSWORD=$POSTGRES_PASSWORD" >> .env
```

#### Step 2: 启动外部存储服务

```bash
# 仅启动数据库服务（测试连接）
docker compose up -d redis neo4j postgres

# 等待健康检查通过
docker compose ps

# 查看日志
docker compose logs redis
docker compose logs neo4j
docker compose logs postgres
```

#### Step 3: 验证数据库连接

```bash
# 测试 Redis
docker compose exec redis redis-cli ping
# 预期输出: PONG

# 测试 Neo4j
docker compose exec neo4j cypher-shell -u neo4j -p your_password "RETURN 1"
# 预期输出: 1

# 测试 PostgreSQL
docker compose exec postgres psql -U lightrag -d lightrag -c "SELECT version();"
# 预期输出: PostgreSQL 16.x + pgvector
```

#### Step 4: 数据迁移（见 [数据迁移脚本](#数据迁移脚本)）

```bash
# 运行迁移脚本
python scripts/migrate_to_external_storage.py --dry-run
python scripts/migrate_to_external_storage.py --execute
```

#### Step 5: 启动应用

```bash
# 启动完整服务
docker compose up -d

# 查看应用日志
docker compose logs -f rag-api

# 验证外部存储已启用
docker compose logs rag-api | grep "external storage"
```

#### Step 6: 功能验证

```bash
# 测试文档插入
curl -X POST http://localhost:8000/insert \
  -F "doc_id=test_external" \
  -F "file=@test.txt"

# 测试查询
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "测试查询", "mode": "naive"}'

# 检查数据已存储到外部数据库
docker compose exec redis redis-cli DBSIZE
docker compose exec neo4j cypher-shell -u neo4j -p your_password "MATCH (n) RETURN count(n)"
docker compose exec postgres psql -U lightrag -d lightrag -c "SELECT COUNT(*) FROM vectors;"
```

### 1.6 监控和调优

#### 资源监控

```bash
# 查看容器资源占用
docker stats

# 查看数据库大小
docker compose exec postgres psql -U lightrag -d lightrag -c "
SELECT pg_size_pretty(pg_database_size('lightrag'));
"

docker compose exec neo4j cypher-shell -u neo4j -p your_password "
CALL dbms.queryJmx('org.neo4j:instance=kernel#0,name=Store file sizes')
YIELD attributes
RETURN attributes.TotalStoreSize.value;
"
```

#### 性能调优

**Redis 调优**：
```bash
# 编辑 docker-compose.yml，调整 Redis 内存限制
command: >
  redis-server
  --appendonly yes
  --maxmemory 1gb           # 增加内存限制
  --maxmemory-policy allkeys-lru
```

**Neo4j 调优**：
```yaml
environment:
  - NEO4J_server_memory_heap_max__size=2G  # 增加堆内存
  - NEO4J_server_memory_pagecache_size=1G  # 增加页缓存
```

**PostgreSQL 调优**：
```bash
# 编辑 postgresql.conf（通过卷挂载）
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
```

---

## 阶段 2：AWS 托管服务迁移

**时间**: 2-3 周
**目标**: 迁移到 AWS 托管服务（ElastiCache + Aurora Serverless + Neo4j Aura）
**环境**: EC2 + AWS 托管数据库

### 2.1 AWS 资源创建

#### 创建 Aurora Serverless v2 集群

```bash
# 使用 AWS CLI 创建 Aurora 集群
aws rds create-db-cluster \
  --db-cluster-identifier lightrag-aurora \
  --engine aurora-postgresql \
  --engine-version 16.1 \
  --master-username lightrag \
  --master-user-password your_secure_password \
  --database-name lightrag \
  --serverless-v2-scaling-configuration MinCapacity=0.5,MaxCapacity=16 \
  --enable-http-endpoint \
  --vpc-security-group-ids sg-xxxxxx \
  --db-subnet-group-name your-subnet-group

# 创建实例（Serverless v2 需要实例）
aws rds create-db-instance \
  --db-instance-identifier lightrag-aurora-instance-1 \
  --db-cluster-identifier lightrag-aurora \
  --db-instance-class db.serverless \
  --engine aurora-postgresql

# 安装 pgvector 扩展
psql -h lightrag-aurora.cluster-xxxxxx.us-east-1.rds.amazonaws.com \
     -U lightrag \
     -d lightrag \
     -c "CREATE EXTENSION vector;"
```

#### 创建 ElastiCache Redis 集群

```bash
# 创建 Redis 集群（Serverless 模式）
aws elasticache create-serverless-cache \
  --serverless-cache-name lightrag-redis \
  --engine redis \
  --serverless-cache-usage-limits DataStorage={Maximum=1,Unit=GB} \
  --security-group-ids sg-xxxxxx \
  --subnet-ids subnet-xxxxxx subnet-yyyyyy
```

#### 注册 Neo4j Aura（托管图数据库）

```bash
# 访问 https://console.neo4j.io/ 创建实例
# 选择：Professional（$65/月）或 Enterprise（$200/月）
# 记录连接信息：
# - URI: neo4j+s://xxxxx.databases.neo4j.io
# - Username: neo4j
# - Password: generated_password
```

### 2.2 更新 .env 配置（AWS 托管服务）

```bash
# ==================== AWS 托管服务配置 ====================

# ElastiCache Redis
REDIS_HOST=lightrag-redis.xxxxxx.cache.amazonaws.com
REDIS_PORT=6379
REDIS_SSL=true  # ElastiCache 建议启用 SSL

# Aurora Serverless PostgreSQL
POSTGRES_HOST=lightrag-aurora.cluster-xxxxxx.us-east-1.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DB=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your_aurora_password
POSTGRES_SSLMODE=require  # Aurora 强制 SSL

# Neo4j Aura
NEO4J_URI=neo4j+s://xxxxx.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_aura_password
NEO4J_DATABASE=neo4j  # Aura 默认数据库名

# 启用外部存储
USE_EXTERNAL_STORAGE=true
KV_STORAGE=RedisKVStorage
VECTOR_STORAGE=PGVectorStorage
GRAPH_STORAGE=Neo4JStorage
```

### 2.3 数据迁移（Docker Compose → AWS）

```bash
# Step 1: 备份 Docker Compose 数据
docker compose exec redis redis-cli --rdb /data/dump.rdb
docker compose exec postgres pg_dump -U lightrag lightrag > backup_postgres.sql
docker compose exec neo4j neo4j-admin database dump neo4j --to-path=/tmp/neo4j-backup

# Step 2: 恢复到 AWS 服务
# Redis: 使用 redis-cli --rdb 导入
cat backup_redis.rdb | redis-cli -h lightrag-redis.xxxxxx.cache.amazonaws.com --pipe

# PostgreSQL: 使用 psql 导入
psql -h lightrag-aurora.cluster-xxxxxx.us-east-1.rds.amazonaws.com \
     -U lightrag -d lightrag < backup_postgres.sql

# Neo4j: 使用 Neo4j Aura 控制台导入
# 访问控制台 → Import → 上传 dump 文件
```

### 2.4 更新 docker-compose.yml（移除本地数据库）

```yaml
version: '3.8'

services:
  # 仅保留应用服务，移除 Redis/Neo4j/PostgreSQL
  rag-api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: rag-api
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./output:/app/output
      - ./logs:/app/logs
    environment:
      - TZ=Asia/Shanghai
      - PYTHONUNBUFFERED=1
      # AWS 托管服务配置（从 .env 读取）
    networks:
      - rag-network

  nginx:
    image: nginx:alpine
    container_name: rag-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./deploy/ssl:/etc/nginx/ssl:ro
    depends_on:
      - rag-api
    networks:
      - rag-network

networks:
  rag-network:
    driver: bridge
```

### 2.5 成本估算（AWS 托管服务）

| 服务 | 类型 | 配置 | 月成本 |
|------|------|------|--------|
| **Aurora Serverless v2** | PostgreSQL | 0.5-16 ACU | $40-500 |
| **ElastiCache Serverless** | Redis | 1GB 数据 | $40-80 |
| **Neo4j Aura** | Professional | 8GB 存储 | $65 |
| **EC2** | t3.small | 应用容器 | $10-15 |
| **数据传输** | 出站流量 | ~100GB | $10 |
| **合计** | - | - | **$165-670/月** |

---

## 阶段 3：迁移到 AWS ECS

**时间**: 3-4 周
**目标**: 无状态容器化部署，支持自动扩缩容
**环境**: AWS ECS Fargate + ALB + 托管数据库

### 3.1 架构设计

```
Internet
    ↓
Route 53 (DNS)
    ↓
CloudFront (CDN，可选)
    ↓
Application Load Balancer (ALB)
    ↓
┌─────────────────────────────────────────┐
│         ECS Service                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐ │
│  │ Task 1  │  │ Task 2  │  │ Task 3  │ │ ← 自动扩缩容（2-10 个任务）
│  └─────────┘  └─────────┘  └─────────┘ │
└─────────────────────────────────────────┘
    ↓              ↓              ↓
┌───────────────────────────────────────────┐
│   VPC (Private Subnet)                    │
│  ┌──────────┐  ┌────────┐  ┌──────────┐  │
│  │ElastiCache│ │Aurora  │  │Neo4j Aura│  │
│  │  Redis   │  │Postgres│  │ (外部)   │  │
│  └──────────┘  └────────┘  └──────────┘  │
└───────────────────────────────────────────┘
```

### 3.2 创建 ECR 仓库

```bash
# 创建 ECR 仓库
aws ecr create-repository --repository-name rag-api

# 登录 ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-east-1.amazonaws.com

# 构建并推送镜像
docker build -t rag-api:latest .
docker tag rag-api:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
```

### 3.3 创建 ECS 任务定义

创建 `ecs-task-definition.json`：

```json
{
  "family": "rag-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "rag-api",
      "image": "123456789012.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "TZ", "value": "Asia/Shanghai"},
        {"name": "PYTHONUNBUFFERED", "value": "1"},
        {"name": "USE_EXTERNAL_STORAGE", "value": "true"}
      ],
      "secrets": [
        {
          "name": "ARK_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:rag-api/ark-api-key"
        },
        {
          "name": "REDIS_HOST",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:rag-api/redis-host"
        },
        {
          "name": "POSTGRES_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:rag-api/postgres-password"
        },
        {
          "name": "NEO4J_PASSWORD",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:rag-api/neo4j-password"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/rag-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/ || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

注册任务定义：

```bash
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json
```

### 3.4 创建 Secrets Manager 密钥

```bash
# 创建密钥
aws secretsmanager create-secret \
  --name rag-api/ark-api-key \
  --secret-string "your_ark_api_key"

aws secretsmanager create-secret \
  --name rag-api/redis-host \
  --secret-string "lightrag-redis.xxxxxx.cache.amazonaws.com"

aws secretsmanager create-secret \
  --name rag-api/postgres-password \
  --secret-string "your_postgres_password"

aws secretsmanager create-secret \
  --name rag-api/neo4j-password \
  --secret-string "your_neo4j_password"
```

### 3.5 创建 Application Load Balancer

```bash
# 创建 ALB
aws elbv2 create-load-balancer \
  --name rag-api-alb \
  --subnets subnet-xxxxxx subnet-yyyyyy \
  --security-groups sg-xxxxxx \
  --scheme internet-facing

# 创建目标组
aws elbv2 create-target-group \
  --name rag-api-tg \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-xxxxxx \
  --target-type ip \
  --health-check-path / \
  --health-check-interval-seconds 30

# 创建监听器
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/rag-api-alb/xxxxx \
  --protocol HTTP \
  --port 80 \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/rag-api-tg/xxxxx
```

### 3.6 创建 ECS 服务

```bash
# 创建 ECS 集群
aws ecs create-cluster --cluster-name rag-api-cluster

# 创建 ECS 服务（带自动扩缩容）
aws ecs create-service \
  --cluster rag-api-cluster \
  --service-name rag-api-service \
  --task-definition rag-api:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --platform-version LATEST \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxx,subnet-yyyyyy],securityGroups=[sg-xxxxxx],assignPublicIp=DISABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/rag-api-tg/xxxxx,containerName=rag-api,containerPort=8000" \
  --health-check-grace-period-seconds 60
```

### 3.7 配置自动扩缩容

```bash
# 注册可扩展目标
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --resource-id service/rag-api-cluster/rag-api-service \
  --scalable-dimension ecs:service:DesiredCount \
  --min-capacity 2 \
  --max-capacity 10

# 创建 CPU 使用率扩缩容策略
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/rag-api-cluster/rag-api-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name cpu-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }'

# 创建内存使用率扩缩容策略
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --resource-id service/rag-api-cluster/rag-api-service \
  --scalable-dimension ecs:service:DesiredCount \
  --policy-name memory-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 80.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageMemoryUtilization"
    },
    "ScaleInCooldown": 300,
    "ScaleOutCooldown": 60
  }'
```

### 3.8 CI/CD 集成（GitHub Actions）

创建 `.github/workflows/deploy-ecs.yml`：

```yaml
name: Deploy to ECS

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1

      - name: Build, tag, and push image to Amazon ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: rag-api
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Update ECS service
        run: |
          aws ecs update-service \
            --cluster rag-api-cluster \
            --service rag-api-service \
            --force-new-deployment
```

### 3.9 成本估算（AWS ECS 部署）

| 服务 | 类型 | 配置 | 月成本 |
|------|------|------|--------|
| **ECS Fargate** | 计算资源 | 2-10 任务（1 vCPU, 2GB） | $60-300 |
| **ALB** | 负载均衡器 | 标准配置 | $20 |
| **Aurora Serverless v2** | PostgreSQL | 0.5-16 ACU | $40-500 |
| **ElastiCache Serverless** | Redis | 1GB 数据 | $40-80 |
| **Neo4j Aura** | Professional | 8GB 存储 | $65 |
| **CloudWatch Logs** | 日志存储 | 10GB/月 | $5 |
| **数据传输** | 出站流量 | ~200GB | $20 |
| **合计** | - | - | **$250-990/月** |

---

## 数据迁移脚本

创建 `scripts/migrate_to_external_storage.py`：

```python
#!/usr/bin/env python3
"""
数据迁移脚本：文件存储 → 外部数据库

使用方法:
  python scripts/migrate_to_external_storage.py --dry-run    # 预演
  python scripts/migrate_to_external_storage.py --execute    # 执行
"""

import os
import json
import asyncio
import argparse
from pathlib import Path
from typing import Dict, List

# 导入 LightRAG 存储后端
from lightrag.kg.redis_impl import RedisKVStorage
from lightrag.kg.postgres_impl import PGVectorStorage
from lightrag.kg.neo4j_impl import Neo4JStorage


class DataMigrator:
    def __init__(self, source_dir: str, dry_run: bool = True):
        self.source_dir = Path(source_dir)
        self.dry_run = dry_run
        self.stats = {
            "kv_entries": 0,
            "vectors": 0,
            "graph_nodes": 0,
            "graph_edges": 0
        }

    async def migrate_kv_storage(self):
        """迁移 KV 存储：JSON → Redis"""
        print("\n🔄 Migrating KV storage (JSON → Redis)...")

        # 读取源文件
        kv_files = [
            "kv_store_full_docs.json",
            "kv_store_full_entities.json",
            "kv_store_full_relations.json",
            "kv_store_text_chunks.json",
        ]

        if self.dry_run:
            for file in kv_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    with open(file_path) as f:
                        data = json.load(f)
                        self.stats["kv_entries"] += len(data)
                        print(f"  ✓ Found {len(data)} entries in {file}")
        else:
            # 实际迁移
            redis = RedisKVStorage(
                namespace="lightrag",
                global_config={},
                embedding_func=None,
                host=os.getenv("REDIS_HOST"),
                port=int(os.getenv("REDIS_PORT", "6379"))
            )

            for file in kv_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    with open(file_path) as f:
                        data = json.load(f)
                        for key, value in data.items():
                            await redis.set(key, value)
                        self.stats["kv_entries"] += len(data)
                        print(f"  ✓ Migrated {len(data)} entries from {file}")

    async def migrate_vector_storage(self):
        """迁移向量存储：NanoVectorDB → PostgreSQL"""
        print("\n🔄 Migrating vector storage (JSON → PostgreSQL)...")

        vector_files = [
            "vdb_entities.json",
            "vdb_relationships.json",
            "vdb_chunks.json"
        ]

        if self.dry_run:
            for file in vector_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    with open(file_path) as f:
                        data = json.load(f)
                        self.stats["vectors"] += len(data)
                        print(f"  ✓ Found {len(data)} vectors in {file}")
        else:
            # 实际迁移
            pg_vector = PGVectorStorage(
                namespace="lightrag",
                global_config={},
                embedding_func=None,
                host=os.getenv("POSTGRES_HOST"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD")
            )

            await pg_vector.initialize()

            for file in vector_files:
                file_path = self.source_dir / file
                if file_path.exists():
                    with open(file_path) as f:
                        data = json.load(f)
                        for key, item in data.items():
                            await pg_vector.insert(
                                id=key,
                                embedding=item["embedding"],
                                metadata=item.get("metadata", {})
                            )
                        self.stats["vectors"] += len(data)
                        print(f"  ✓ Migrated {len(data)} vectors from {file}")

    async def migrate_graph_storage(self):
        """迁移图存储：NetworkX/GraphML → Neo4j"""
        print("\n🔄 Migrating graph storage (GraphML → Neo4j)...")

        graph_file = self.source_dir / "graph_chunk_entity_relation.graphml"

        if not graph_file.exists():
            print("  ⚠️  GraphML file not found, skipping graph migration")
            return

        if self.dry_run:
            import networkx as nx
            G = nx.read_graphml(graph_file)
            self.stats["graph_nodes"] = G.number_of_nodes()
            self.stats["graph_edges"] = G.number_of_edges()
            print(f"  ✓ Found {self.stats['graph_nodes']} nodes and {self.stats['graph_edges']} edges")
        else:
            # 实际迁移
            import networkx as nx
            from neo4j import AsyncGraphDatabase

            G = nx.read_graphml(graph_file)

            driver = AsyncGraphDatabase.driver(
                os.getenv("NEO4J_URI"),
                auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
            )

            async with driver.session() as session:
                # 创建节点
                for node_id, node_data in G.nodes(data=True):
                    await session.run(
                        "MERGE (n:Entity {id: $id}) SET n += $properties",
                        id=node_id,
                        properties=node_data
                    )
                self.stats["graph_nodes"] = G.number_of_nodes()

                # 创建边
                for src, tgt, edge_data in G.edges(data=True):
                    await session.run(
                        "MATCH (a:Entity {id: $src}), (b:Entity {id: $tgt}) "
                        "MERGE (a)-[r:RELATES_TO]->(b) SET r += $properties",
                        src=src,
                        tgt=tgt,
                        properties=edge_data
                    )
                self.stats["graph_edges"] = G.number_of_edges()

            await driver.close()
            print(f"  ✓ Migrated {self.stats['graph_nodes']} nodes and {self.stats['graph_edges']} edges")

    async def run(self):
        """执行完整迁移"""
        print("=" * 70)
        print(f"{'DRY RUN MODE' if self.dry_run else 'LIVE MIGRATION MODE'}")
        print("=" * 70)

        await self.migrate_kv_storage()
        await self.migrate_vector_storage()
        await self.migrate_graph_storage()

        print("\n" + "=" * 70)
        print("📊 Migration Summary")
        print("=" * 70)
        print(f"  KV Entries:   {self.stats['kv_entries']}")
        print(f"  Vectors:      {self.stats['vectors']}")
        print(f"  Graph Nodes:  {self.stats['graph_nodes']}")
        print(f"  Graph Edges:  {self.stats['graph_edges']}")
        print("=" * 70)

        if self.dry_run:
            print("\n✅ Dry run completed. Run with --execute to perform actual migration.")
        else:
            print("\n✅ Migration completed successfully!")


async def main():
    parser = argparse.ArgumentParser(description="Migrate LightRAG data to external storage")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writing data")
    parser.add_argument("--execute", action="store_true", help="Execute actual migration")
    parser.add_argument("--source-dir", default="./rag_local_storage", help="Source directory for file storage")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("❌ Error: Must specify either --dry-run or --execute")
        return

    migrator = DataMigrator(
        source_dir=args.source_dir,
        dry_run=args.dry_run
    )

    await migrator.run()


if __name__ == "__main__":
    asyncio.run(main())
```

---

## 回滚方案

### 阶段 1 回滚（外部存储 → 文件存储）

```bash
# Step 1: 备份外部数据库
docker compose exec redis redis-cli SAVE
docker compose exec postgres pg_dump -U lightrag lightrag > backup.sql
docker compose exec neo4j neo4j-admin database dump neo4j --to-path=/tmp/backup

# Step 2: 停止服务
docker compose down

# Step 3: 恢复 docker-compose.yml 到文件存储版本
git checkout HEAD~1 docker-compose.yml

# Step 4: 更新 .env
USE_EXTERNAL_STORAGE=false

# Step 5: 启动服务
docker compose up -d
```

### 阶段 2 回滚（AWS 托管 → Docker Compose）

```bash
# Step 1: 从 AWS 导出数据
aws elasticache create-snapshot \
  --snapshot-name lightrag-backup-$(date +%Y%m%d)

aws rds create-db-snapshot \
  --db-snapshot-identifier lightrag-backup-$(date +%Y%m%d)

# Step 2: 启动本地 Docker Compose 数据库
docker compose up -d redis neo4j postgres

# Step 3: 恢复数据（使用备份脚本）
python scripts/restore_from_aws.py

# Step 4: 更新 .env 指向本地服务
REDIS_HOST=localhost
POSTGRES_HOST=localhost
NEO4J_URI=bolt://localhost:7687
```

### 阶段 3 回滚（ECS → EC2）

```bash
# Step 1: 停止 ECS 服务
aws ecs update-service \
  --cluster rag-api-cluster \
  --service rag-api-service \
  --desired-count 0

# Step 2: 在 EC2 上启动 Docker Compose
ssh ec2-user@your-ec2-instance
cd /app/rag-api
docker compose up -d

# Step 3: 更新 DNS（指向 EC2 IP）
aws route53 change-resource-record-sets \
  --hosted-zone-id Z123456 \
  --change-batch file://update-dns-to-ec2.json
```

---

## 监控和验证

### CloudWatch 监控指标

```bash
# ECS 任务 CPU 使用率
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=rag-api-service \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average

# Aurora 数据库连接数
aws cloudwatch get-metric-statistics \
  --namespace AWS/RDS \
  --metric-name DatabaseConnections \
  --dimensions Name=DBClusterIdentifier,Value=lightrag-aurora \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average
```

### 健康检查脚本

创建 `scripts/health_check.sh`：

```bash
#!/bin/bash

echo "🏥 RAG API Health Check"
echo "========================"

# 检查 API 健康状态
API_URL=${API_URL:-"http://localhost:8000"}
echo -n "API Health: "
curl -sf $API_URL/ > /dev/null && echo "✅ OK" || echo "❌ FAIL"

# 检查 Redis 连接
echo -n "Redis: "
redis-cli -h ${REDIS_HOST:-localhost} ping > /dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL"

# 检查 PostgreSQL 连接
echo -n "PostgreSQL: "
pg_isready -h ${POSTGRES_HOST:-localhost} -U lightrag > /dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL"

# 检查 Neo4j 连接
echo -n "Neo4j: "
cypher-shell -a ${NEO4J_URI:-bolt://localhost:7687} \
  -u ${NEO4J_USERNAME:-neo4j} \
  -p ${NEO4J_PASSWORD} \
  "RETURN 1" > /dev/null 2>&1 && echo "✅ OK" || echo "❌ FAIL"

# 测试查询功能
echo -n "Query Test: "
RESPONSE=$(curl -sf -X POST $API_URL/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "mode": "naive"}')

if [ -n "$RESPONSE" ]; then
  echo "✅ OK"
else
  echo "❌ FAIL"
fi
```

---

## 附录

### A. Terraform 基础设施代码示例

创建 `terraform/main.tf`：

```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# VPC 和子网
module "vpc" {
  source = "terraform-aws-modules/vpc/aws"

  name = "rag-api-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["us-east-1a", "us-east-1b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true
}

# ElastiCache Redis
resource "aws_elasticache_serverless_cache" "redis" {
  engine = "redis"
  name   = "lightrag-redis"

  cache_usage_limits {
    data_storage {
      maximum = 1
      unit    = "GB"
    }
  }

  security_group_ids = [aws_security_group.redis.id]
  subnet_ids         = module.vpc.private_subnets
}

# Aurora Serverless v2
resource "aws_rds_cluster" "aurora" {
  cluster_identifier     = "lightrag-aurora"
  engine                 = "aurora-postgresql"
  engine_version         = "16.1"
  database_name          = "lightrag"
  master_username        = "lightrag"
  master_password        = var.postgres_password

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 16
  }

  vpc_security_group_ids = [aws_security_group.aurora.id]
  db_subnet_group_name   = aws_db_subnet_group.aurora.name
}

resource "aws_rds_cluster_instance" "aurora_instance" {
  identifier         = "lightrag-aurora-instance-1"
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
}

# ECS 集群
resource "aws_ecs_cluster" "main" {
  name = "rag-api-cluster"
}

# ECS 任务定义
resource "aws_ecs_task_definition" "rag_api" {
  family                   = "rag-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn

  container_definitions = jsonencode([
    {
      name  = "rag-api"
      image = "${aws_ecr_repository.rag_api.repository_url}:latest"
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]
      environment = [
        {name = "USE_EXTERNAL_STORAGE", value = "true"},
        {name = "REDIS_HOST", value = aws_elasticache_serverless_cache.redis.endpoint[0].address}
      ]
    }
  ])
}

# ECS 服务
resource "aws_ecs_service" "rag_api" {
  name            = "rag-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.rag_api.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = module.vpc.private_subnets
    security_groups  = [aws_security_group.rag_api.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.rag_api.arn
    container_name   = "rag-api"
    container_port   = 8000
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "rag-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "rag_api" {
  name        = "rag-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    path                = "/"
    healthy_threshold   = 2
    unhealthy_threshold = 10
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.rag_api.arn
  }
}
```

### B. 成本优化建议

1. **使用 Savings Plans**：承诺 1 年使用，节省 30-50%
2. **Aurora Serverless v2 暂停策略**：设置 `min_capacity=0.5` 避免完全暂停
3. **ElastiCache 数据分层**：使用 Serverless 模式，按需付费
4. **ECS Spot 实例**：非关键任务使用 Spot，节省 70%
5. **CloudFront CDN**：静态资源使用 CDN，减少数据传输成本

### C. 安全检查清单

- [ ] 所有密码使用 AWS Secrets Manager 管理
- [ ] 数据库连接强制 SSL/TLS
- [ ] ECS 任务使用私有子网，通过 NAT 网关访问外网
- [ ] 安全组限制入站流量（ALB → ECS → 数据库）
- [ ] 启用 CloudTrail 审计日志
- [ ] 配置 AWS WAF 防止常见攻击
- [ ] 启用 GuardDuty 威胁检测

---

## 总结

本指南提供了从文件存储到 AWS ECS 部署的完整迁移路径，分为三个阶段：

1. **阶段 1（1-2 周）**：Docker Compose 外部化存储（本地测试）
2. **阶段 2（2-3 周）**：AWS 托管服务迁移（高可用）
3. **阶段 3（3-4 周）**：ECS Fargate 部署（无状态、自动扩缩容）

每个阶段都有详细的步骤、配置示例、数据迁移脚本和回滚方案，确保安全、可控的生产环境迁移。

**下一步行动**：
1. 在 dev 分支保持文件存储（快速开发）
2. 在 main 分支实施阶段 1（Docker Compose 外部化）
3. 验证功能和性能后，逐步推进阶段 2 和 3

---

**维护者**: Backend Team
**最后更新**: 2025-10-23
**版本**: 1.0
