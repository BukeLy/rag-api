# AWS 云服务迁移指南

> **目标**：从自建开源架构迁移到 AWS 托管服务，实现高可用、自动扩展和低运维成本。

## 📊 架构对比

### 当前自建架构 vs AWS 托管服务

| 组件类型 | 自建方案 | AWS 托管服务 | 迁移难度 | 优先级 |
|---------|---------|-------------|---------|--------|
| **KV 存储** | Redis/DragonflyDB | ElastiCache for Redis | ⭐ 简单 | 高 |
| **向量存储** | Qdrant/pgvector | 自建 Qdrant on ECS 或 RDS+pgvector | ⭐⭐ 中等 | 高 |
| **图存储** | Neo4j/Memgraph | Neptune 或 自建 on EC2 | ⭐⭐⭐ 复杂 | 中 |
| **API 服务** | Docker Compose | ECS Fargate / EKS | ⭐⭐ 中等 | 高 |
| **负载均衡** | Nginx | Application Load Balancer (ALB) | ⭐ 简单 | 高 |
| **对象存储** | Local Volume | S3 | ⭐ 简单 | 中 |

---

## 🎯 推荐迁移方案

### 方案 A：全托管方案 ⭐⭐⭐⭐⭐ （推荐）

**适合**：希望最小化运维成本，快速上线

```
┌─────────────────────────────────────────────────┐
│    CloudFront (CDN) + Route 53 (DNS)            │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│  Application Load Balancer (ALB)                │
│  - 自动扩展                                      │
│  - HTTPS 终止 (ACM 证书)                         │
│  - 健康检查                                      │
└────────────────────┬────────────────────────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐
│ ECS       │  │ ECS       │  │ ECS       │
│ Fargate   │  │ Fargate   │  │ Fargate   │
│ Task 1    │  │ Task 2    │  │ Task 3    │
│ (rag-api) │  │ (rag-api) │  │ (rag-api) │
└─────┬─────┘  └─────┬─────┘  └─────┬─────┘
      │              │              │
      └──────────────┼──────────────┘
                     │
   ┌─────────────────┼─────────────────┐
   │                 │                 │
┌──▼──────────┐  ┌───▼────────────┐  ┌▼──────────┐
│ElastiCache  │  │ ECS Fargate    │  │  Neptune  │
│ for Redis   │  │ + Qdrant       │  │  或 RDS   │
│ (Cluster)   │  │ (Cluster)      │  │  pgvector │
│             │  │                │  │           │
│ 自动故障转移 │  │  无维度限制     │  │ 高可用     │
└─────────────┘  └────────────────┘  └───────────┘
       │                  │                 │
       └──────────────────┼─────────────────┘
                          │
                    ┌─────▼─────┐
                    │    S3     │
                    │  (备份)    │
                    └───────────┘
```

### 核心服务映射

#### 1️⃣ KV 存储：Redis/DragonflyDB → **ElastiCache for Redis**

**AWS 服务**：`Amazon ElastiCache for Redis`

**推荐配置**：
- **实例类型**：`cache.r7g.large` (2 vCPU, 13.07 GiB)
- **集群模式**：启用（分片集群）
- **副本数**：每分片 2 个副本（主 + 2 只读）
- **自动故障转移**：启用
- **备份**：自动快照（保留 7 天）

**价格**（us-east-1）：
- 单节点：$0.218/小时 ≈ **$158/月**
- 集群（3 分片 + 6 副本）：≈ **$1,426/月**

**环境变量**：
```bash
# 单节点模式
REDIS_URI=redis://your-elasticache-endpoint.cache.amazonaws.com:6379/0

# 集群模式
REDIS_URI=redis://your-elasticache-cluster-endpoint.cache.amazonaws.com:6379/0

# 带 TLS 加密
REDIS_URI=rediss://your-elasticache-endpoint.cache.amazonaws.com:6379/0
```

**特性**：
- ✅ 自动故障转移（Multi-AZ）
- ✅ 自动备份和恢复
- ✅ CloudWatch 监控
- ✅ 自动软件更新
- ✅ VPC 隔离

---

#### 2️⃣ 向量存储：Qdrant/pgvector → **两种方案**

##### 方案 2A：Qdrant on ECS Fargate ⭐⭐⭐⭐⭐ （推荐）

**为什么选择自建 Qdrant**：
- ✅ 无维度限制（支持 4096 维度）
- ✅ 性能极佳（3-5ms 查询延迟）
- ✅ 开源免费，无许可成本
- ✅ ECS Fargate 自动扩展

