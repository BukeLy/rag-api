# 部署模式说明

## 概述

RAG API 支持两种部署模式，以满足不同场景的需求：

1. **生产模式 (Production)** - 标准容器部署
2. **开发模式 (Development)** - 代码外挂，支持热重载

## 部署模式对比

| 特性 | 生产模式 | 开发模式 |
|------|---------|---------|
| Docker Compose 文件 | `docker-compose.yml` | `docker-compose.dev.yml` |
| 代码存储位置 | 容器内部 | 挂载本地目录 |
| 代码修改后 | 需要重新构建镜像 | 自动重载（热重载） |
| 适用场景 | 生产环境、稳定部署 | 本地开发、调试测试 |
| 性能 | 最优 | 略低（文件系统挂载） |
| 安全性 | 高 | 中（暴露源代码） |

## 使用方法

### 1. 使用一键部署脚本

运行部署脚本时，会提示选择部署模式：

```bash
./deploy.sh
```

脚本会显示以下选项：

```
请选择部署模式:
  1) 生产模式 (Production) - 标准容器部署，适合生产环境
  2) 开发模式 (Development) - 外挂代码库，支持热重载，适合开发调试

请输入选择 (1/2, 默认: 1):
```

- 输入 `1` 或直接回车：使用生产模式
- 输入 `2`：使用开发模式

### 2. 手动部署

#### 生产模式

```bash
docker compose -f docker-compose.yml build
docker compose -f docker-compose.yml up -d
```

#### 开发模式

```bash
docker compose -f docker-compose.dev.yml build
docker compose -f docker-compose.dev.yml up -d
```

或使用简化脚本：

```bash
./scripts/dev.sh
```

## 开发模式特性

### 代码挂载

开发模式会将本地代码目录挂载到容器中：

```yaml
volumes:
  - ./api:/app/api
  - ./src:/app/src
  - ./main.py:/app/main.py
```

### 热重载

使用 `watchfiles` 实现自动重载：

```bash
CMD ["watchfiles", "--filter", "python", "uvicorn main:app --host 0.0.0.0 --port 8000"]
```

当检测到 Python 文件变化时，自动重启应用。

### 适用场景

- **本地开发**：修改代码后立即生效，无需重新构建镜像
- **调试测试**：快速验证代码变更
- **学习研究**：方便查看和修改源代码

## 常用命令

### 生产模式

```bash
# 启动服务
docker compose -f docker-compose.yml up -d

# 查看日志
docker compose -f docker-compose.yml logs -f

# 重启服务
docker compose -f docker-compose.yml restart

# 停止服务
docker compose -f docker-compose.yml down
```

### 开发模式

```bash
# 启动服务
docker compose -f docker-compose.dev.yml up -d

# 查看日志（观察热重载）
docker compose -f docker-compose.dev.yml logs -f

# 重启服务
docker compose -f docker-compose.dev.yml restart

# 停止服务
docker compose -f docker-compose.dev.yml down
```

## 切换模式

### 从生产模式切换到开发模式

```bash
# 停止生产模式
docker compose -f docker-compose.yml down

# 启动开发模式
docker compose -f docker-compose.dev.yml up -d
```

### 从开发模式切换到生产模式

```bash
# 停止开发模式
docker compose -f docker-compose.dev.yml down

# 启动生产模式
docker compose -f docker-compose.yml up -d
```

## 注意事项

### 开发模式

1. **不建议用于生产环境**
   - 代码外挂会暴露源代码
   - 性能略低于生产模式
   - 文件系统挂载可能有权限问题

2. **文件权限**
   - 确保本地代码目录有正确的权限
   - 容器内用户需要能读取挂载的文件

3. **热重载限制**
   - 只监控 Python 文件变更
   - 配置文件（如 `.env`）变更需要手动重启
   - 依赖变更需要重新构建镜像

### 生产模式

1. **代码更新**
   - 修改代码后需要重新构建镜像
   - 使用 `./scripts/update.sh` 脚本进行更新

2. **版本控制**
   - 建议使用 Git 标签管理版本
   - 构建时指定明确的版本号

## 性能对比

### 启动时间

- **生产模式**：约 10-15 秒
- **开发模式**：约 12-18 秒（包含挂载和 watchfiles 初始化）

### 运行性能

- **生产模式**：100% 基准性能
- **开发模式**：约 95-98% 性能（文件系统挂载开销）

### 重载时间

- **生产模式**：需要重新构建镜像（2-5 分钟）
- **开发模式**：自动重载（2-5 秒）

## 最佳实践

### 本地开发

1. 使用开发模式进行日常开发
2. 频繁测试和迭代
3. 提交前切换到生产模式进行完整测试

### 生产部署

1. 始终使用生产模式
2. 通过 CI/CD 自动构建和部署
3. 使用版本标签管理发布

### 团队协作

1. 统一开发环境配置
2. 在 `.env.example` 中提供完整的环境变量示例
3. 文档化特殊配置和依赖

## 故障排查

### 开发模式无法启动

1. 检查本地代码目录权限
2. 确保 Docker 有权访问项目目录
3. 查看容器日志：`docker compose -f docker-compose.dev.yml logs`

### 热重载不工作

1. 确认修改的是 Python 文件
2. 检查 `watchfiles` 是否正常运行
3. 查看容器日志确认重载事件

### 生产模式镜像过大

1. 使用多阶段构建优化镜像
2. 清理不必要的依赖和缓存
3. 使用 `.dockerignore` 排除不需要的文件

## 更新历史

- **v1.1** (2025-10-30)
  - 添加部署模式选择功能
  - 支持生产模式和开发模式切换
  - 优化部署脚本用户体验

- **v1.0** (2025-10-23)
  - 初始版本
  - 仅支持生产模式部署

