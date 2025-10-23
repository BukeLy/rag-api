#!/bin/bash
# Development Environment Startup Script
# 启动dev环境（代码热重载）

set -e

echo "🚀 Starting RAG API Development Environment..."
echo "================================================"
echo "特性："
echo "  - 代码外挂：修改立即生效"
echo "  - 热重载：自动检测代码变化"
echo "  - 完整测试工具：test_api.py, test_concurrent_perf.sh等"
echo "================================================"
echo ""

# 检查.env文件
if [ ! -f .env ]; then
    echo "❌ .env file not found. Please copy from env.example:"
    echo "   cp env.example .env"
    exit 1
fi

# 启动开发环境
docker compose -f docker-compose.dev.yml up --build

# 清理
trap 'docker compose -f docker-compose.dev.yml down' EXIT