**AWS 服务组合**：
- `ECS Fargate`：运行 Qdrant 容器
- `EFS`：持久化存储
- `Application Load Balancer`：负载均衡
- `CloudWatch`：监控和告警

**推荐配置**：
```yaml
# ECS Task Definition
Family: qdrant-cluster
LaunchType: FARGATE
CPU: 4096 (4 vCPU)
Memory: 16384 (16 GB)
DesiredCount: 3  # 3 节点集群

# 挂载 EFS
Volumes:
  - Name: qdrant-data
    EFSVolumeConfiguration:
      FileSystemId: fs-xxxxxxxxx
      TransitEncryption: ENABLED

# 集群模式环境变量
Environment:
  - QDRANT__CLUSTER__ENABLED=true
  - QDRANT__CLUSTER__P2P__PORT=6335
```

**价格估算**（us-east-1）：
- ECS Fargate：4 vCPU × 16 GB × 3 节点 × $0.04048/vCPU/hr = **$350/月**
- EFS 存储：100 GB × $0.30/GB = **$30/月**
- ALB：$16.20 + 数据传输
- **总计**：≈ **$400-500/月**

**环境变量**：
```bash
VECTOR_STORAGE=QdrantStorage
QDRANT_URL=http://qdrant-cluster-alb-xxxxxxxxx.us-east-1.elb.amazonaws.com:6333
# QDRANT_API_KEY=your_api_key  # 建议启用认证
```

**部署步骤**：
```bash
# 1. 创建 EFS 文件系统
aws efs create-file-system \
  --creation-token qdrant-storage \
  --performance-mode generalPurpose \
  --throughput-mode bursting

# 2. 创建 ECS 集群
aws ecs create-cluster --cluster-name qdrant-cluster

# 3. 注册任务定义
aws ecs register-task-definition --cli-input-json file://qdrant-task-def.json

# 4. 创建服务
aws ecs create-service \
  --cluster qdrant-cluster \
  --service-name qdrant \
  --task-definition qdrant:1 \
  --desired-count 3 \
  --launch-type FARGATE \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...
```

---

##### 方案 2B：RDS for PostgreSQL + pgvector

**适合**：使用 1024 维度模型，希望使用 AWS 全托管数据库

**AWS 服务**：`Amazon RDS for PostgreSQL 16+ (带 pgvector 扩展)`

**推荐配置**：
- **实例类型**：`db.r7g.large` (2 vCPU, 16 GiB)
- **Multi-AZ**：启用（高可用）
- **存储**：500 GB gp3 (3000 IOPS)
- **备份**：自动备份 7 天

**价格**（us-east-1）：
- 实例：$0.416/小时 × 730 小时 = **$304/月**
- 存储：500 GB × $0.133/GB = **$67/月**
- **总计**：≈ **$371/月**

**环境变量**：
```bash
VECTOR_STORAGE=PGVectorStorage
POSTGRES_HOST=your-rds-instance.xxxxxxxxx.us-east-1.rds.amazonaws.com
POSTGRES_PORT=5432
POSTGRES_DATABASE=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=your_secure_password
EMBEDDING_DIM=1024  # ⚠️  必须 ≤ 2000 才能使用 HNSW 索引
```

**初始化脚本**：
```sql
-- 连接到 RDS 实例
psql -h your-rds-instance.xxxxxxxxx.us-east-1.rds.amazonaws.com -U postgres

-- 创建扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 创建数据库和用户
CREATE DATABASE lightrag;
CREATE USER lightrag WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE lightrag TO lightrag;
```

---

#### 3️⃣ 图存储：Neo4j/Memgraph → **两种方案**

##### 方案 3A：Amazon Neptune ⭐⭐⭐⭐

**AWS 服务**：`Amazon Neptune` (托管图数据库)

**优势**：
- ✅ 全托管，零运维
- ✅ 高可用（Multi-AZ）
- ✅ 支持 openCypher 查询语言（Neo4j 兼容）
- ✅ 自动备份和恢复

**推荐配置**：
- **实例类型**：`db.r6g.large` (2 vCPU, 16 GiB)
- **只读副本**：1 个（不同 AZ）
- **存储**：按使用量计费（$0.10/GB/月）

**价格**（us-east-1）：
- 主实例：$0.348/小时 × 730 小时 = **$254/月**
- 只读副本：$0.348/小时 × 730 小时 = **$254/月**
- 存储：100 GB × $0.10/GB = **$10/月**
- **总计**：≈ **$518/月**

