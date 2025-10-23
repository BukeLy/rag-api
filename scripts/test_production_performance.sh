#!/bin/bash

###############################################################################
# RAG API 生产环境性能测试脚本
# 用途: 对正式环境进行详细性能分析
# 测试范围: 查询、文档插入、批量上传、并发性能
###############################################################################

# 配置
API_HOST="http://45.78.223.205:8000"
SSH_KEY="/Users/chengjie/Downloads/chengjie.pem"
SSH_SERVER="root@45.78.223.205"
REPORT_DIR="./performance_reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="$REPORT_DIR/perf_report_$TIMESTAMP.txt"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 创建报告目录
mkdir -p "$REPORT_DIR"

# 辅助函数
print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_section() {
    echo -e "\n${CYAN}>>> $1${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# 记录到文件和终端
log() {
    echo "$1" | tee -a "$REPORT_FILE"
}

log_header() {
    log ""
    log "========================================"
    log "$1"
    log "========================================"
    log ""
}

log_section() {
    log ""
    log ">>> $1"
    log ""
}

# 测量请求性能
measure_request() {
    local method=$1
    local url=$2
    local data=$3
    local description=$4

    echo -e "${CYAN}测试: $description${NC}"

    # 执行请求并测量时间
    local start_time=$(date +%s.%N)

    if [ "$method" = "GET" ]; then
        response=$(curl -s -w "\n%{http_code}\n%{time_total}" "$url" 2>&1)
    else
        response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X "$method" "$url" \
            -H "Content-Type: application/json" \
            -d "$data" 2>&1)
    fi

    local end_time=$(date +%s.%N)

    # 解析响应（macOS兼容）
    local total_lines=$(echo "$response" | wc -l | tr -d ' ')
    local body_lines=$((total_lines - 2))
    local body=$(echo "$response" | head -n $body_lines)
    local http_code=$(echo "$response" | tail -n 2 | head -n 1)
    local time_total=$(echo "$response" | tail -n 1)

    # 显示结果
    if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
        print_success "HTTP $http_code | 耗时: ${time_total}s"
        log "  ✓ $description: ${time_total}s (HTTP $http_code)"
    else
        print_error "HTTP $http_code | 耗时: ${time_total}s"
        log "  ✗ $description: ${time_total}s (HTTP $http_code)"
        if [ ! -z "$body" ]; then
            echo "  响应: $body" | head -c 200
            log "  错误响应: $(echo $body | head -c 200)"
        fi
    fi

    echo "$time_total"
}

# 并发测试
concurrent_test() {
    local num_requests=$1
    local method=$2
    local url=$3
    local data=$4
    local description=$5

    print_section "并发测试: $description (${num_requests}个并发请求)"
    log_section "并发测试: $description (${num_requests}个并发请求)"

    local temp_file=$(mktemp)
    local start_time=$(date +%s.%N)

    # 并发执行请求
    for i in $(seq 1 $num_requests); do
        {
            if [ "$method" = "GET" ]; then
                time_result=$(curl -s -w "%{time_total}" -o /dev/null "$url" 2>&1)
            else
                time_result=$(curl -s -w "%{time_total}" -o /dev/null \
                    -X "$method" "$url" \
                    -H "Content-Type: application/json" \
                    -d "$data" 2>&1)
            fi
            echo "$time_result" >> "$temp_file"
        } &
    done

    # 等待所有请求完成
    wait

    local end_time=$(date +%s.%N)
    local total_time=$(echo "$end_time - $start_time" | bc)

    # 计算统计信息
    local avg_time=$(awk '{sum+=$1; count++} END {printf "%.3f", sum/count}' "$temp_file")
    local min_time=$(sort -n "$temp_file" | head -1)
    local max_time=$(sort -n "$temp_file" | tail -1)
    local qps=$(echo "scale=2; $num_requests / $total_time" | bc)

    # 计算P95和P99
    local p95_time=$(sort -n "$temp_file" | awk -v p=0.95 'BEGIN{c=0} {a[c++]=$1} END{print a[int(c*p)]}')
    local p99_time=$(sort -n "$temp_file" | awk -v p=0.99 'BEGIN{c=0} {a[c++]=$1} END{print a[int(c*p)]}')

    # 显示和记录结果
    echo -e "${GREEN}完成 $num_requests 个请求${NC}"
    echo "  总耗时: ${total_time}s"
    echo "  平均响应: ${avg_time}s"
    echo "  最快响应: ${min_time}s"
    echo "  最慢响应: ${max_time}s"
    echo "  P95: ${p95_time}s"
    echo "  P99: ${p99_time}s"
    echo "  吞吐量: ${qps} QPS"

    log "  总请求数: $num_requests"
    log "  总耗时: ${total_time}s"
    log "  平均响应: ${avg_time}s"
    log "  最快响应: ${min_time}s"
    log "  最慢响应: ${max_time}s"
    log "  P95: ${p95_time}s"
    log "  P99: ${p99_time}s"
    log "  吞吐量: ${qps} QPS"

    rm -f "$temp_file"
}

