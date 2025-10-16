#!/bin/bash

###############################################################################
# RAG API 智能更新脚本 (远端 SSH 部署优化)
# 用途: 拉取最新代码，利用 Docker 缓存快速重建
# 部署流程: git push → SSH pull → build → run
# 特性: 
#   1. 自动启用 BuildKit，获得更好的缓存和并行构建
#   2. 利用持久化卷 model_cache 保留包缓存（跨容器）
#   3. 智能检测是否需要完整重建
#   4. 详细的构建时间和缓存统计
###############################################################################

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# BuildKit 支持函数
enable_buildkit() {
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    export BUILDKIT_PROGRESS=plain
}

# 检查 model_cache 卷是否存在（判断是否首次构建）
is_first_build() {
    if [ ! -d "./model_cache" ]; then
        return 0  # 目录不存在，首次构建
    fi
    
    if [ -z "$(ls -A ./model_cache 2>/dev/null)" ]; then
        return 0  # 目录为空，视为首次构建
    fi
    
    return 1  # 缓存存在，非首次构建
}

# 获取上次构建的时间戳
get_last_build_time() {
    if [ -f ".docker/last_build_time" ]; then
        cat ".docker/last_build_time"
    else
        echo "0"
    fi
}

# 保存本次构建时间戳
save_build_time() {
    mkdir -p ".docker"
    date +%s > ".docker/last_build_time"
}

echo -e "${BLUE}======================================================================"
echo "                   RAG API 智能更新 (远端 SSH 部署优化)"
echo -e "======================================================================${NC}"
echo ""

# 启用 BuildKit
enable_buildkit
echo -e "${GREEN}✓ 已启用 Docker BuildKit${NC}"
echo ""

# 1. 备份当前数据
echo -e "${YELLOW}[1/7] 备份当前数据...${NC}"
if [ -f "./scripts/backup.sh" ]; then
    bash ./scripts/backup.sh > /dev/null 2>&1 || true
else
    echo -e "${YELLOW}  ⚠ 备份脚本不存在，跳过备份${NC}"
fi
echo -e "${GREEN}✓ 备份完成${NC}"
echo ""

# 2. 拉取最新代码
echo -e "${YELLOW}[2/7] 拉取最新代码...${NC}"
git fetch origin 2>/dev/null || true
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
git pull origin "$BRANCH" 2>/dev/null || true
NEW_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
echo -e "${GREEN}✓ 代码已更新 (commit: ${NEW_COMMIT})${NC}"
echo ""

# 3. 检查构建缓存情况
echo -e "${YELLOW}[3/7] 检查构建缓存...${NC}"
CACHE_STATUS="有效"
CACHE_SIZE="0B"

if is_first_build; then
    echo -e "${YELLOW}  ⚠ 首次构建，将下载所有依赖...${NC}"
    CACHE_STATUS="无（首次）"
    IS_FIRST=true
else
    CACHE_SIZE=$(du -sh ./model_cache 2>/dev/null | awk '{print $1}')
    echo -e "${GREEN}✓ 检测到缓存 (大小: ${CACHE_SIZE})${NC}"
    IS_FIRST=false
fi
echo ""

# 4. 清理系统空间（但保留 model_cache）
echo -e "${YELLOW}[4/7] 清理旧镜像...${NC}"
# 清理悬空镜像和卷，但不清理模型缓存
docker image prune -f > /dev/null 2>&1 || true
docker container prune -f > /dev/null 2>&1 || true

# 统计可释放空间
PRUNE_OUTPUT=$(docker system df 2>/dev/null || echo "")
echo -e "${GREEN}✓ 旧镜像已清理${NC}"
echo ""

# 5. 停止当前服务
echo -e "${YELLOW}[5/7] 停止当前服务...${NC}"
docker compose down > /dev/null 2>&1 || true
sleep 2  # 等待容器完全停止
echo -e "${GREEN}✓ 服务已停止${NC}"
echo ""

# 6. 重新构建镜像
echo -e "${YELLOW}[6/7] 重新构建镜像...${NC}"
if [ "$IS_FIRST" = true ]; then
    echo -e "${BLUE}  提示: 首次构建，需要下载所有依赖（约20-40分钟，取决于网络）${NC}"
    echo -e "${BLUE}       Python 包会保存到 ./model_cache，供后续重用${NC}"
else
    echo -e "${BLUE}  提示: 非首次构建，将复用已缓存的包（约2-5分钟）${NC}"
    echo -e "${BLUE}       若仅代码变化，构建会更快{{NC}"
fi
echo -e "${BLUE}  提示: BuildKit 启用，支持并行构建和增强缓存${NC}"
echo ""

BUILD_START=$(date +%s%N)

# 执行构建，启用 BuildKit 缓存层
docker compose build

BUILD_END=$(date +%s%N)

# 计算构建时间
BUILD_TIME_MS=$(( (BUILD_END - BUILD_START) / 1000000 ))
BUILD_TIME_S=$(( BUILD_TIME_MS / 1000 ))
BUILD_TIME_MS=$(( BUILD_TIME_MS % 1000 ))

echo ""
echo -e "${GREEN}✓ 构建完成，耗时 ${BUILD_TIME_S}s ${BUILD_TIME_MS}ms${NC}"
echo ""

# 保存构建时间戳
save_build_time

# 7. 启动新服务
echo -e "${YELLOW}[7/7] 启动新服务...${NC}"
docker compose up -d
echo -e "${GREEN}✓ 服务启动中...${NC}"
echo ""

# 等待服务就绪
echo -e "${YELLOW}等待服务就绪（最多 60 秒）...${NC}"
MAX_RETRIES=20
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost:8000/ &> /dev/null; then
        echo -e "${GREEN}✓ 服务已就绪！${NC}"
        break
    fi
    echo -n "."
    sleep 3
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}✗ 服务启动超时，请检查日志: docker compose logs rag-api${NC}"
fi

echo ""
echo -e "${GREEN}======================================================================"
echo "                   更新完成！"
echo -e "======================================================================${NC}"
echo ""
echo -e "构建耗时:           ${BUILD_TIME_S}s ${BUILD_TIME_MS}ms"
echo -e "首次构建:           $([ "$IS_FIRST" = true ] && echo "是" || echo "否")"
echo -e "缓存状态:           ${CACHE_STATUS}"
echo -e "缓存大小:           ${CACHE_SIZE}"
echo -e "磁盘可用:           $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"
echo -e "镜像大小:           $(docker images rag-api-rag-api:latest --format '{{.Size}}' 2>/dev/null || echo 'N/A')"
echo ""
echo "📋 关键信息:"
echo "  • model_cache/ 目录保存 Python 包，跨容器重用"
echo "  • 后续更新会复用缓存包，加快构建速度"
echo "  • 若想完整重建，删除 model_cache/ 后重新运行此脚本"
echo ""
echo "🔧 常用命令:"
echo "  查看服务状态:     docker compose ps"
echo "  查看实时日志:     docker compose logs -f rag-api"
echo "  查看性能统计:     docker stats --no-stream"
echo "  查看缓存大小:     du -sh ./model_cache"
echo "  清理缓存重建:     rm -rf ./model_cache && bash ./scripts/update.sh"
echo ""