**环境变量**：
```bash
GRAPH_STORAGE=Neo4JStorage  # Neptune 兼容 Neo4j Bolt 协议
NEO4J_URI=bolt://your-neptune-cluster.cluster-xxxxxxxxx.us-east-1.neptune.amazonaws.com:8182
NEO4J_USERNAME=  # Neptune 使用 IAM 认证，留空
NEO4J_PASSWORD=
```

**注意事项**：
- Neptune 需要配置 **IAM 数据库认证**
- 建议使用 **VPC 终端节点**连接
- 需要修改 LightRAG 代码以支持 IAM 认证

---

##### 方案 3B：自建 Memgraph on EC2

**为什么自建**：
- Memgraph 性能比 Neo4j 快 50 倍
- Neptune 主要优化为 AWS 生态，性能不一定优于专业图数据库

**AWS 服务组合**：
- `EC2 (c7g.xlarge)`：运行 Memgraph
- `EBS gp3`：持久化存储
- `Auto Scaling Group`：自动扩展
- `Application Load Balancer`：负载均衡

**推荐配置**：
- **实例类型**：`c7g.xlarge` (4 vCPU, 8 GiB)
- **实例数**：3 节点集群
- **存储**：500 GB EBS gp3

**价格**（us-east-1）：
- EC2：$0.1445/小时 × 3 实例 × 730 小时 = **$317/月**
- EBS：500 GB × 3 × $0.08/GB = **$120/月**
- **总计**：≈ **$437/月**

**环境变量**：
```bash
GRAPH_STORAGE=MemgraphStorage
MEMGRAPH_URI=bolt://memgraph-cluster-alb-xxxxxxxxx.us-east-1.elb.amazonaws.com:7687
```

**部署脚本**（EC2 User Data）：
```bash
#!/bin/bash
# 安装 Docker
yum update -y
yum install -y docker
systemctl start docker

# 运行 Memgraph
docker run -d \
  --name memgraph \
  -p 7687:7687 \
  -p 7444:7444 \
  -v /data/memgraph:/var/lib/memgraph \
  memgraph/memgraph-platform:latest \
  --memory-limit=6144 \
  --storage-snapshot-interval-sec=3600
```

---

#### 4️⃣ API 服务：Docker Compose → **ECS Fargate**

**AWS 服务**：`Amazon ECS on Fargate`

**推荐配置**：
- **Task CPU**：2048 (2 vCPU)
- **Task Memory**：8192 (8 GB)
- **Desired Count**：3 个任务（高可用）
- **Auto Scaling**：基于 CPU/内存使用率

**价格**（us-east-1）：
- 2 vCPU × 8 GB × 3 任务 × $0.04048/vCPU/hr = **$178/月**

**环境变量注入**（推荐使用 SSM Parameter Store）：
```bash
# 创建参数
aws ssm put-parameter \
  --name /rag-api/prod/redis-uri \
  --value "redis://your-elasticache.amazonaws.com:6379/0" \
  --type SecureString

# ECS Task Definition 引用
{
  "secrets": [
    {
      "name": "REDIS_URI",
      "valueFrom": "arn:aws:ssm:us-east-1:123456789012:parameter/rag-api/prod/redis-uri"
    }
  ]
}
```

**部署步骤**：
```bash
# 1. 推送镜像到 ECR
aws ecr create-repository --repository-name rag-api
docker build -t rag-api .
docker tag rag-api:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest

# 2. 创建 ECS 集群
aws ecs create-cluster --cluster-name rag-api-prod

# 3. 注册任务定义
aws ecs register-task-definition --cli-input-json file://task-definition.json

# 4. 创建服务
aws ecs create-service \
  --cluster rag-api-prod \
  --service-name rag-api \
  --task-definition rag-api:1 \
  --desired-count 3 \
  --launch-type FARGATE \
  --load-balancers targetGroupArn=arn:aws:elasticloadbalancing:...
```

---

#### 5️⃣ 负载均衡：Nginx → **Application Load Balancer (ALB)**

**AWS 服务**：`Application Load Balancer`

**功能**：
- ✅ 自动扩展
- ✅ HTTPS 终止（ACM 免费证书）
- ✅ 健康检查
- ✅ WebSocket 支持
- ✅ 路径路由