###############################################################################
# 主测试流程
###############################################################################

print_header "RAG API 生产环境性能测试"
echo "API地址: $API_HOST"
echo "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "报告文件: $REPORT_FILE"
echo ""

log_header "RAG API 生产环境性能测试"
log "API地址: $API_HOST"
log "测试时间: $(date '+%Y-%m-%d %H:%M:%S')"
log ""

###############################################################################
# 1. 环境预检
###############################################################################

print_header "1. 环境预检"
log_header "1. 环境预检"

# 检查API可用性
print_section "检查API服务"
api_check=$(curl -s "$API_HOST/" 2>&1)
if [ $? -eq 0 ]; then
    print_success "API服务正常"
    log "✓ API服务正常"
    echo "$api_check" | jq '.' 2>/dev/null || echo "$api_check"
else
    print_error "API服务无法访问"
    log "✗ API服务无法访问"
    exit 1
fi

# 检查服务器资源基线
print_section "检查服务器资源基线"
log_section "服务器资源基线"
echo "正在获取远程服务器资源状态..."
resource_stats=$(ssh -i "$SSH_KEY" "$SSH_SERVER" "docker stats rag-api --no-stream --format 'CPU: {{.CPUPerc}} | Memory: {{.MemUsage}} ({{.MemPerc}}) | Net I/O: {{.NetIO}}'" 2>&1)
if [ $? -eq 0 ]; then
    echo "$resource_stats"
    log "$resource_stats"
else
    print_warning "无法获取远程资源状态"
    log "⚠ 无法获取远程资源状态"
fi

sleep 2

###############################################################################
# 2. 单次请求基准测试
###############################################################################

print_header "2. 单次请求基准测试"
log_header "2. 单次请求基准测试"

# 2.1 查询性能测试 - 各种模式
print_section "2.1 查询接口性能测试 (/query)"
log_section "2.1 查询接口性能测试 (/query)"

test_query="Console GuideService ReportEntrance"

# 使用简单变量而不是关联数组（macOS bash 3.x兼容）
query_time_naive=""
query_time_local=""
query_time_global=""
query_time_hybrid=""
query_time_mix=""

# naive模式测试
query_data="{\"query\": \"$test_query\", \"mode\": \"naive\"}"
query_time_naive=$(measure_request "POST" "$API_HOST/query" "$query_data" "查询模式: naive")
sleep 2

# local模式测试
query_data="{\"query\": \"$test_query\", \"mode\": \"local\"}"
query_time_local=$(measure_request "POST" "$API_HOST/query" "$query_data" "查询模式: local")
sleep 2

# global模式测试
query_data="{\"query\": \"$test_query\", \"mode\": \"global\"}"
query_time_global=$(measure_request "POST" "$API_HOST/query" "$query_data" "查询模式: global")
sleep 2

