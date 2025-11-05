# Embedding 维度配置修复报告

> **⚠️ 配置更新说明（2025-11-05）**
> 本文档是历史修复报告，文中使用 `SF_EMBEDDING_MODEL` 是修复时的变量名。
> 当前项目已更新为功能导向命名：`EMBEDDING_MODEL`、`EMBEDDING_API_KEY`、`EMBEDDING_BASE_URL`。
> 详见 [配置重构总结](./config_refactor/08_final_summary.md)。

## 问题总结

修复了 `docker-compose.yml`、`docker-compose.dev.yml` 和 `src/rag.py` 中硬编码 `EMBEDDING_DIM=4096` 的配置不一致问题。

## 修复的 Bug

### Bug 1: docker-compose.yml 硬编码维度

**问题**：
- 第 49 行和第 204 行硬编码 `EMBEDDING_DIM=4096`
- 但 `env.example` 默认是 `EMBEDDING_DIM=1024`
- 导致用户即使在 `.env` 中设置 1024，实际运行时仍使用 4096

**修复**：
```yaml
# 修复前
- EMBEDDING_DIM=4096

# 修复后
- EMBEDDING_DIM=${EMBEDDING_DIM:-1024}
```

### Bug 2: docker-compose.dev.yml 硬编码维度

**问题**：
- 第 31 行和第 179 行同样硬编码 `EMBEDDING_DIM=4096`
- 开发环境与生产环境存在相同的配置不一致问题

**修复**：
```yaml
# 修复前
- EMBEDDING_DIM=4096

# 修复后
- EMBEDDING_DIM=${EMBEDDING_DIM:-1024}
```

### Bug 3: src/rag.py 硬编码日志输出

**问题**：
- 第 84 行日志输出硬编码 `dim={4096}`
- 当实际使用 1024 维度时，日志会误导用户

**修复**：
```python
# 修复前
logger.info(f"🔤 Embedding: {sf_embedding_model} (dim={4096})")

# 修复后
embedding_dim = os.getenv("EMBEDDING_DIM", "1024")
logger.info(f"🔤 Embedding: {sf_embedding_model} (dim={embedding_dim})")
```

## 修复的文件

1. ✅ `docker-compose.yml` (2 处)
2. ✅ `docker-compose.dev.yml` (2 处)
3. ✅ `src/rag.py` (1 处)
4. ✅ `CLAUDE.md` (更新文档说明)
5. ✅ 新增 `scripts/verify_embedding_config.sh` (配置验证工具)

## 配置建议

### 推荐配置（轻量级）

适用于大多数场景，性能和精度平衡：

```bash
# .env
EMBEDDING_DIM=1024
SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
RERANK_MODEL=Qwen/Qwen2-7B-Instruct  # 配合 Rerank 提升质量
```

### 高精度配置

适用于对精度要求极高的场景：

```bash
# .env
EMBEDDING_DIM=4096
SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B

# ⚠️ 注意：
# - 需要更多计算资源
# - 如果使用 PostgreSQL，无法创建 HNSW 索引（限制 2000 维度）
# - 建议使用 Qdrant 向量存储（支持 4096 维度索引）
```

## 验证配置一致性

使用新增的验证脚本检查配置：

```bash
./scripts/verify_embedding_config.sh
```

该脚本会检查：
1. `.env` 文件中的配置
2. Embedding 模型与维度是否匹配
3. docker-compose 配置是否一致
4. 数据库实际使用的维度
5. 是否使用了不推荐的配置组合

## 迁移指南

如果你之前使用了硬编码的 4096 维度：

### 选项 A：继续使用 4096 维度

在 `.env` 中显式设置：

```bash
echo "EMBEDDING_DIM=4096" >> .env
# 或修改 .env 文件，取消注释并设置为 4096
```

### 选项 B：切换到 1024 维度（推荐）

1. 停止服务：
   ```bash
   docker compose down
   ```

2. 删除数据库（维度改变需要重新初始化）：
   ```bash
   docker volume rm rag-api_postgres_data rag-api_neo4j_data
   ```

3. 修改 `.env`：
   ```bash
   EMBEDDING_DIM=1024
   SF_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-0.6B
   RERANK_MODEL=Qwen/Qwen2-7B-Instruct
   ```

4. 重新启动：
   ```bash
   docker compose up -d
   ```

5. 验证配置：
   ```bash
   ./scripts/verify_embedding_config.sh
   ```

## 为什么需要这个修复？

1. **配置一致性**：确保 `.env` 中的配置真正生效
2. **避免意外错误**：防止维度不匹配导致向量插入失败
3. **提高透明度**：日志输出反映实际使用的配置
4. **灵活性**：用户可以自由选择 1024 或 4096 维度
5. **符合最佳实践**：与 `env.example` 默认配置保持一致

## 影响范围

- ✅ 不影响现有已部署的系统（因为之前硬编码 4096，现在可以通过 `.env` 继续使用 4096）
- ✅ 新部署默认使用 1024 维度（与 `env.example` 一致）
- ✅ 用户可以通过 `.env` 自由切换维度
- ⚠️ 改变维度需要重新初始化数据库

## 相关文档

- `CLAUDE.md` - 完整的配置说明和陷阱
- `env.example` - 推荐的环境变量配置
- `docs/DEPLOYMENT_EXTERNAL_STORAGE.md` - 外部存储配置指南
- `scripts/verify_embedding_config.sh` - 配置验证工具

---

**修复日期**：2025-10-30  
**修复人**：Claude  
**相关 Issue**：配置不一致问题

