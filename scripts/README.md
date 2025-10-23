# Scripts 目录说明

本目录包含生产环境迁移和运维相关的脚本工具。

---

## 📁 脚本清单

### 1. `init_postgres.sql`

**用途**: PostgreSQL 数据库初始化脚本

**功能**:
- 启用 pgvector 扩展
- 配置用户权限
- 创建监控视图

**使用**: 自动执行（放置在 Docker Compose 的 `/docker-entrypoint-initdb.d/` 目录）

```yaml
# docker-compose.yml
postgres:
  volumes:
    - ./scripts/init_postgres.sql:/docker-entrypoint-initdb.d/init.sql
```

---

### 2. `health_check.sh` ✅

**用途**: 健康检查脚本，验证所有外部存储服务的连接状态

**功能**:
- 检查 API 服务
- 检查 Redis 连接
- 检查 PostgreSQL 连接
- 检查 Neo4j 连接
- 测试查询端点

**使用**:
```bash
# 标准模式
./scripts/health_check.sh

# 详细模式（显示数据库统计）
./scripts/health_check.sh --verbose
```

**输出示例**:
```
============================================================
🏥 RAG API Health Check
============================================================
Checking services...

🌐 API Service (http://localhost:8000): ✅ OK
🔴 Redis (localhost:6379): ✅ OK
🐘 PostgreSQL (localhost:5432): ✅ OK
🕸️  Neo4j (bolt://localhost:7687): ✅ OK

============================================================
🔬 Functional Tests
============================================================
🔍 Query Endpoint: ✅ OK

============================================================
📊 Summary
============================================================
✅ All services are healthy! ✨
```

---

### 3. `migrate_to_external_storage.py` 🚧

**用途**: 数据迁移脚本（文件存储 → 外部数据库）

**功能**:
- 迁移 KV 存储（JSON → Redis）
- 迁移向量存储（NanoVectorDB → PostgreSQL）
- 迁移图存储（GraphML → Neo4j）

**使用**:
```bash
# 预演模式（不实际写入数据）
python scripts/migrate_to_external_storage.py --dry-run

# 执行迁移
python scripts/migrate_to_external_storage.py --execute

# 指定源目录
python scripts/migrate_to_external_storage.py \
  --execute \
  --source-dir ./rag_local_storage
```

**注意**: 完整实现请参考 [PRODUCTION_MIGRATION_GUIDE.md](../docs/PRODUCTION_MIGRATION_GUIDE.md#数据迁移脚本)

---

### 4. `restore_from_aws.py` 🚧

**用途**: 从 AWS 托管服务恢复数据到本地 Docker Compose

**功能**:
- 从 ElastiCache 导出数据到本地 Redis
- 从 Aurora 导出数据到本地 PostgreSQL
- 从 Neo4j Aura 导出数据到本地 Neo4j

**使用**:
```bash
# 从 AWS 恢复数据
python scripts/restore_from_aws.py --execute

# 预演模式
python scripts/restore_from_aws.py --dry-run
```

**注意**: 此脚本用于回滚方案，实现细节待补充

---

## 🛠️ 开发计划

### 待实现脚本

| 脚本名 | 优先级 | 状态 | 说明 |
|--------|--------|------|------|
| `migrate_to_external_storage.py` | 高 | 🚧 | 详细实现在文档中 |
| `restore_from_aws.py` | 中 | 📝 | 回滚方案需要 |
| `backup.sh` | 中 | 📝 | 自动备份脚本 |
| `performance_test.sh` | 低 | 📝 | 性能基准测试 |

---

## 📚 相关文档

- [生产环境迁移指南](../docs/PRODUCTION_MIGRATION_GUIDE.md)
- [快速开始指南](../docs/PRODUCTION_MIGRATION_QUICKSTART.md)
- [架构设计文档](../docs/ARCHITECTURE.md)

---

## 🔧 脚本开发规范

### Shell 脚本

- 使用 `#!/bin/bash` shebang
- 添加详细的注释和使用说明
- 使用 `set -e` 确保错误时退出
- 提供 `--help` 参数
- 支持 `--dry-run` 模式

### Python 脚本

- 使用 `#!/usr/bin/env python3` shebang
- 使用 `argparse` 处理命令行参数
- 添加类型注解
- 提供 `--dry-run` 模式
- 记录详细日志

---

**维护者**: Backend Team
**最后更新**: 2025-10-23
