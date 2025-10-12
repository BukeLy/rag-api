#!/bin/bash

###############################################################################
# RAG API 更新脚本
# 用途: 拉取最新代码并重新部署
###############################################################################

set -e

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================================================"
echo "                   RAG API 更新部署"
echo -e "======================================================================${NC}"
echo ""

# 1. 备份当前数据
echo -e "${YELLOW}[1/6] 备份当前数据...${NC}"
if [ -f "./scripts/backup.sh" ]; then
    bash ./scripts/backup.sh
else
    echo -e "${RED}警告: 备份脚本不存在，跳过备份${NC}"
fi

# 2. 拉取最新代码
echo -e "${YELLOW}[2/6] 拉取最新代码...${NC}"
git fetch origin
git pull origin main

# 3. 停止当前服务
echo -e "${YELLOW}[3/6] 停止当前服务...${NC}"
docker compose down

# 4. 重新构建镜像
echo -e "${YELLOW}[4/6] 重新构建镜像...${NC}"
docker compose build --no-cache

# 5. 启动新服务
echo -e "${YELLOW}[5/6] 启动新服务...${NC}"
docker compose up -d

# 6. 等待服务就绪
echo -e "${YELLOW}[6/6] 等待服务就绪...${NC}"
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
echo "查看服务状态: docker compose ps"
echo "查看日志:     docker compose logs -f"

