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

# === 依赖层：只复制依赖文件，这层会被有效缓存 ===
# 远端部署优化：当 pyproject.toml/uv.lock 不变时，此层会被重用
COPY pyproject.toml uv.lock* ./

# 使用 uv 安装依赖
# 关键优化：BuildKit 缓存挂载 + 持久化卷
# 1. 通过 BuildKit 的 cache mount 保留构建期间的缓存
# 2. /root/.cache/uv 会映射到宿主机的 ./model_cache（docker-compose.yml 中定义）
# 3. 下次构建时会重用已缓存的包，大幅加快速度
# 4. 即使容器销毁，宿主机上的 ./model_cache 依然保留
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

