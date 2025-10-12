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
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（使用 pip 安装更可靠）
RUN pip install --no-cache-dir uv

# 复制项目文件
COPY pyproject.toml ./
COPY main.py ./
COPY src/ ./src/

# 使用 uv 安装依赖
RUN uv sync

# 创建必要的目录
RUN mkdir -p /app/rag_local_storage /app/output /app/logs

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动命令
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

