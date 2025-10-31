# Docker 健康检查最佳实践

## 概述

本文档记录了项目中 Docker 健康检查的设计决策和最佳实践，特别是针对 Qdrant 向量数据库的健康检查实现。

## 背景

### Qdrant 官方立场

根据 [GitHub Issue #3491](https://github.com/qdrant/qdrant/issues/3491)：

- **PR #3505 被拒绝**：Qdrant 团队拒绝在官方镜像中添加 curl
- **拒绝原因**：
  1. 🔒 安全考虑：减小容器攻击面
  2. 🎯 极简主义：正在"进一步精简容器，移除核心工具"
- **关闭时间**：2024年2月5日

### Docker 社区最佳实践

根据《13 Docker Tricks You Didn't Know》文章第5条"Health Checks in Dockerfiles"：

**业界标准做法**：
```dockerfile
FROM nginx:latest

# Install curl for the health check.
RUN apt-get update && apt-get install -y curl && apt-get clean

HEALTHCHECK --interval=30s --timeout=30s --retries=3 --start-period=5s \
  CMD curl -f http://localhost/ || exit 1
```

**关键观察**：
- ✅ 在 Dockerfile 中安装 curl 是**业界标准做法**
- ✅ 使用 `curl -f` 检查 HTTP 端点
- ✅ 推荐使用专门的健康检查端点（如 `/healthz`）

## 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **1. curl HTTP 检查** | 最可靠，检查 HTTP 服务 | 需要安装 curl (+1MB) | ⭐⭐⭐⭐⭐ 生产环境 |
| **2. TCP 端口检查** | 零依赖，最轻量 | 只检查端口，不验证服务 | ⭐⭐⭐ 开发环境 |
| **3. 无健康检查** | 无开销 | 无法监控服务状态 | ⭐ 不推荐 |
| **4. Sidecar 容器** | 最安全 | 架构复杂，资源开销大 | ⭐⭐ 高安全要求 |

## 我们的方案：自定义 Dockerfile + curl

### 设计决策

我们选择**方案1（curl HTTP 检查）**，原因：

1. ✅ **符合 Docker 社区最佳实践**
2. ✅ **尊重 Qdrant 官方立场**（不改官方镜像，使用自定义镜像）
3. ✅ **最可靠的健康检查**（验证 HTTP 服务，非仅端口）
4. ✅ **性能影响可忽略**（镜像大小 +1MB < 1%，运行时几乎无影响）
5. ✅ **完全自动化**（一次构建，永久使用）

### 实现细节

#### Dockerfile.qdrant

```dockerfile
# 自定义 Qdrant 镜像 - 添加 curl 支持健康检查
FROM qdrant/qdrant:latest

# 安装 curl（用于健康检查）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 保持原有的启动命令和配置
```

**关键点**：
- 基于官方镜像，保持兼容性
- 使用 `--no-install-recommends` 减小镜像大小
- 清理 apt 缓存 (`rm -rf /var/lib/apt/lists/*`)

#### docker-compose 配置

```yaml
qdrant:
  build:
    context: .
    dockerfile: Dockerfile.qdrant
  image: rag-qdrant:latest
  container_name: rag-qdrant
  restart: unless-stopped
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 30s
```

**参数说明**：
- `interval: 30s`：每30秒检查一次
- `timeout: 10s`：单次检查超时时间
- `retries: 5`：连续失败5次才标记为 unhealthy
- `start_period: 30s`：容器启动后等待30秒再开始健康检查

## 性能影响分析

### 镜像大小
- 原始 Qdrant 镜像：**178MB**
- curl + 依赖：**~1-2MB**
- **总增加：<1%**

### 构建时间
- 首次构建：**+10-15秒**
- 后续构建（有缓存）：**~0秒**

### 运行时性能
- 启动时间：**0ms 额外开销**
- 健康检查执行时间：**10-50ms**（每30秒一次）
- 内存占用：**~1-2MB**（临时，仅检查时）
- CPU 使用：**几乎可忽略**

## 最佳实践总结

### ✅ DO（推荐做法）

1. **使用专用健康检查端点**
   ```yaml
   test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
   ```

2. **设置合理的 start_period**
   - 给应用足够的启动时间
   - Qdrant 建议 30 秒

3. **使用轻量的检查命令**
   - curl 本身很轻量
   - 避免复杂的脚本

4. **在 Dockerfile 中安装工具**
   - 一次构建，永久使用
   - 团队共享，完全自动化

5. **清理构建缓存**
   ```dockerfile
   RUN apt-get update && \
       apt-get install -y --no-install-recommends curl && \
       rm -rf /var/lib/apt/lists/*
   ```

### ❌ DON'T（避免做法）

1. **运行时手动安装 curl**
   - ❌ 健康检查会立即失败
   - ❌ 每次重启都要重装
   - ❌ 无法自动化

2. **过于复杂的健康检查命令**
   - ❌ 可能不可靠
   - ❌ 影响性能

3. **忽略外部依赖**
   - ❌ 如果服务依赖外部资源，健康检查要考虑

4. **过于频繁的检查**
   - ❌ 增加系统负担
   - 推荐间隔：30秒

5. **过于严格的重试次数**
   - ❌ retries=1 可能导致误判
   - 推荐：3-5 次

## 替代方案（参考）

### TCP 端口检查（轻量但不可靠）

```yaml
healthcheck:
  test: ["CMD-SHELL", "timeout 1 bash -c '</dev/tcp/localhost/6333' || exit 1"]
```

**优点**：
- ✅ 零依赖
- ✅ 性能最优

**缺点**：
- ❌ 只检查端口，不验证 HTTP 服务
- ❌ 无法检测服务是否真正响应

### Sidecar 容器（最安全但复杂）

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    # 不定义健康检查

  qdrant-healthcheck:
    image: curlimages/curl:latest
    command: >
      sh -c 'while true; do
        curl -f http://qdrant:6333/healthz || exit 1;
        sleep 30;
      done'
    depends_on:
      - qdrant
```

**优点**：
- ✅ 完全隔离，最安全
- ✅ 不修改主容器

**缺点**：
- ❌ 架构复杂
- ❌ 额外容器资源开销
- ❌ 管理成本高

## 参考资料

### 官方文档
- [Docker Healthcheck 文档](https://docs.docker.com/engine/reference/builder/#healthcheck)
- [Dockerfile 最佳实践](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

### 社区资源
- [Qdrant Issue #3491](https://github.com/qdrant/qdrant/issues/3491) - 官方拒绝添加 curl
- [13 Docker Tricks You Didn't Know](https://overcast.blog/13-docker-tricks-you-didnt-know-47775a4f678f) - 第5条健康检查最佳实践

### 相关项目文档
- `Dockerfile.qdrant` - 自定义 Qdrant 镜像
- `docker-compose.dev.yml` - 开发环境配置
- `docker-compose.yml` - 生产环境配置

## 维护说明

### 升级 Qdrant 版本

```bash
# 1. 更新 Dockerfile.qdrant 中的基础镜像版本
FROM qdrant/qdrant:v1.x.x  # 改为新版本

# 2. 重新构建镜像
docker compose -f docker-compose.dev.yml build qdrant

# 3. 测试健康检查
docker compose -f docker-compose.dev.yml up -d
docker ps  # 查看健康状态
```

### 故障排查

**健康检查失败**：
```bash
# 1. 查看容器日志
docker logs rag-qdrant

# 2. 手动执行健康检查命令
docker exec rag-qdrant curl -f http://localhost:6333/healthz

# 3. 检查 Qdrant 服务状态
docker exec rag-qdrant ps aux | grep qdrant
```

**curl 命令不存在**：
```bash
# 检查 curl 是否已安装
docker exec rag-qdrant which curl

# 如果不存在，重新构建镜像
docker compose build qdrant --no-cache
```

## 更新历史

- **2025-10-31**: 初始版本，记录健康检查方案选择和最佳实践