**价格**（us-east-1）：
- ALB 小时费用：$0.0225/小时 × 730 小时 = **$16.43/月**
- LCU（负载容量单元）：根据流量计费

**配置示例**：
```bash
# 创建 ALB
aws elbv2 create-load-balancer \
  --name rag-api-alb \
  --subnets subnet-12345678 subnet-87654321 \
  --security-groups sg-12345678 \
  --scheme internet-facing \
  --type application

# 创建目标组
aws elbv2 create-target-group \
  --name rag-api-targets \
  --protocol HTTP \
  --port 8000 \
  --vpc-id vpc-12345678 \
  --health-check-path /health \
  --health-check-interval-seconds 30 \
  --target-type ip  # Fargate 必须用 ip

# 创建监听器（HTTPS）
aws elbv2 create-listener \
  --load-balancer-arn arn:aws:elasticloadbalancing:... \
  --protocol HTTPS \
  --port 443 \
  --certificates CertificateArn=arn:aws:acm:... \
  --default-actions Type=forward,TargetGroupArn=arn:aws:elasticloadbalancing:...
```

---

## 💰 成本对比总结

### 月度成本（us-east-1 区域）

| 组件 | 自建成本 | AWS 方案 A（全托管） | AWS 方案 B（混合） |
|------|---------|---------------------|-------------------|
| **KV 存储** | $50-100 | ElastiCache $158 | ElastiCache $158 |
| **向量存储** | $50-100 | Qdrant on ECS $450 | RDS+pgvector $371 |
| **图存储** | $50-100 | Neptune $518 | Memgraph on EC2 $437 |
| **API 服务** | $100-200 | ECS Fargate $178 | ECS Fargate $178 |
| **负载均衡** | $0 | ALB $20 | ALB $20 |
| **备份存储** | $20 | S3 $30 | S3 $30 |
| **运维人力** | $500/月 | $100/月 (减少 80%) | $200/月 (减少 60%) |
| **总计** | $770-1120 | **$1,454** | **$1,394** |

**关键洞察**：
- 虽然云服务成本高 30%，但**运维成本降低 60-80%**
- 考虑人力成本后，云服务**总成本更低**
- 获得**高可用、自动扩展、自动备份**等企业级能力

---

## 📋 迁移步骤（分阶段）

### 阶段 1：数据层迁移（第 1-2 周）

#### Step 1: 迁移 Redis（最简单）

```bash
# 1. 创建 ElastiCache 集群
aws elasticache create-replication-group \
  --replication-group-id rag-redis-prod \
  --replication-group-description "RAG API Redis" \
  --engine redis \
  --cache-node-type cache.r7g.large \
  --num-cache-clusters 2 \
  --automatic-failover-enabled

# 2. 导出现有数据
docker exec rag-redis-dev redis-cli --rdb /data/dump.rdb
docker cp rag-redis-dev:/data/dump.rdb ./backup.rdb

# 3. 导入到 ElastiCache（通过临时 EC2）
# 在与 ElastiCache 同一 VPC 的 EC2 上：
redis-cli -h your-elasticache-endpoint.cache.amazonaws.com \
  --rdb backup.rdb

# 4. 更新 .env 配置
REDIS_URI=redis://your-elasticache-endpoint.cache.amazonaws.com:6379/0

# 5. 重启 rag-api，验证连接
```

---

#### Step 2: 迁移向量数据库

**选项 A：迁移到 Qdrant on ECS**

```bash
# 1. 部署 Qdrant 集群到 ECS（参考上方配置）
# 已创建 ECS 服务和 ALB

# 2. 从现有 PostgreSQL 导出数据（如果使用 pgvector）
# 注意：需要重新生成 embeddings，不同数据库格式不兼容
# 建议：从源文档重新插入

# 3. 更新 .env 配置
VECTOR_STORAGE=QdrantStorage
QDRANT_URL=http://qdrant-alb.us-east-1.elb.amazonaws.com:6333

# 4. 使用批量插入脚本重新插入文档
python scripts/migrate_to_qdrant.py \
  --source-docs /path/to/documents \
  --tenant-id default \
  --batch-size 100
```

---

#### Step 3: 迁移图数据库

**选项 A：迁移到 Neptune**

