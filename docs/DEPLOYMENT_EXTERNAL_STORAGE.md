# 远端外部存储功能部署指南

## 📋 问题回顾

**之前的错误**：
```
TypeError: LightRAG.__init__() got an unexpected keyword argument 'kv_storage_cls_kwargs'
```

**根本原因**：LightRAG 1.4.9.4 通过环境变量读取外部存储配置，而非初始化参数。

**修复状态**：✅ 已在 dev 分支完成修复（commit: 0a8c377）

---

## 🚀 部署步骤

### 1️⃣ 连接到测试服务器

```bash
ssh -i /Users/chengjie/Downloads/chengjie.pem root@45.78.223.205
cd ~/rag-api
```

### 2️⃣ 停止服务并清理所有数据 ⚠️

**重要**：按用户要求，清理所有现有数据，确保干净部署。

```bash
# 停止所有服务
docker compose down

# 删除所有容器卷（包括 Redis、PostgreSQL、Neo4j 数据）
docker compose down -v

# 清理本地文件存储目录
rm -rf rag_local_storage

# 可选：清理日志文件（如果需要）
# rm -rf logs/*

# 验证清理结果
ls -la rag_local_storage 2>/dev/null && echo "⚠️ 文件夹仍存在！" || echo "✅ 本地存储已清理"
docker volume ls | grep rag && echo "⚠️ 卷仍存在！" || echo "✅ Docker 卷已清理"
```

### 3️⃣ 拉取最新代码

```bash
# 确保在 dev 分支
git checkout dev

# 拉取最新修复
git pull origin dev

# 验证是否获取了修复提交
git log --oneline -1
# 应显示：0a8c377 fix: 修复外部存储初始化错误（LightRAG 1.4.9.4 兼容性）
```

### 4️⃣ 更新 .env 配置

**选项 A：启用外部存储（推荐）**

编辑 `.env` 文件，添加/修改以下配置：

```bash
# === 外部存储配置 ===
USE_EXTERNAL_STORAGE=true
KV_STORAGE=RedisKVStorage
VECTOR_STORAGE=PGVectorStorage
GRAPH_STORAGE=Neo4JStorage

# Redis 配置（注意：使用 REDIS_URI 而非分离的 host/port）
REDIS_URI=redis://redis:6379/0
REDIS_WORKSPACE=default

# PostgreSQL 配置（注意：使用 POSTGRES_DATABASE 而非 POSTGRES_DB）
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DATABASE=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=<安全密码>  # 请替换为安全密码
POSTGRES_WORKSPACE=default
POSTGRES_MAX_CONNECTIONS=20

# Neo4j 配置
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<安全密码>  # 请替换为安全密码
NEO4J_WORKSPACE=default
```

**快速配置命令**（复制现有密码）：

```bash
# 从现有 .env 获取密码
NEO4J_PASS=$(grep "^NEO4J_PASSWORD=" .env | cut -d'=' -f2)
POSTGRES_PASS=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2)

# 批量更新配置
cat >> .env <<EOF

# === 外部存储配置（修复后的配置）===
USE_EXTERNAL_STORAGE=true
KV_STORAGE=RedisKVStorage
VECTOR_STORAGE=PGVectorStorage
GRAPH_STORAGE=Neo4JStorage

# Redis 配置
REDIS_URI=redis://redis:6379/0
REDIS_WORKSPACE=default

# PostgreSQL 配置
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DATABASE=lightrag
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=$POSTGRES_PASS
POSTGRES_WORKSPACE=default
POSTGRES_MAX_CONNECTIONS=20

# Neo4j 配置
NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=$NEO4J_PASS
NEO4J_WORKSPACE=default
EOF
```

**选项 B：暂时使用文件存储（保守方案）**

如果想先测试代码修复是否有效，可以先不启用外部存储：

```bash
USE_EXTERNAL_STORAGE=false
# 其他配置保持不变
```

### 5️⃣ 启动服务

