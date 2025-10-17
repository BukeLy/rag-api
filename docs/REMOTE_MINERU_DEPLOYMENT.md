# 远程 MinerU 部署指南

## 🎯 功能概述

本功能实现了完整的远程 MinerU API 集成，通过环境变量 `MINERU_MODE=remote` 启用。主要特性：

- **文件服务**: 在 8000 端口提供临时文件访问，支持远程 MinerU API 调用
- **自动切换**: 根据配置自动选择本地或远程处理方式
- **容错设计**: 远程服务不可用时自动回退到本地处理
- **性能优化**: 远程模式支持高并发处理（10+ 文档同时处理）

## 📋 部署前准备

### 1. 申请 MinerU API Token

1. 访问 [MinerU 官网](https://mineru.net)
2. 注册账号并登录
3. 在 API 管理页面申请 API Token
4. 免费账号每天有 2000 页的额度

### 2. 配置环境变量

编辑 `.env` 文件，配置以下参数：

```bash
# ====== 远程 MinerU 配置 ======
MINERU_MODE=remote
MINERU_API_TOKEN=sk-xxxxxxxxxxxxxxxxxxxx  # 替换为您的实际 Token
MINERU_API_BASE_URL=https://mineru.net
MINERU_MODEL_VERSION=vlm

# ====== 文件服务配置 ======
# 必须设置为服务器公网 IP:8000
FILE_SERVICE_BASE_URL=http://45.78.223.205:8000

# ====== 性能优化配置 ======
# 远程模式可大幅提升并发数
DOCUMENT_PROCESSING_CONCURRENCY=10
MINERU_MAX_CONCURRENT_REQUESTS=5
MINERU_REQUESTS_PER_MINUTE=60
```

## 🚀 部署步骤

### 1. 本地开发测试

```bash
# 测试文件服务功能
python scripts/test_remote_mineru.py

# 如果测试通过，提交代码
git add .
git commit -m "feat: 实现远程 MinerU 支持"
git push origin feature-branch
```

### 2. 服务器部署

在服务器 `45.78.223.205` 上执行：

```bash
# 拉取最新代码
cd /root/rag-api
git pull origin feature-branch

# 运行部署检查
./scripts/check-deployment.sh

# 如果检查通过，运行更新脚本
./scripts/update.sh
```

### 3. 验证部署

```bash
# 检查服务状态
docker compose ps

# 查看实时日志
docker compose logs -f rag-api

# 测试文件上传
curl -X POST "http://45.78.223.205:8000/insert?doc_id=test123" \
  -F "file=@test.pdf"
```

## 🔧 配置说明

### 环境变量详解

| 变量名 | 说明 | 默认值 | 必需 |
|--------|------|--------|------|
| `MINERU_MODE` | 运行模式 | `local` | ✅ |
| `MINERU_API_TOKEN` | API Token | - | ✅ |
| `FILE_SERVICE_BASE_URL` | 文件服务 URL | `http://localhost:8000` | ✅ |
| `DOCUMENT_PROCESSING_CONCURRENCY` | 处理并发数 | `1` | ✅ |

### 性能优化建议

1. **远程模式**: 设置 `DOCUMENT_PROCESSING_CONCURRENCY=10`
2. **本地模式**: 保持 `DOCUMENT_PROCESSING_CONCURRENCY=1`
3. **API 限流**: 根据 MinerU 套餐调整并发请求数

## 🐛 故障排除

### 常见问题

1. **文件服务无法访问**
   ```bash
   # 检查端口配置
   curl -I http://45.78.223.205:8000/files/
   ```

2. **MinerU API 连接失败**
   ```bash
   # 测试 API 连通性
   curl https://mineru.net/api/v4/health
   ```

3. **Token 无效**
   - 检查 MinerU API Token 是否正确
   - 确认 Token 是否有足够额度

### 日志分析

查看相关日志：

```bash
# 文件服务日志
docker compose logs rag-api | grep "File registered"

# MinerU API 调用日志
docker compose logs rag-api | grep "Remote MinerU"

# 错误日志
docker compose logs rag-api | grep -i error
```

## 📊 性能对比

### 本地模式 vs 远程模式

| 指标 | 本地模式 | 远程模式 |
|------|----------|----------|
| 并发处理数 | 1 | 10+ |
| 资源占用 | 高（GPU+内存） | 低（仅网络） |
| 处理速度 | 中等 | 快（依赖网络） |
| 稳定性 | 受本地资源限制 | 专业 API 服务 |

## 🔄 回退机制

如果远程 MinerU 服务不可用，系统会自动回退到本地处理：

1. 尝试远程处理
2. 如果失败，记录警告日志
3. 自动切换到本地 RAG-Anything 处理
4. 保证服务持续可用

## 📝 后续优化

- [ ] 实现批量文件处理（单次 API 调用处理多个文件）
- [ ] 添加结果缓存机制
- [ ] 实现更智能的文件清理策略
- [ ] 添加性能监控和告警

## 🆘 技术支持

如果遇到问题，请检查：

1. MinerU API Token 是否有效
2. 网络连通性（服务器能访问 mineru.net）
3. 文件服务 URL 配置是否正确
4. 查看详细日志获取错误信息
