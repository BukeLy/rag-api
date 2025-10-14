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

# 只复制依赖文件（用于缓存层）
COPY pyproject.toml uv.lock* ./

# 使用 uv 安装依赖（这层会被缓存，除非 pyproject.toml 变化）
RUN uv sync

# 创建必要的目录
RUN mkdir -p /app/rag_local_storage /app/output /app/logs

# 代码将通过 volume 挂载，不在这里 COPY

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 启动命令
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

