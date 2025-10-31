# 使用官方 Python 3.10 基础镜像
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    git \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 创建字体符号链接（RAG-Anything 期望的路径）
RUN mkdir -p /usr/share/fonts/wqy-microhei && \
    ln -s /usr/share/fonts/truetype/wqy/wqy-microhei.ttc /usr/share/fonts/wqy-microhei/wqy-microhei.ttc

# 安装 uv（使用 pip 安装更可靠）
RUN pip install --no-cache-dir uv

# === 依赖层（多阶段优化）：最大化缓存复用 ===
# 策略：先复制 uv.lock（锁定依赖版本），只有它变化才重新安装
# pyproject.toml 的 metadata 变化（版本号、描述等）不会触发依赖重装
COPY uv.lock* ./

# 第一阶段：安装依赖（基于 lock 文件）
# --frozen: 严格按 lock 文件安装，不解析 pyproject.toml
# 优点：只有依赖版本变化才重建，添加注释或修改版本号不会触发
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen || echo "⚠️ uv.lock not found, will sync with pyproject.toml"

# 第二阶段：复制 pyproject.toml（metadata 变化不影响依赖层）
COPY pyproject.toml ./

# 同步 metadata（如果 pyproject.toml 有新依赖，补充安装）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync

# === 代码层：放在最后，不影响依赖层缓存 ===
# 仅修改代码不影响依赖层，构建快速
COPY main.py ./
COPY src/ ./src/
COPY api/ ./api/

# 创建必要的目录
RUN mkdir -p /app/rag_local_storage /app/output /app/logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动命令
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

