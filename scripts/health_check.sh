#!/bin/bash

# ============================================================
# RAG API 健康检查脚本
# ============================================================
# 用途：检查所有服务的健康状态
#
# 使用方法：
#   ./scripts/health_check.sh
#   ./scripts/health_check.sh --verbose
#
# 配置：从 .env 文件读取
#   - API_URL: API 服务地址（默认 http://localhost:8000）
#   - REDIS_HOST: DragonflyDB/Redis 主机地址
#   - QDRANT_URL: Qdrant 连接 URL
#   - MEMGRAPH_URI: Memgraph 连接 URI
# ============================================================

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 加载环境变量
if [ -f .env ]; then
    source .env
fi

# 默认配置
API_URL=${API_URL:-"http://localhost:8000"}
REDIS_HOST=${REDIS_HOST:-"localhost"}
REDIS_PORT=${REDIS_PORT:-6379}
QDRANT_URL=${QDRANT_URL:-"http://localhost:6333"}
MEMGRAPH_URI=${MEMGRAPH_URI:-"bolt://localhost:7687"}
MEMGRAPH_USERNAME=${MEMGRAPH_USERNAME:-""}
MEMGRAPH_PASSWORD=${MEMGRAPH_PASSWORD:-""}
USE_EXTERNAL_STORAGE=${USE_EXTERNAL_STORAGE:-"false"}
KV_STORAGE=${KV_STORAGE:-"JsonKVStorage"}
VECTOR_STORAGE=${VECTOR_STORAGE:-"NanoVectorDB"}
GRAPH_STORAGE=${GRAPH_STORAGE:-"NetworkXStorage"}

VERBOSE=false
if [ "$1" == "--verbose" ]; then
    VERBOSE=true
fi

# 辅助函数
print_header() {
    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠  $1${NC}"
}

# 健康检查函数
check_api() {
    echo -n "🚀 API Service ($API_URL): "

    if response=$(curl -sf "$API_URL/" 2>&1); then
        print_success "OK"
        if [ "$VERBOSE" = true ]; then
            echo "   Response: $response"
        fi
        return 0
    else
        print_error "FAIL"
        if [ "$VERBOSE" = true ]; then
            echo "   Error: $response"
        fi
        return 1
    fi
}

check_redis() {
    echo -n "🐉 DragonflyDB/Redis ($REDIS_HOST:$REDIS_PORT): "

    if command -v redis-cli > /dev/null 2>&1; then
        if result=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping 2>&1); then
            if [ "$result" == "PONG" ]; then
                print_success "OK"

                if [ "$VERBOSE" = true ]; then
                    db_size=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" DBSIZE)
                    memory=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
                    echo "   DB Size: $db_size keys"
                    echo "   Memory: $memory"
                fi
                return 0
            fi
        fi
    else
        # Fallback: 使用 Docker Compose
        if docker compose exec -T redis redis-cli ping > /dev/null 2>&1; then
            print_success "OK (via Docker)"
            return 0
        fi
    fi

    print_error "FAIL"
    return 1
}

check_qdrant() {
    echo -n "🎯 Qdrant ($QDRANT_URL): "

    if response=$(curl -sf "$QDRANT_URL/healthz" 2>&1); then
        print_success "OK"

        if [ "$VERBOSE" = true ]; then
            collections=$(curl -sf "$QDRANT_URL/collections" 2>/dev/null | grep -o '"result":\[.*\]' | grep -o '\[.*\]' | tr -d '[]' || echo "0")
            echo "   Collections: $collections"
        fi
        return 0
    else
        # Fallback: 使用 Docker Compose
        if docker compose exec -T qdrant curl -sf http://localhost:6333/healthz > /dev/null 2>&1; then
            print_success "OK (via Docker)"
            return 0
        fi
    fi

    print_error "FAIL"
    return 1
}