```bash
# 1. 创建 Neptune 集群
aws neptune create-db-cluster \
  --db-cluster-identifier rag-neptune-prod \
  --engine neptune \
  --db-subnet-group-name my-subnet-group \
  --vpc-security-group-ids sg-12345678

# 2. 创建实例
aws neptune create-db-instance \
  --db-instance-identifier rag-neptune-instance-1 \
  --db-instance-class db.r6g.large \
  --engine neptune \
  --db-cluster-identifier rag-neptune-prod

# 3. 从 Neo4j 导出数据（Cypher 格式）
docker exec rag-neo4j-dev cypher-shell -u neo4j -p password \
  "MATCH (n) RETURN n" > nodes.cypher
docker exec rag-neo4j-dev cypher-shell -u neo4j -p password \
  "MATCH ()-[r]->() RETURN r" > relationships.cypher

# 4. 导入到 Neptune（需要转换格式）
# Neptune 使用 Gremlin/SPARQL，需要格式转换脚本

# 5. 更新 .env 配置
NEO4J_URI=bolt://your-neptune-cluster.cluster-xxxxxxxxx.us-east-1.neptune.amazonaws.com:8182
```

---

### 阶段 2：应用层迁移（第 3-4 周）

#### Step 4: 迁移 API 服务到 ECS

```bash
# 1. 构建并推送 Docker 镜像到 ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 123456789012.dkr.ecr.us-east-1.amazonaws.com
docker build -t rag-api .
docker tag rag-api:latest 123456789012.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest

# 2. 创建任务定义（task-definition.json）
# 见上方配置示例

# 3. 创建 ECS 服务
aws ecs create-service \
  --cluster rag-api-prod \
  --service-name rag-api \
  --task-definition rag-api:1 \
  --desired-count 3 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345678,subnet-87654321],securityGroups=[sg-12345678],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:us-east-1:123456789012:targetgroup/rag-api/50dc6c495c0c9188,containerName=rag-api,containerPort=8000"

# 4. 配置 Auto Scaling
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/rag-api-prod/rag-api \
  --min-capacity 2 \
  --max-capacity 10

aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/rag-api-prod/rag-api \
  --policy-name cpu-scaling-policy \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration file://cpu-scaling-policy.json
```

---

### 阶段 3：切换流量（第 5 周）

```bash
# 1. 更新 DNS（Route 53）
aws route53 change-resource-record-sets \
  --hosted-zone-id Z1234567890ABC \
  --change-batch file://dns-change.json

# dns-change.json:
{
  "Changes": [{
    "Action": "UPSERT",
    "ResourceRecordSet": {
      "Name": "api.yourdomain.com",
      "Type": "A",
      "AliasTarget": {
        "HostedZoneId": "Z35SXDOTRQ7X7K",
        "DNSName": "rag-api-alb-123456789.us-east-1.elb.amazonaws.com",
        "EvaluateTargetHealth": true
      }
    }
  }]
}

# 2. 灰度发布（使用加权路由）
# 10% 流量到新环境，90% 到旧环境
# 监控 CloudWatch 指标
# 逐步增加到 50%、100%

# 3. 监控关键指标
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=rag-api \
  --start-time 2025-10-30T00:00:00Z \
  --end-time 2025-10-31T00:00:00Z \
  --period 300 \
  --statistics Average
```

---

## 🔧 高可用配置清单

### Multi-AZ 部署

```yaml
# 所有服务跨 3 个可用区
Availability Zones:
  - us-east-1a
  - us-east-1b
  - us-east-1c

# ECS 任务分布
ECS Tasks:
  - AZ: us-east-1a, Count: 1
  - AZ: us-east-1b, Count: 1
  - AZ: us-east-1c, Count: 1

# ElastiCache 副本分布
ElastiCache:
  - Primary: us-east-1a
  - Replica 1: us-east-1b
  - Replica 2: us-east-1c

# Qdrant 集群分布
Qdrant:
  - Node 1: us-east-1a
  - Node 2: us-east-1b
  - Node 3: us-east-1c
```

### 自动故障恢复

```yaml
# ECS 服务自动恢复
Service:
  DesiredCount: 3
  MinHealthyPercent: 50  # 滚动更新时保持 50% 容量
  MaxPercent: 200         # 允许临时双倍容量
  HealthCheck:
    Path: /health
    Interval: 30s
    Timeout: 5s
    HealthyThreshold: 2
    UnhealthyThreshold: 3

# ElastiCache 自动故障转移
ReplicationGroup:
  AutomaticFailoverEnabled: true
  MultiAZEnabled: true
  SnapshotRetentionLimit: 7

# ALB 健康检查
TargetGroup:
  HealthCheckProtocol: HTTP
  HealthCheckPath: /health
  HealthCheckIntervalSeconds: 30
  HealthyThresholdCount: 2
  UnhealthyThresholdCount: 3
```

