# Docker 构建优化策略 (适配 ECR 部署)

## 🎯 设计目标

1. ✅ **镜像完整性**: 代码打包在镜像中，可推送到 ECR 独立运行
2. ✅ **构建速度**: 利用 Docker 缓存，代码变更时快速重建
3. ✅ **磁盘管理**: 自动清理旧镜像，防止磁盘爆满

---

## 📦 Dockerfile 分层策略

```dockerfile
# 第 1 层：系统依赖（变化频率：低）
RUN apt-get update && apt-get install -y gcc g++ ...

# 第 2 层：Python 包管理器（变化频率：极低）
RUN pip install --no-cache-dir uv

# 第 3 层：Python 依赖（变化频率：中）
COPY pyproject.toml uv.lock* ./
RUN uv sync  # 这层会被缓存，8GB 依赖不用重复下载

# 第 4 层：应用代码（变化频率：高）
COPY main.py ./
COPY src/ ./src/
COPY api/ ./api/
```

**关键原则**: 把变化频率低的层放前面，变化频率高的层放后面。

---

## ⚡ 构建性能

### 场景 1：只修改代码（90% 的情况）

```bash
# 修改 main.py, src/, api/ 中的代码
vim main.py

# 重新构建
./scripts/update.sh
```

**构建过程**:
- ✅ 第 1-3 层：从缓存加载（秒级）
- 🔄 第 4 层：重新复制代码（秒级）

**构建时间**: **1-2 分钟**（vs 之前的 15 分钟）

---

### 场景 2：修改依赖（10% 的情况）

```bash
# 修改 pyproject.toml
vim pyproject.toml

# 重新构建
./scripts/update.sh
```

**构建过程**:
- ✅ 第 1-2 层：从缓存加载（秒级）
- 🔄 第 3 层：重新下载 Python 包（慢）
- 🔄 第 4 层：复制代码

**构建时间**: **15 分钟**（无法避免，需要下载包）

---

## 🗑️ 自动清理策略

### `update.sh` 自动执行

每次更新时，脚本会：

```bash
# 1. 清理悬空镜像（<none>:<none>）
docker image prune -f

# 2. 清理构建缓存中的无用层
# （Docker 会自动管理，保留有用的缓存）
```

### 手动深度清理

如果磁盘空间还是不够：

```bash
# 清理所有未使用的镜像（包括旧版本）
docker system prune -a -f

# 清理所有构建缓存
docker builder prune -af
```

⚠️ **注意**: 深度清理后，下次构建会从头开始，需要 15 分钟。

---

## 📊 磁盘占用预期

```
初始状态（首次部署）:
├─ 镜像: 10.8GB
├─ 容器数据: 2.6GB
└─ 构建缓存: 0GB
总计: ~13GB

经过 5 次代码更新后:
├─ 镜像: 10.8GB (只有最新版)
├─ 容器数据: 2.6GB
├─ 构建缓存: 2-3GB (Docker 自动管理)
└─ 悬空镜像: 0GB (自动清理)
总计: ~16GB ✅

经过 10 次代码更新后:
├─ 镜像: 10.8GB
├─ 容器数据: 2.6GB
├─ 构建缓存: 3-4GB
└─ 悬空镜像: 0GB
总计: ~18GB ✅
```

**结论**: 磁盘占用稳定在 15-20GB，不会无限增长。

---

## 🚀 ECR 部署流程

### 1. 本地构建并推送

```bash
# 登录 ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# 打标签
docker tag rag-api-rag-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest

# 推送到 ECR
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
```

### 2. 在其他服务器上部署

```bash
# 拉取镜像
docker pull <account-id>.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest

# 运行（镜像包含完整代码，可以独立运行）
docker run -d \
  --name rag-api \
  -p 8000:8000 \
  --env-file .env \
  -v ./rag_local_storage:/app/rag_local_storage \
  <account-id>.dkr.ecr.us-east-1.amazonaws.com/rag-api:latest
```

✅ **镜像是完整的**，包含所有代码和依赖，可以在任何地方运行。

---

## 🆚 对比：错误方案 vs 正确方案

| 维度 | ❌ 代码挂载方案 | ✅ 当前方案 |
|-----|--------------|----------|
| **镜像完整性** | 镜像不含代码，不能推 ECR | 镜像完整，可推 ECR |
| **代码更新速度** | 1秒（重启容器） | 1-2分钟（重建镜像） |
| **依赖更新速度** | 15分钟 | 15分钟 |
| **磁盘占用** | 13GB | 15-20GB（稳定） |
| **适用场景** | 单机开发 | 生产部署 |

---

## 🔍 故障排查

### 问题 1：构建很慢，明明只改了代码

```bash
# 检查是否有缓存
docker builder ls

# 清理并重建
docker builder prune -af
docker compose build
```

### 问题 2：磁盘占用超过 25GB

```bash
# 查看占用
docker system df

# 清理所有未使用资源
docker system prune -a -f --volumes
```

### 问题 3：推送到 ECR 后无法运行

```bash
# 检查镜像是否包含代码
docker run --rm <image> ls -la /app

# 应该看到 main.py, src/, api/
```

---

## 📝 最佳实践

1. **频繁提交小改动**: 利用缓存，每次构建更快
2. **批量修改依赖**: 一次性修改所有依赖，避免多次 15 分钟构建
3. **定期清理**: 每周执行 `docker system prune -f`
4. **监控磁盘**: `df -h /` 和 `docker system df`
5. **版本标签**: 推送 ECR 时打上版本标签，便于回滚

---

## ✅ 总结

这个方案**平衡了构建速度和镜像完整性**：

- ✅ 镜像可以推送到 ECR 独立部署
- ✅ 代码更新时利用缓存，2 分钟完成（vs 15 分钟）
- ✅ 磁盘占用可控，不会无限增长
- ✅ 适合生产环境的标准 Docker 实践

**这是一个真正可持续、可扩展的方案！** 🎉