check_memgraph() {
    echo -n "🧠 Memgraph ($MEMGRAPH_URI): "

    # 解析主机地址
    MEMGRAPH_HOST=$(echo "$MEMGRAPH_URI" | sed 's|bolt://||' | cut -d: -f1)
    MEMGRAPH_PORT=$(echo "$MEMGRAPH_URI" | sed 's|bolt://||' | cut -d: -f2)

    # 尝试使用 mgconsole 或 cypher-shell
    if command -v mgconsole > /dev/null 2>&1; then
        if echo "RETURN 1;" | mgconsole --host "$MEMGRAPH_HOST" --port "$MEMGRAPH_PORT" > /dev/null 2>&1; then
            print_success "OK"

            if [ "$VERBOSE" = true ]; then
                node_count=$(echo "MATCH (n) RETURN count(n) AS count;" | mgconsole --host "$MEMGRAPH_HOST" --port "$MEMGRAPH_PORT" --output-format=csv 2>/dev/null | tail -n 1)
                edge_count=$(echo "MATCH ()-[r]->() RETURN count(r) AS count;" | mgconsole --host "$MEMGRAPH_HOST" --port "$MEMGRAPH_PORT" --output-format=csv 2>/dev/null | tail -n 1)
                echo "   Nodes: $node_count"
                echo "   Edges: $edge_count"
            fi
            return 0
        fi
    else
        # Fallback: 使用 Docker Compose
        if docker compose exec -T memgraph bash -c "echo 'RETURN 1;' | mgconsole --host 127.0.0.1 --port 7687" > /dev/null 2>&1; then
            print_success "OK (via Docker)"
            return 0
        fi
    fi

    print_error "FAIL"
    return 1
}

check_query_endpoint() {
    echo -n "🔍 Query Endpoint: "

    response=$(curl -sf -X POST "$API_URL/query" \
        -H "Content-Type: application/json" \
        -d '{"query": "health check test", "mode": "naive"}' 2>&1)

    if [ $? -eq 0 ] && [ -n "$response" ]; then
        print_success "OK"

        if [ "$VERBOSE" = true ]; then
            echo "   Response length: ${#response} chars"
        fi
        return 0
    else
        print_error "FAIL"
        if [ "$VERBOSE" = true ]; then
            echo "   Error: $response"
        fi
        return 1
    fi
}

# 主函数
main() {
    print_header "🏥 RAG API Health Check"

    echo "Configuration:"
    echo "  - API URL: $API_URL"
    echo "  - External Storage: $USE_EXTERNAL_STORAGE"
    if [ "$USE_EXTERNAL_STORAGE" = "true" ]; then
        echo "  - KV Storage: $KV_STORAGE ($REDIS_HOST:$REDIS_PORT)"
        echo "  - Vector Storage: $VECTOR_STORAGE ($QDRANT_URL)"
        echo "  - Graph Storage: $GRAPH_STORAGE ($MEMGRAPH_URI)"
    fi

    echo ""
    echo "Checking services..."
    echo ""

    # 记录失败的服务
    failed_services=()

    # 检查核心服务
    check_api || failed_services+=("API")

    # 如果启用了外部存储，检查数据库
    if [ "$USE_EXTERNAL_STORAGE" = "true" ]; then
        check_redis || failed_services+=("DragonflyDB")
        check_qdrant || failed_services+=("Qdrant")
        check_memgraph || failed_services+=("Memgraph")
    else
        print_warning "External storage disabled, skipping database checks"
    fi

    echo ""
    print_header "🧪 Functional Tests"

    check_query_endpoint || failed_services+=("Query")

    # 总结
    echo ""
    print_header "📊 Summary"

    if [ ${#failed_services[@]} -eq 0 ]; then
        print_success "All services are healthy! ✨"
        exit 0
    else
        print_error "Failed services: ${failed_services[*]}"
        print_warning "Please check the logs for more details"
        exit 1
    fi
}

# 执行主函数
main