```bash
# 构建并启动所有服务
docker compose up -d --build

# 实时查看日志（检查是否有错误）
docker compose logs -f rag-api
```

### 6️⃣ 验证部署

**检查服务状态**：

```bash
docker compose ps
# 所有服务应显示 healthy 状态
```

**检查日志关键信息**：

如果启用了外部存储，应看到：

```
🔌 Using external storage backends:
   - KV Storage: RedisKVStorage
   - Vector Storage: PGVectorStorage
   - Graph Storage: Neo4JStorage
   Redis: redis://redis:6379/0
   PostgreSQL: postgres:5432/lightrag
   Neo4j: bolt://neo4j:7687 (user: neo4j)
```

**不应该再看到**：

```
TypeError: LightRAG.__init__() got an unexpected keyword argument 'kv_storage_cls_kwargs'
```

**测试 API**：

```bash
# 健康检查
curl http://45.78.223.205:8000/

# 测试查询（应该正常工作）
curl -s -X POST "http://45.78.223.205:8000/query" \
  -H "Content-Type: application/json" \
  -d '{"query": "test query", "mode": "naive"}'
```

---

## 📊 预期结果

### ✅ 成功指标

1. **服务启动无错误**：
   - 日志中不再出现 `kv_storage_cls_kwargs` 错误
   - 所有容器状态为 `healthy`

2. **外部存储连接成功**（如果启用）：
   - 日志显示 "🔌 Using external storage backends"
   - Redis、PostgreSQL、Neo4j 连接成功

3. **API 功能正常**：
   - 文档上传成功
   - 查询返回结果
   - 性能符合预期（15-20s 首次查询，6-11s 后续查询）

### 📈 性能提升（启用外部存储后）

根据之前的测试：
- 查询速度提升约 **25%**
- 支持水平扩展和高可用
- 数据持久化更可靠（ACID 事务）

---

## 🔧 故障排查

### 问题 1：服务启动失败

```bash
# 查看详细错误日志
docker compose logs rag-api | tail -100

# 检查配置文件语法
cat .env | grep -E "(REDIS_URI|POSTGRES_DATABASE|NEO4J_URI)"
```

### 问题 2：外部存储连接失败

```bash
# 检查数据库服务状态
docker compose ps redis postgres neo4j

# 测试 Redis 连接
docker compose exec redis redis-cli ping

# 测试 PostgreSQL 连接
docker compose exec postgres psql -U lightrag -d lightrag -c "SELECT 1;"

# 测试 Neo4j 连接
docker compose exec neo4j cypher-shell -u neo4j -p <password> "RETURN 1;"
```

### 问题 3：仍然看到 kv_storage_cls_kwargs 错误

确认代码已更新：

```bash
# 检查 src/rag.py 是否包含修复
grep "kv_storage_cls_kwargs" src/rag.py
# 应该没有输出（该参数已删除）

# 重新构建镜像
docker compose up -d --build --force-recreate
```

---

## 📝 回滚方案

如果部署出现问题，快速回滚到文件存储：

```bash
# 1. 修改 .env
sed -i 's/USE_EXTERNAL_STORAGE=true/USE_EXTERNAL_STORAGE=false/' .env

# 2. 重启服务
docker compose restart rag-api

# 3. 验证
docker compose logs -f rag-api
# 应看到："📁 Using local file storage (default)"
```

---

## 🎯 下一步

1. ✅ **验证功能**：上传测试文档并查询
2. ✅ **监控性能**：使用 `/monitor` 端点查看系统指标
3. ✅ **数据迁移**（可选）：如果需要从之前的备份恢复数据，使用 `scripts/migrate_to_external_storage.py`

---

## 📞 需要帮助？

如果遇到问题：
1. 查看详细日志：`docker compose logs rag-api | tail -200`
2. 检查数据库状态：`docker compose ps`
3. 查阅文档：`CLAUDE.md` - External Storage Configuration 章节
