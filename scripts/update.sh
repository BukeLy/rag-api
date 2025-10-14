#!/bin/bash

###############################################################################
# RAG API 智能更新脚本 (适配 ECR 部署)
# 用途: 拉取最新代码，利用 Docker 缓存快速重建
###############################################################################

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================================================"
echo "                   RAG API 智能更新"
echo -e "======================================================================${NC}"
echo ""

# 1. 备份当前数据
echo -e "${YELLOW}[1/6] 备份当前数据...${NC}"
if [ -f "./scripts/backup.sh" ]; then
    bash ./scripts/backup.sh
else
    echo -e "${YELLOW}备份脚本不存在，跳过备份${NC}"
fi

# 2. 拉取最新代码
echo -e "${YELLOW}[2/6] 拉取最新代码...${NC}"
git fetch origin
git pull origin main

# 3. 清理悬空镜像（保留当前使用的镜像）
echo -e "${YELLOW}[3/6] 清理悬空镜像...${NC}"
docker image prune -f
CLEANED=$(docker system df -v | grep "Build Cache" | awk '{print $4}')
echo -e "${GREEN}✓ 已清理构建缓存${NC}"

# 4. 停止当前服务
echo -e "${YELLOW}[4/6] 停止当前服务...${NC}"
docker compose down

# 5. 重新构建镜像（利用缓存）
echo -e "${YELLOW}[5/6] 重新构建镜像（利用缓存加速）...${NC}"
echo -e "${BLUE}提示: 如果只修改了代码，构建会很快（1-2分钟）${NC}"
echo -e "${BLUE}提示: 如果修改了依赖，需要重新下载包（15分钟）${NC}"
BUILD_START=$(date +%s)
docker compose build
BUILD_END=$(date +%s)
BUILD_TIME=$((BUILD_END - BUILD_START))
echo -e "${GREEN}✓ 构建完成，耗时 ${BUILD_TIME}s${NC}"

# 6. 启动新服务
echo -e "${YELLOW}[6/6] 启动新服务...${NC}"
docker compose up -d

# 7. 等待服务就绪
echo -e "${YELLOW}等待服务就绪...${NC}"
for i in {1..20}; do
    if curl -f http://localhost:8000/ &> /dev/null; then
        echo -e "${GREEN}✓ 服务已就绪！${NC}"
        break
    fi
    echo -n "."
    sleep 3
done

echo ""
echo -e "${GREEN}======================================================================"
echo "                   更新完成！"
echo -e "======================================================================${NC}"
echo ""
echo -e "构建耗时: ${BUILD_TIME}s"
echo -e "磁盘使用: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"
echo -e "镜像大小: $(docker images rag-api-rag-api:latest --format '{{.Size}}')"
echo ""
echo "查看服务状态: docker compose ps"
echo "查看日志:     docker compose logs -f"
echo "查看性能:     docker stats --no-stream"