---

## 📊 监控和告警

### CloudWatch 指标

```bash
# 创建告警 - ECS CPU 使用率过高
aws cloudwatch put-metric-alarm \
  --alarm-name rag-api-high-cpu \
  --alarm-description "ECS CPU > 80%" \
  --metric-name CPUUtilization \
  --namespace AWS/ECS \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=ServiceName,Value=rag-api Name=ClusterName,Value=rag-api-prod

# 创建告警 - ElastiCache 内存使用率
aws cloudwatch put-metric-alarm \
  --alarm-name redis-high-memory \
  --metric-name DatabaseMemoryUsagePercentage \
  --namespace AWS/ElastiCache \
  --statistic Average \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 90 \
  --comparison-operator GreaterThanThreshold

# 创建告警 - ALB 5xx 错误率
aws cloudwatch put-metric-alarm \
  --alarm-name alb-high-5xx \
  --metric-name HTTPCode_Target_5XX_Count \
  --namespace AWS/ApplicationELB \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold
```

### 日志聚合（CloudWatch Logs）

```yaml
# ECS 任务日志配置
LogConfiguration:
  LogDriver: awslogs
  Options:
    awslogs-group: /ecs/rag-api
    awslogs-region: us-east-1
    awslogs-stream-prefix: ecs

# 创建日志组
aws logs create-log-group --log-group-name /ecs/rag-api
aws logs put-retention-policy --log-group-name /ecs/rag-api --retention-in-days 7
```

---

## 🔐 安全最佳实践

### 1. VPC 隔离

```bash
# 创建专用 VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --tag-specifications 'ResourceType=vpc,Tags=[{Key=Name,Value=rag-api-vpc}]'

# 创建子网
aws ec2 create-subnet --vpc-id vpc-12345678 --cidr-block 10.0.1.0/24 --availability-zone us-east-1a  # Public
aws ec2 create-subnet --vpc-id vpc-12345678 --cidr-block 10.0.10.0/24 --availability-zone us-east-1a  # Private
```

### 2. IAM 角色和策略

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "elasticache:DescribeCacheClusters",
        "elasticache:DescribeReplicationGroups"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameter",
        "ssm:GetParameters"
      ],
      "Resource": "arn:aws:ssm:us-east-1:123456789012:parameter/rag-api/*"
    }
  ]
}
```

### 3. Secrets Manager 管理敏感信息

```bash
# 存储数据库密码
aws secretsmanager create-secret \
  --name rag-api/prod/postgres-password \
  --secret-string "your_secure_password"

# ECS 任务引用
{
  "secrets": [
    {
      "name": "POSTGRES_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:us-east-1:123456789012:secret:rag-api/prod/postgres-password"
    }
  ]
}
```

---

## 🎯 总结

### 推荐迁移路径

1. **第 1 周**：迁移 Redis → ElastiCache（最简单，风险最低）
2. **第 2-3 周**：迁移 Qdrant → ECS Fargate（核心组件，需充分测试）
3. **第 4 周**：迁移 API 服务 → ECS Fargate
4. **第 5 周**：灰度切换流量，逐步下线自建环境

### 关键收益

| 维度 | 自建 | AWS 托管 | 提升 |
|------|------|---------|------|
| **可用性 SLA** | 95% | 99.95% | +5% |
| **RTO（恢复时间）** | 4 小时 | 5 分钟 | **48x** |
| **RPO（数据丢失）** | 24 小时 | 5 分钟 | **288x** |
| **运维人力** | 2 人/天 | 0.5 人/天 | **-75%** |
| **扩展能力** | 手动 | 自动 | ∞ |

### 风险和注意事项

⚠️ **潜在风险**：
1. **成本超预期**：AWS 数据传输费用可能很高，建议启用 VPC Endpoints
2. **厂商锁定**：Neptune、ElastiCache 迁移回自建有难度
3. **学习曲线**：团队需要熟悉 AWS 服务和 IAM 权限模型

✅ **缓解措施**：
1. 使用 **AWS Cost Explorer** 实时监控成本
2. 优先使用开源服务（Qdrant on ECS），保留迁移灵活性
3. 参加 AWS 培训，获取认证（Solutions Architect）

---

**最后更新**：2025-10-31
**负责人**：待定
**预计完成时间**：5 周
