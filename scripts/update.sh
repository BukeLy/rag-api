#!/bin/bash

###############################################################################
# RAG API 智能更新脚本
# 用途: 拉取最新代码，智能判断是否需要重建镜像
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

# 0. 获取当前文件的 Git Hash
echo -e "${YELLOW}[1/7] 检测变更文件...${NC}"
BEFORE_DEPS_HASH=$(git log -1 --format="%H" -- pyproject.toml Dockerfile 2>/dev/null || echo "none")
BEFORE_CODE_HASH=$(git log -1 --format="%H" -- main.py src/ api/ 2>/dev/null || echo "none")

# 1. 备份当前数据
echo -e "${YELLOW}[2/7] 备份当前数据...${NC}"
if [ -f "./scripts/backup.sh" ]; then
    bash ./scripts/backup.sh
else
    echo -e "${YELLOW}备份脚本不存在，跳过备份${NC}"
fi

# 2. 拉取最新代码
echo -e "${YELLOW}[3/7] 拉取最新代码...${NC}"
git fetch origin
git pull origin main

# 3. 检测变更类型
AFTER_DEPS_HASH=$(git log -1 --format="%H" -- pyproject.toml Dockerfile 2>/dev/null || echo "none")
AFTER_CODE_HASH=$(git log -1 --format="%H" -- main.py src/ api/ 2>/dev/null || echo "none")

NEED_REBUILD=false
if [ "$BEFORE_DEPS_HASH" != "$AFTER_DEPS_HASH" ]; then
    echo -e "${YELLOW}检测到依赖文件变更 (pyproject.toml 或 Dockerfile)${NC}"
    NEED_REBUILD=true
fi

# 4. 根据变更类型决定操作
if [ "$NEED_REBUILD" = true ]; then
    echo -e "${YELLOW}[4/7] 清理旧镜像和缓存...${NC}"
    docker compose down
    docker system prune -f
    docker builder prune -f
    
    echo -e "${YELLOW}[5/7] 重新构建镜像 (依赖变更)...${NC}"
    docker compose build
    
    echo -e "${YELLOW}[6/7] 启动新服务...${NC}"
    docker compose up -d
else
    echo -e "${GREEN}✓ 依赖未变更，无需重建镜像${NC}"
    
    if [ "$BEFORE_CODE_HASH" != "$AFTER_CODE_HASH" ]; then
        echo -e "${YELLOW}[4/7] 检测到代码变更${NC}"
        echo -e "${YELLOW}[5/7] 跳过镜像构建${NC}"
        echo -e "${YELLOW}[6/7] 重启容器以加载新代码...${NC}"
        docker compose restart
    else
        echo -e "${GREEN}✓ 代码未变更，无需操作${NC}"
        echo -e "${YELLOW}[4/7] 跳过${NC}"
        echo -e "${YELLOW}[5/7] 跳过${NC}"
        echo -e "${YELLOW}[6/7] 跳过${NC}"
    fi
fi

# 7. 等待服务就绪
echo -e "${YELLOW}[7/7] 等待服务就绪...${NC}"
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
echo "磁盘使用: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"
echo "镜像大小: $(docker images rag-api-rag-api:latest --format '{{.Size}}')"
echo ""
echo "查看服务状态: docker compose ps"
echo "查看日志:     docker compose logs -f"
echo "查看性能:     docker stats --no-stream"
