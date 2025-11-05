#!/bin/bash

# 部署前检查脚本
echo "🔍 部署前环境检查..."

# 检查必要的环境变量
required_vars=("MINERU_API_TOKEN" "FILE_SERVICE_BASE_URL" "MINERU_MODE")

for var in "${required_vars[@]}"; do
    value=$(grep "^$var=" .env 2>/dev/null | cut -d '=' -f2)
    if [ -z "$value" ] || [[ "$value" = "your_"* ]]; then
        echo "❌ $var 未正确配置"
        exit 1
    else
        echo "✅ $var: 已配置"
    fi
done

# 检查 FILE_SERVICE_BASE_URL 是否使用 8000 端口
FILE_URL=$(grep "^FILE_SERVICE_BASE_URL=" .env 2>/dev/null | cut -d '=' -f2)
if [[ "$FILE_URL" != *":8000" ]]; then
    echo "❌ FILE_SERVICE_BASE_URL 必须使用 8000 端口"
    exit 1
fi

# 检查 MINERU_MODE 是否为 remote
MINERU_MODE=$(grep "^MINERU_MODE=" .env 2>/dev/null | cut -d '=' -f2)
if [[ "$MINERU_MODE" != "remote" ]]; then
    echo "❌ MINERU_MODE 必须设置为 'remote'"
    exit 1
fi

# 检查网络连通性
echo "🌐 测试 MinerU API 连通性..."
if curl -s https://mineru.net/api/v4/health > /dev/null; then
    echo "✅ MinerU API 可达"
else
    echo "❌ MinerU API 无法访问，检查网络"
    exit 1
fi

echo "✅ 环境检查通过，可以部署"