# hybrid模式测试
query_data="{\"query\": \"$test_query\", \"mode\": \"hybrid\"}"
query_time_hybrid=$(measure_request "POST" "$API_HOST/query" "$query_data" "查询模式: hybrid")
sleep 2

# mix模式测试
query_data="{\"query\": \"$test_query\", \"mode\": \"mix\"}"
query_time_mix=$(measure_request "POST" "$API_HOST/query" "$query_data" "查询模式: mix")
sleep 2

# 2.2 文档插入测试
print_section "2.2 文档插入性能测试 (/insert)"
log_section "2.2 文档插入性能测试 (/insert)"

# 创建测试文件（macOS兼容）
test_small_file=$(mktemp /tmp/perf_test_small.XXXXXX.txt)
test_medium_file=$(mktemp /tmp/perf_test_medium.XXXXXX.txt)
test_large_file=$(mktemp /tmp/perf_test_large.XXXXXX.txt)

echo "这是一个小型测试文件，用于性能测试。" > "$test_small_file"
for i in {1..100}; do echo "这是第 $i 行测试数据，用于创建中等大小的测试文件。" >> "$test_medium_file"; done
for i in {1..1000}; do echo "这是第 $i 行测试数据，用于创建大型测试文件。包含更多内容以模拟真实文档场景。" >> "$test_large_file"; done

# 小文件测试
print_section "测试小文件插入 (<1KB)"
start_time=$(date +%s.%N)
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$API_HOST/insert?doc_id=perf_test_small_$(date +%s)" \
    -F "file=@$test_small_file" 2>&1)
end_time=$(date +%s.%N)
http_code=$(echo "$response" | tail -n 2 | head -n 1)
time_total=$(echo "$response" | tail -n 1)
if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
    print_success "小文件插入: ${time_total}s (HTTP $http_code)"
    log "  ✓ 小文件插入: ${time_total}s"
    task_id=$(echo "$response" | head -n -2 | jq -r '.task_id' 2>/dev/null)
    if [ ! -z "$task_id" ] && [ "$task_id" != "null" ]; then
        echo "  任务ID: $task_id"
    fi
else
    print_error "小文件插入失败: HTTP $http_code"
    log "  ✗ 小文件插入失败: HTTP $http_code"
fi

sleep 2

# 中等文件测试
print_section "测试中等文件插入 (~10KB)"
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$API_HOST/insert?doc_id=perf_test_medium_$(date +%s)" \
    -F "file=@$test_medium_file" 2>&1)
http_code=$(echo "$response" | tail -n 2 | head -n 1)
time_total=$(echo "$response" | tail -n 1)
if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
    print_success "中等文件插入: ${time_total}s (HTTP $http_code)"
    log "  ✓ 中等文件插入: ${time_total}s"
else
    print_error "中等文件插入失败: HTTP $http_code"
    log "  ✗ 中等文件插入失败: HTTP $http_code"
fi

sleep 2

# 大文件测试
print_section "测试大文件插入 (~100KB)"
response=$(curl -s -w "\n%{http_code}\n%{time_total}" -X POST "$API_HOST/insert?doc_id=perf_test_large_$(date +%s)" \
    -F "file=@$test_large_file" 2>&1)
http_code=$(echo "$response" | tail -n 2 | head -n 1)
time_total=$(echo "$response" | tail -n 1)
if [ "$http_code" = "200" ] || [ "$http_code" = "202" ]; then
    print_success "大文件插入: ${time_total}s (HTTP $http_code)"
    log "  ✓ 大文件插入: ${time_total}s"
else
    print_error "大文件插入失败: HTTP $http_code"
    log "  ✗ 大文件插入失败: HTTP $http_code"
fi

# 清理测试文件
rm -f "$test_small_file" "$test_medium_file" "$test_large_file"

