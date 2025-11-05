#!/bin/bash

###############################################################################
# RAG API 监控脚本
# 用途: 监控服务状态、资源使用情况
###############################################################################

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "======================================================================"
echo "                   RAG API 服务监控"
echo "======================================================================"
echo ""

# 1. Docker 服务状态
echo -e "${BLUE}[1] Docker 服务状态${NC}"
docker compose ps
echo ""

# 2. 容器资源使用
echo -e "${BLUE}[2] 容器资源使用${NC}"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}" | grep rag
echo ""

# 3. API 健康检查
echo -e "${BLUE}[3] API 健康检查${NC}"
if curl -s -f http://localhost:8000/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ API 服务正常${NC}"
    curl -s http://localhost:8000/ | jq .
else
    echo -e "${RED}✗ API 服务异常${NC}"
fi
echo ""

# 4. 磁盘使用
echo -e "${BLUE}[4] 磁盘使用情况${NC}"
echo "向量数据库: $(du -sh ./rag_local_storage 2>/dev/null | cut -f1)"
echo "输出文件:   $(du -sh ./output 2>/dev/null | cut -f1)"
echo "日志文件:   $(du -sh ./logs 2>/dev/null | cut -f1)"
echo ""

# 5. 最近错误日志
echo -e "${BLUE}[5] 最近错误日志（最新 10 条）${NC}"
docker compose logs --tail=10 | grep -i "error\|warning\|fail" || echo "无错误日志"
echo ""

# 6. 系统资源
echo -e "${BLUE}[6] 系统资源总览${NC}"
echo "CPU 使用率:"
top -bn1 | grep "Cpu(s)" | sed "s/.*, *\([0-9.]*\)%* id.*/\1/" | awk '{print "  " 100 - $1"%"}'

echo "内存使用:"
free -h | awk 'NR==2{printf "  %s / %s (%.2f%%)\n", $3,$2,$3*100/$2 }'

echo "磁盘使用:"
df -h / | awk 'NR==2{printf "  %s / %s (%s)\n", $3,$2,$5}'

echo ""
echo "======================================================================"
echo "提示: 使用 'docker compose logs -f' 实时查看日志"
echo "======================================================================"

