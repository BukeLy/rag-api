#!/bin/bash
# 服务器本地执行的性能测试脚本

echo "🚀 RAG API 性能测试（本地执行）"
echo "=================================="

# 1. 创建测试文件
echo "📝 创建测试文件..."
echo '人工智能（AI）是计算机科学的一个分支，致力于创建能够执行通常需要人类智能的任务的系统。机器学习是 AI 的一个子领域，专注于开发能够从数据中学习的算法。深度学习使用多层神经网络来处理复杂的数据模式。' > /tmp/test_perf.txt

# 2. 获取初始资源状态
echo ""
echo "📊 上传前资源状态："
docker stats rag-api --no-stream --format 'CPU: {{.CPUPerc}}  |  内存: {{.MemUsage}} ({{.MemPerc}})'

# 3. 上传文件并记录时间
echo ""
echo "⏱️  上传文件并计时..."
START_TIME=$(date +%s)

RESPONSE=$(curl -s -w '\nHTTP_CODE:%{http_code}\nTIME_TOTAL:%{time_total}' \
    -X POST "http://localhost:8000/insert?doc_id=perf_test_$(date +%s)" \
    -F 'file=@/tmp/test_perf.txt')

END_TIME=$(date +%s)
UPLOAD_TIME=$((END_TIME - START_TIME))

echo "$RESPONSE" | grep -v "HTTP_CODE\|TIME_TOTAL"
HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d: -f2)
API_TIME=$(echo "$RESPONSE" | grep "TIME_TOTAL" | cut -d: -f2)

echo ""
echo "✅ 上传响应时间: ${API_TIME}s"
echo "   HTTP 状态码: $HTTP_CODE"

# 提取 task_id
TASK_ID=$(echo "$RESPONSE" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4)
echo "   Task ID: $TASK_ID"

# 4. 监控处理过程
if [ ! -z "$TASK_ID" ]; then
    echo ""
    echo "🔄 监控任务处理进度（每2秒刷新）..."
    
    for i in {1..60}; do
        # 查询任务状态
        STATUS_RESPONSE=$(curl -s "http://localhost:8000/task/$TASK_ID")
        STATUS=$(echo "$STATUS_RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        
        # 获取当前资源使用
        STATS=$(docker stats rag-api --no-stream --format 'CPU: {{.CPUPerc}}  内存: {{.MemUsage}}')
        
        echo "[$i/60] 状态: $STATUS | $STATS"
        
        # 如果完成或失败，退出循环
        if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ]; then
            echo ""
            if [ "$STATUS" = "completed" ]; then
                echo "✅ 任务完成！"
                echo ""
                echo "完整结果："
                echo "$STATUS_RESPONSE" | python3 -m json.tool
            else
                ERROR=$(echo "$STATUS_RESPONSE" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
                echo "❌ 任务失败: $ERROR"
            fi
            break
        fi
        
        sleep 2
    done
fi

# 5. 最终资源状态
echo ""
echo "📊 处理后资源状态："
docker stats rag-api --no-stream --format 'CPU: {{.CPUPerc}}  |  内存: {{.MemUsage}} ({{.MemPerc}})'

echo ""
echo "=================================="
echo "测试完成！"

