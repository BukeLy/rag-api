#!/bin/bash

echo ""
echo "========================================================================"
echo "🚀 RAG API 端到端测试"
echo "========================================================================"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 测试 1: 健康检查
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 测试 1: 健康检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

health_response=$(curl -s http://localhost:8000/)
if echo "$health_response" | grep -q "running"; then
    echo -e "${GREEN}✓ 健康检查通过${NC}"
    echo "  响应: $health_response"
else
    echo -e "${RED}✗ 健康检查失败${NC}"
    exit 1
fi

# 测试 2: 上传文档
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📤 测试 2: 上传文档（纯文本 - LightRAG 直接插入）"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

upload_start=$(date +%s)
upload_response=$(curl -s -X POST 'http://localhost:8000/insert?doc_id=e2e_test_001' \
  -F "file=@/tmp/test_e2e_doc.txt")
upload_end=$(date +%s)
upload_time=$((upload_end - upload_start))

echo "  响应: $upload_response"

task_id=$(echo "$upload_response" | jq -r '.task_id')
if [ "$task_id" != "null" ] && [ -n "$task_id" ]; then
    echo -e "${GREEN}✓ 文档上传成功${NC}"
    echo "  Task ID: $task_id"
    echo "  上传耗时: ${upload_time}s"
else
    echo -e "${RED}✗ 文档上传失败${NC}"
    exit 1
fi

# 测试 3: 轮询任务状态
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ 测试 3: 等待任务完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

max_wait=120  # 最多等待 120 秒
wait_count=0
task_start=$(date +%s)

while [ $wait_count -lt $max_wait ]; do
    task_response=$(curl -s "http://localhost:8000/task/$task_id")
    status=$(echo "$task_response" | jq -r '.status')
    
    echo -ne "\r  状态: $status | 已等待: ${wait_count}s"
    
    if [ "$status" == "completed" ]; then
        task_end=$(date +%s)
        task_time=$((task_end - task_start))
        echo ""
        echo -e "${GREEN}✓ 任务完成${NC}"
        echo "  处理耗时: ${task_time}s"
        echo "  结果: $(echo "$task_response" | jq -r '.result.message')"
        break
    elif [ "$status" == "failed" ]; then
        echo ""
        echo -e "${RED}✗ 任务失败${NC}"
        echo "  错误: $(echo "$task_response" | jq -r '.error')"
        exit 1
    fi
    
    sleep 2
    wait_count=$((wait_count + 2))
done

if [ $wait_count -ge $max_wait ]; then
    echo ""
    echo -e "${RED}✗ 任务超时${NC}"
    exit 1
fi

# 测试 4: 查询功能
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 测试 4: 查询功能"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

query_start=$(date +%s)
query_response=$(curl -s -X POST 'http://localhost:8000/query' \
  -H 'Content-Type: application/json' \
  -d '{"query": "RAG API 有哪些核心功能？", "mode": "naive"}')
query_end=$(date +%s)
query_time=$((query_end - query_start))

answer=$(echo "$query_response" | jq -r '.answer')
if [ "$answer" != "null" ] && [ -n "$answer" ]; then
    echo -e "${GREEN}✓ 查询成功${NC}"
    echo "  查询耗时: ${query_time}s"
    echo "  答案（前 200 字符）:"
    echo "  $(echo "$answer" | head -c 200)..."
else
    echo -e "${RED}✗ 查询失败${NC}"
    echo "  响应: $query_response"
    exit 1
fi

# 总结
echo ""
echo "========================================================================"
echo "✅ 端到端测试完成！"
echo "========================================================================"
echo ""
echo "📊 性能总结:"
echo "  - 上传耗时: ${upload_time}s"
echo "  - 任务处理: ${task_time}s"
echo "  - 查询耗时: ${query_time}s"
total_time=$((upload_time + task_time + query_time))
echo "  - 总耗时: ${total_time}s"
echo ""
echo "✅ 测试项目:"
echo "  ✓ 健康检查"
echo "  ✓ 文档上传（异步任务）"
echo "  ✓ 任务状态轮询"
echo "  ✓ 知识图谱构建"
echo "  ✓ 智能查询"
echo ""
echo "========================================================================"
