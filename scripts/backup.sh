#!/bin/bash

###############################################################################
# RAG API 备份脚本
# 用途: 备份向量数据库和配置文件
###############################################################################

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="rag_backup_${TIMESTAMP}.tar.gz"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}======================================================================"
echo "                   RAG API 数据备份"
echo -e "======================================================================${NC}"
echo ""

# 创建备份目录
mkdir -p $BACKUP_DIR

echo -e "${YELLOW}[1/3] 备份向量数据库...${NC}"
tar -czf "${BACKUP_DIR}/rag_storage_${TIMESTAMP}.tar.gz" \
    -C . rag_local_storage 2>/dev/null || echo "向量数据库为空"

echo -e "${YELLOW}[2/3] 备份输出文件...${NC}"
tar -czf "${BACKUP_DIR}/output_${TIMESTAMP}.tar.gz" \
    -C . output 2>/dev/null || echo "输出目录为空"

echo -e "${YELLOW}[3/3] 备份配置文件...${NC}"
tar -czf "${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz" \
    .env docker-compose.yml 2>/dev/null || echo "配置文件不存在"

# 合并所有备份
echo -e "${YELLOW}合并备份文件...${NC}"
tar -czf "${BACKUP_DIR}/${BACKUP_FILE}" \
    -C ${BACKUP_DIR} \
    "rag_storage_${TIMESTAMP}.tar.gz" \
    "output_${TIMESTAMP}.tar.gz" \
    "config_${TIMESTAMP}.tar.gz"

# 清理临时文件
rm -f "${BACKUP_DIR}/rag_storage_${TIMESTAMP}.tar.gz"
rm -f "${BACKUP_DIR}/output_${TIMESTAMP}.tar.gz"
rm -f "${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz"

# 显示备份信息
BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_FILE}" | cut -f1)

echo ""
echo -e "${GREEN}✓ 备份完成！${NC}"
echo -e "  文件: ${BACKUP_DIR}/${BACKUP_FILE}"
echo -e "  大小: ${BACKUP_SIZE}"
echo ""

# 保留最近 7 天的备份
echo -e "${YELLOW}清理旧备份（保留最近 7 天）...${NC}"
find ${BACKUP_DIR} -name "rag_backup_*.tar.gz" -mtime +7 -delete
echo -e "${GREEN}✓ 清理完成${NC}"

echo ""
echo -e "${BLUE}======================================================================"
echo "恢复备份: tar -xzf ${BACKUP_DIR}/${BACKUP_FILE}"
echo -e "======================================================================${NC}"

