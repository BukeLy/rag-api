#!/bin/bash

# 租户配置隔离测试脚本
# 测试 LLM/Embedding/Rerank/DeepSeek-OCR/MinerU 配置隔离功能

set -e

API_BASE="${API_BASE:-http://localhost:8000}"
TENANT_A="test_tenant_a"
TENANT_B="test_tenant_b"

echo "=========================================="
echo "租户配置隔离测试"
echo "API Base: $API_BASE"
echo "=========================================="

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

log_error() {
    echo -e "${RED}✗ $1${NC}"
}

log_info() {
    echo -e "${YELLOW}ℹ $1${NC}"
}

# 1. 测试：租户 A 配置独立的 DeepSeek-OCR API key
echo -e "\n========== 测试 1: 租户 A 配置 DeepSeek-OCR =========="
log_info "为租户 A 设置 DeepSeek-OCR 配置..."

curl -s -X PUT "$API_BASE/tenants/$TENANT_A/config" \
  -H "Content-Type: application/json" \
  -d '{
    "ds_ocr_config": {
      "api_key": "sk-tenant-a-ds-ocr-key",
      "base_url": "https://api.siliconflow.cn/v1",
      "model": "deepseek-ai/DeepSeek-OCR",
      "timeout": 90
    }
  }' | python3 -m json.tool

if [ $? -eq 0 ]; then
    log_success "租户 A 配置成功"
else
    log_error "租户 A 配置失败"
    exit 1
fi

# 2. 测试：租户 B 配置独立的 MinerU API token
echo -e "\n========== 测试 2: 租户 B 配置 MinerU =========="
log_info "为租户 B 设置 MinerU 配置..."

curl -s -X PUT "$API_BASE/tenants/$TENANT_B/config" \
  -H "Content-Type: application/json" \
  -d '{
    "mineru_config": {
      "api_token": "tenant-b-mineru-token",
      "base_url": "https://mineru.net",
      "model_version": "vlm",
      "timeout": 120
    }
  }' | python3 -m json.tool

if [ $? -eq 0 ]; then
    log_success "租户 B 配置成功"
else
    log_error "租户 B 配置失败"
    exit 1
fi

# 3. 测试：查询租户 A 配置（验证 API key 脱敏）
echo -e "\n========== 测试 3: 查询租户 A 配置 =========="
log_info "查询租户 A 配置..."

RESPONSE=$(curl -s "$API_BASE/tenants/$TENANT_A/config")
echo "$RESPONSE" | python3 -m json.tool

# 验证 API key 脱敏
if echo "$RESPONSE" | grep -q "sk-\*\*\*"; then
    log_success "API key 正确脱敏"
else
    log_error "API key 脱敏失败"
fi

# 验证 merged_config 包含 ds_ocr
if echo "$RESPONSE" | grep -q '"ds_ocr"'; then
    log_success "merged_config 包含 ds_ocr"
else
    log_error "merged_config 缺少 ds_ocr"
fi

# 4. 测试：查询租户 B 配置（验证 api_token 脱敏）
echo -e "\n========== 测试 4: 查询租户 B 配置 =========="
log_info "查询租户 B 配置..."

RESPONSE=$(curl -s "$API_BASE/tenants/$TENANT_B/config")
echo "$RESPONSE" | python3 -m json.tool

# 验证 api_token 脱敏
if echo "$RESPONSE" | grep -q "ten\*\*\*"; then
    log_success "API token 正确脱敏"
else
    log_error "API token 脱敏失败"
fi

# 验证 merged_config 包含 mineru
if echo "$RESPONSE" | grep -q '"mineru"'; then
    log_success "merged_config 包含 mineru"
else
    log_error "merged_config 缺少 mineru"
fi

# 5. 测试：租户 A 配置 LLM（验证多配置同时存在）
echo -e "\n========== 测试 5: 租户 A 添加 LLM 配置 =========="
log_info "为租户 A 添加 LLM 配置..."

curl -s -X PUT "$API_BASE/tenants/$TENANT_A/config" \
  -H "Content-Type: application/json" \
  -d '{
    "llm_config": {
      "provider": "openai",
      "model": "gpt-4",
      "api_key": "sk-tenant-a-llm-key",
      "base_url": "https://api.openai.com/v1"
    },
    "ds_ocr_config": {
      "api_key": "sk-tenant-a-ds-ocr-key",
      "base_url": "https://api.siliconflow.cn/v1",
      "model": "deepseek-ai/DeepSeek-OCR",
      "timeout": 90
    }
  }' | python3 -m json.tool

if [ $? -eq 0 ]; then
    log_success "租户 A 多配置更新成功"
else
    log_error "租户 A 多配置更新失败"
    exit 1
fi

# 6. 测试：验证租户 A 的 merged_config 包含 5 个配置
echo -e "\n========== 测试 6: 验证租户 A merged_config =========="
log_info "查询租户 A 的 merged_config..."

RESPONSE=$(curl -s "$API_BASE/tenants/$TENANT_A/config")
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
merged = data.get('merged_config', {})
print('merged_config keys:', list(merged.keys()))

# 验证 5 个配置都存在
required = ['llm', 'embedding', 'rerank', 'ds_ocr', 'mineru']
missing = [k for k in required if k not in merged]

if missing:
    print(f'❌ 缺失配置: {missing}')
    sys.exit(1)
else:
    print('✅ 所有配置都存在')
"

if [ $? -eq 0 ]; then
    log_success "租户 A merged_config 包含 5 个配置"
else
    log_error "租户 A merged_config 缺少配置"
fi

# 7. 测试：刷新配置缓存
echo -e "\n========== 测试 7: 刷新租户配置缓存 =========="
log_info "刷新租户 A 配置缓存..."

curl -s -X POST "$API_BASE/tenants/$TENANT_A/config/refresh" | python3 -m json.tool

if [ $? -eq 0 ]; then
    log_success "配置缓存刷新成功"
else
    log_error "配置缓存刷新失败"
fi

# 8. 测试：清理租户配置（降级到全局配置）
echo -e "\n========== 测试 8: 删除租户配置 =========="
log_info "删除租户 A 配置..."

curl -s -X DELETE "$API_BASE/tenants/$TENANT_A/config" | python3 -m json.tool

if [ $? -eq 0 ]; then
    log_success "租户 A 配置删除成功"
else
    log_error "租户 A 配置删除失败"
fi

log_info "删除租户 B 配置..."

curl -s -X DELETE "$API_BASE/tenants/$TENANT_B/config" | python3 -m json.tool

if [ $? -eq 0 ]; then
    log_success "租户 B 配置删除成功"
else
    log_error "租户 B 配置删除失败"
fi

# 9. 测试：验证配置降级（租户配置删除后应返回 404）
echo -e "\n========== 测试 9: 验证配置降级 =========="
log_info "查询已删除的租户 A 配置..."

HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$API_BASE/tenants/$TENANT_A/config")

if [ "$HTTP_CODE" == "404" ]; then
    log_success "配置降级正常（返回 404）"
else
    log_error "配置降级异常（期望 404，实际 $HTTP_CODE）"
fi

echo -e "\n=========================================="
echo "测试完成！"
echo "=========================================="
