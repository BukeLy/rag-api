#!/bin/bash
# 性能监控脚本

SSH_KEY="/Users/chengjie/Downloads/chengjie.pem"
SERVER="root@45.78.223.205"

echo "🔍 RAG API 性能监控"
echo "=" | awk '{s=$0; while (length(s)<60) s=s$0; print substr(s,1,60)}'

# 实时监控容器资源
ssh -i $SSH_KEY $SERVER "docker stats rag-api --no-stream --format 'table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.NetIO}}'"

