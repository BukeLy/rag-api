# 部署优化说明

## 🎯 优化目标

解决 Docker 镜像重复构建导致的磁盘空间问题，实现**可持续的部署流程**。

---

## 🔧 核心改动

### 1. **代码与依赖分离** 

**之前的问题：**
```dockerfile
# 旧 Dockerfile - 每次代码变更都要重建整个镜像
COPY main.py ./
COPY src/ ./src/
COPY api/ ./api/
RUN uv sync  # 8GB+ 依赖每次都重新下载
```

**现在的方案：**
```dockerfile
# 新 Dockerfile - 只在依赖变更时重建
COPY pyproject.toml uv.lock* ./
RUN uv sync  # 这层会被 Docker 缓存
# 代码通过 volume 挂载，不在镜像里
```

```yaml
# docker-compose.yml - 代码动态挂载
volumes:
  - ./main.py:/app/main.py:ro
  - ./src:/app/src:ro
  - ./api:/app/api:ro
```

---

### 2. **智能更新策略**

#### **脚本：`scripts/update.sh`**

```bash
# 自动检测变更类型
if pyproject.toml 或 Dockerfile 变更:
    清理旧镜像 → 重建镜像 → 重启容器
else if 代码文件变更:
    仅重启容器 (1秒完成)
else:
    什么都不做
```

**效果对比：**

| 变更类型 | 旧方案 | 新方案 |
|---------|-------|-------|
| 修改代码 | 重建镜像 (15分钟) | 重启容器 (1秒) |
| 修改依赖 | 重建镜像 (15分钟) | 重建镜像 (15分钟) |
| 磁盘占用 | 每次 +10GB | 只有1个镜像 |

---

### 3. **自动清理机制**

**deploy.sh 和 update.sh 都会在重建前自动清理：**
```bash
docker system prune -f     # 清理悬空镜像
docker builder prune -f    # 清理构建缓存
```

---

## 📊 磁盘使用预期

```
初始状态:
├─ Docker 镜像: 10.8GB (只有1个)
├─ 容器数据:    2.6GB
└─ 构建缓存:    0GB (自动清理)
总计: ~13GB

旧方案 (3次更新后):
├─ Docker 镜像: 32GB (3个镜像)
├─ 容器数据:    2.6GB
└─ 构建缓存:    8GB
总计: ~43GB ❌ 超出40GB硬盘
```

---

## 🚀 使用方法

### **首次部署**
```bash
git clone <your-repo>
cd rag-api
./deploy.sh
```

### **代码更新 (90%的情况)**
```bash
cd rag-api
./scripts/update.sh
# 自动检测：只重启容器，1秒完成
```

### **依赖更新 (10%的情况)**
```bash
# 修改 pyproject.toml 后
cd rag-api
./scripts/update.sh
# 自动检测：清理 → 重建 → 重启，15分钟完成
```

---

## ⚠️ 注意事项

### **代码挂载的含义**
- ✅ **代码变更立即生效**（重启容器即可）
- ✅ **不占用镜像空间**（代码在宿主机上）
- ⚠️ **容器内不能修改代码**（挂载为只读 `:ro`）

### **何时需要重建镜像？**
- 修改 `pyproject.toml` (添加/删除依赖)
- 修改 `Dockerfile` (系统依赖、配置等)
- 修改 `uv.lock` (依赖版本锁定)

### **何时只需重启容器？**
- 修改 `main.py`, `src/`, `api/` (所有业务代码)
- 修改 `.env` (环境变量)

---

## 🔍 故障排查

### **问题：容器启动失败，提示 "No such file or directory: main.py"**
```bash
# 原因：volume 挂载路径不对
# 解决：确保在项目根目录执行命令
pwd  # 应该显示 /root/rag-api 或类似路径
docker compose up -d
```

### **问题：代码修改后没有生效**
```bash
# 原因：容器没有重启
docker compose restart
```

### **问题：磁盘空间还是不够**
```bash
# 手动深度清理
docker system prune -af --volumes
# 会删除所有未使用的镜像和卷，谨慎使用
```

---

## 📈 监控磁盘使用

```bash
# 查看 Docker 占用
docker system df

# 查看详细磁盘使用
du -sh /var/lib/docker/*

# 查看系统总览
df -h /
```

---

## ✅ 验证优化效果

```bash
# 1. 首次部署
./deploy.sh
du -sh /var/lib/docker  # 记录大小

# 2. 修改代码（例如 main.py 加个注释）
vim main.py
./scripts/update.sh  # 应该 1秒完成，不重建镜像

# 3. 查看磁盘
du -sh /var/lib/docker  # 应该几乎不变
```

---

## 🎉 总结

| 指标 | 优化前 | 优化后 | 改进 |
|-----|-------|-------|-----|
| 代码更新时间 | 15分钟 | 1秒 | **900x** |
| 磁盘占用 (3次更新) | 43GB | 13GB | **70%↓** |
| 是否可持续 | ❌ | ✅ | - |

**这套方案可以在 40GB 磁盘上长期稳定运行！** 🎊

