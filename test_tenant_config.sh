#!/bin/bash
#
# 租户配置热重载功能测试脚本
#
# 用法: ./test_tenant_config.sh
#

set -e  # 遇到错误立即退出

API_BASE="http://localhost:8000"
TENANT_ID="demo"

echo "========================================="
echo "测试租户配置热重载功能"
echo "========================================="
echo ""

# 1. 检查服务状态
echo "[1/6] 检查服务状态..."
curl -s "$API_BASE/" | python3 -m json.tool
echo ""

# 2. 创建租户配置（使用 GPT-4）
echo "[2/6] 创建租户配置（GPT-4 + 高配额）..."
curl -s -X PUT "$API_BASE/tenants/$TENANT_ID/config" \
  -H "Content-Type: application/json" \
  -d '{
    "llm_config": {
      "provider": "openai",
      "model": "gpt-4",
      "api_key": "sk-test-key-12345678"
    },
    "quota": {
      "daily_queries": 5000,
      "storage_mb": 2000
    }
  }' | python3 -m json.tool
echo ""

# 3. 获取租户配置
echo "[3/6] 获取租户配置（验证创建成功）..."
curl -s "$API_BASE/tenants/$TENANT_ID/config" | python3 -m json.tool
echo ""

# 4. 更新租户配置（修改配额）
echo "[4/6] 更新租户配置（修改配额）..."
curl -s -X PUT "$API_BASE/tenants/$TENANT_ID/config" \
  -H "Content-Type: application/json" \
  -d '{
    "quota": {
      "daily_queries": 10000
    }
  }' | python3 -m json.tool
echo ""

# 5. 刷新配置缓存
echo "[5/6] 刷新配置缓存..."
curl -s -X POST "$API_BASE/tenants/$TENANT_ID/config/refresh" | python3 -m json.tool
echo ""

# 6. 删除租户配置
echo "[6/6] 删除租户配置（恢复全局配置）..."
curl -s -X DELETE "$API_BASE/tenants/$TENANT_ID/config" | python3 -m json.tool
echo ""

# 7. 验证删除后返回 404
echo "[验证] 删除后获取配置应返回 404..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE/tenants/$TENANT_ID/config")
if [ "$STATUS" -eq 404 ]; then
    echo "✓ 删除成功，返回 404"
else
    echo "✗ 删除验证失败，返回状态码: $STATUS"
fi
echo ""

echo "========================================="
echo "测试完成！"
echo "========================================="