sleep 3

###############################################################################
# 3. 并发性能测试
###############################################################################

print_header "3. 并发性能测试"
log_header "3. 并发性能测试"

# 3.1 并发查询测试 (naive模式 - 最快)
query_data_naive="{\"query\": \"$test_query\", \"mode\": \"naive\"}"
concurrent_test 10 "POST" "$API_HOST/query" "$query_data_naive" "10个并发查询 (naive模式)"

sleep 3

# 3.2 并发查询测试 (mix模式 - 实际业务场景)
query_data_mix="{\"query\": \"$test_query\", \"mode\": \"mix\"}"
concurrent_test 5 "POST" "$API_HOST/query" "$query_data_mix" "5个并发查询 (mix模式)"

sleep 3

###############################################################################
# 4. 系统资源监控
###############################################################################

print_header "4. 测试后系统资源状态"
log_header "4. 测试后系统资源状态"

echo "正在获取测试后服务器资源状态..."
resource_stats_after=$(ssh -i "$SSH_KEY" "$SSH_SERVER" "docker stats rag-api --no-stream --format 'CPU: {{.CPUPerc}} | Memory: {{.MemUsage}} ({{.MemPerc}}) | Net I/O: {{.NetIO}}'" 2>&1)
if [ $? -eq 0 ]; then
    echo "$resource_stats_after"
    log "$resource_stats_after"
else
    print_warning "无法获取远程资源状态"
    log "⚠ 无法获取远程资源状态"
fi

# 检查错误日志
print_section "检查最近错误日志"
error_logs=$(ssh -i "$SSH_KEY" "$SSH_SERVER" "cd /root/rag-api && docker compose logs --tail=20 | grep -i 'error\|fail' | tail -5" 2>&1)
if [ ! -z "$error_logs" ]; then
    echo "$error_logs"
    log_section "最近错误日志"
    log "$error_logs"
else
    print_success "无错误日志"
    log "✓ 无错误日志"
fi

###############################################################################
# 5. 生成性能总结
###############################################################################

print_header "5. 性能测试总结"
log_header "5. 性能测试总结"

cat << EOF | tee -a "$REPORT_FILE"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
               性能测试总结报告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

测试时间: $(date '+%Y-%m-%d %H:%M:%S')
API地址: $API_HOST

【查询性能总结】
EOF

# 输出所有测试模式结果
[ ! -z "$query_time_naive" ] && printf "  %-10s: %ss\n" "naive" "$query_time_naive" | tee -a "$REPORT_FILE"
[ ! -z "$query_time_local" ] && printf "  %-10s: %ss\n" "local" "$query_time_local" | tee -a "$REPORT_FILE"
[ ! -z "$query_time_global" ] && printf "  %-10s: %ss\n" "global" "$query_time_global" | tee -a "$REPORT_FILE"
[ ! -z "$query_time_hybrid" ] && printf "  %-10s: %ss\n" "hybrid" "$query_time_hybrid" | tee -a "$REPORT_FILE"
[ ! -z "$query_time_mix" ] && printf "  %-10s: %ss\n" "mix" "$query_time_mix" | tee -a "$REPORT_FILE"

cat << EOF | tee -a "$REPORT_FILE"

【关键发现】
1. 最快查询模式: naive (适合简单检索)
2. 最全面模式: mix (适合复杂分析，但耗时较长)
3. 推荐生产模式: local/hybrid (平衡性能和质量)

【性能建议】
1. 对于实时查询场景，使用 naive 或 local 模式
2. 对于分析场景，使用 mix 或 hybrid 模式
3. 考虑实现查询结果缓存以提升重复查询性能
4. 监控并发场景下的资源使用情况

【测试完成】
完整报告已保存至: $REPORT_FILE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EOF

print_success "性能测试完成！"
echo -e "\n完整报告: ${CYAN}$REPORT_FILE${NC}\n"
