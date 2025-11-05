#!/bin/bash

###############################################################################
# RAG API 一键部署脚本
# 用途: 在全新的 Linux 服务器上一键部署 RAG API
# 支持: Ubuntu 20.04+, Debian 11+, CentOS 8+
###############################################################################

set -e  # 遇到错误立即退出

# 全局变量
COMPOSE_FILE="docker-compose.yml"  # 默认使用生产模式
DEPLOY_MODE="production"           # 部署模式: production 或 development

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检测操作系统
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$ID
        VERSION=$VERSION_ID
    else
        log_error "无法检测操作系统类型"
        exit 1
    fi
    log_info "检测到操作系统: $OS $VERSION"
}

# 检查是否为 root 用户
check_root() {
    if [ "$EUID" -eq 0 ]; then
        log_warning "检测到 root 用户，建议使用普通用户 + sudo 执行"
        read -p "是否继续? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# 选择部署模式
select_deploy_mode() {
    echo ""
    log_info "请选择部署模式:"
    echo "  1) 生产模式 (Production) - 标准容器部署，适合生产环境"
    echo "  2) 开发模式 (Development) - 外挂代码库，支持热重载，适合开发调试"
    echo ""
    read -p "请输入选择 (1/2, 默认: 1): " -n 1 -r
    echo ""
    
    case $REPLY in
        2)
            COMPOSE_FILE="docker-compose.dev.yml"
            DEPLOY_MODE="development"
            log_success "已选择: 开发模式 (使用 docker-compose.dev.yml)"
            log_warning "开发模式会将本地代码挂载到容器中，修改代码会自动重载"
            ;;
        1|"")
            COMPOSE_FILE="docker-compose.yml"
            DEPLOY_MODE="production"
            log_success "已选择: 生产模式 (使用 docker-compose.yml)"
            ;;
        *)
            log_error "无效的选择，使用默认的生产模式"
            COMPOSE_FILE="docker-compose.yml"
            DEPLOY_MODE="production"
            ;;
    esac
    
    echo ""
}

# 安装 Docker
install_docker() {
    log_info "检查 Docker 安装状态..."
    
    if command -v docker &> /dev/null; then
        log_success "Docker 已安装: $(docker --version)"
        return 0
    fi
    
    log_info "开始安装 Docker..."
    
    case $OS in
        ubuntu|debian)
            sudo apt-get update
            sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
            
            # 添加 Docker 官方 GPG 密钥
            curl -fsSL https://download.docker.com/linux/$OS/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
            
            # 添加 Docker 仓库
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/$OS $(lsb_release -cs) stable" | \
                sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            # 安装 Docker
            sudo apt-get update
            sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
            
        centos|rhel|fedora)
            sudo yum install -y yum-utils
            sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
            sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            sudo systemctl start docker
            sudo systemctl enable docker
            ;;
            
        *)
            log_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac
    
    # 将当前用户添加到 docker 组
    if [ "$EUID" -ne 0 ]; then
        sudo usermod -aG docker "$USER"
        log_warning "已将用户 $USER 添加到 docker 组，请重新登录后生效"
    fi
    
    log_success "Docker 安装完成"
}

# 安装 Docker Compose
install_docker_compose() {
    log_info "检查 Docker Compose 安装状态..."
    
    if docker compose version &> /dev/null; then
        log_success "Docker Compose 已安装: $(docker compose version)"
        return 0
    fi
    
    log_info "Docker Compose 已作为 Docker 插件安装"
}

# 配置环境变量
setup_env() {
    log_info "配置环境变量..."
    
    if [ ! -f .env ]; then
        cp .env.example .env
        log_warning "已创建 .env 文件，请编辑并填入真实的 API 密钥！"
        echo ""
        echo "请执行以下命令编辑配置文件:"
        echo "  nano .env"
        echo ""
        read -p "现在编辑配置文件? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            ${EDITOR:-nano} .env
        else
            log_error "必须配置 .env 文件才能继续！"
            exit 1
        fi
    else
        log_success ".env 文件已存在"
    fi
    
    # 验证必需的环境变量
    source .env
    if [ -z "$LLM_API_KEY" ] || [ "$LLM_API_KEY" = "your_llm_api_key_here" ]; then
        log_error "LLM_API_KEY 未配置！请编辑 .env 文件"
        exit 1
    fi

    if [ -z "$EMBEDDING_API_KEY" ] || [ "$EMBEDDING_API_KEY" = "your_embedding_api_key_here" ]; then
        log_error "EMBEDDING_API_KEY 未配置！请编辑 .env 文件"
        exit 1
    fi
    
    log_success "环境变量配置完成"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    mkdir -p rag_local_storage
    mkdir -p output
    mkdir -p logs
    mkdir -p deploy
    
    log_success "目录创建完成"
}

# 优化系统参数
optimize_system() {
    log_info "优化系统参数..."
    
    # 增加文件描述符限制
    if ! grep -q "rag-api file limits" /etc/security/limits.conf 2>/dev/null; then
        echo "# rag-api file limits" | sudo tee -a /etc/security/limits.conf
        echo "* soft nofile 65535" | sudo tee -a /etc/security/limits.conf
        echo "* hard nofile 65535" | sudo tee -a /etc/security/limits.conf
        log_success "已增加文件描述符限制"
    fi
    
    # 优化内核参数
    if [ -f /etc/sysctl.conf ]; then
        if ! grep -q "rag-api kernel params" /etc/sysctl.conf; then
            echo "" | sudo tee -a /etc/sysctl.conf
            echo "# rag-api kernel params" | sudo tee -a /etc/sysctl.conf
            echo "net.core.somaxconn = 1024" | sudo tee -a /etc/sysctl.conf
            echo "net.ipv4.tcp_max_syn_backlog = 2048" | sudo tee -a /etc/sysctl.conf
            sudo sysctl -p
            log_success "已优化内核参数"
        fi
    fi
    
    log_success "系统优化完成"
}

# 构建并启动服务
start_services() {
    log_info "清理旧 Docker 资源..."
    docker system prune -f || true
    docker builder prune -f || true
    
    log_info "使用配置文件: $COMPOSE_FILE"
    log_info "构建 Docker 镜像..."
    docker compose -f $COMPOSE_FILE build
    
    log_info "启动服务..."
    docker compose -f $COMPOSE_FILE up -d
    
    log_success "服务已启动 (模式: $DEPLOY_MODE)"
    
    # 显示磁盘使用情况
    log_info "当前磁盘使用: $(df -h / | tail -1 | awk '{print $3 "/" $2 " (" $5 ")"}')"
}

# 等待服务就绪
wait_for_service() {
    log_info "等待服务启动（最多等待 120 秒）..."

    for _ in {1..40}; do
        if curl -f http://localhost:8000/ &> /dev/null; then
            log_success "服务已就绪！"
            return 0
        fi
        echo -n "."
        sleep 3
    done
    
    echo ""
    log_error "服务启动超时，请检查日志: docker compose logs"
    return 1
}

# 显示服务状态
show_status() {
    log_info "服务状态:"
    docker compose -f $COMPOSE_FILE ps
    
    echo ""
    log_info "服务健康检查:"
    curl -s http://localhost:8000/ | jq . || echo "API 响应: $(curl -s http://localhost:8000/)"
}

# 显示部署信息
show_info() {
    echo ""
    echo "======================================================================"
    log_success "🎉 RAG API 部署完成！"
    echo "======================================================================"
    echo ""
    echo "🚀 部署模式: $DEPLOY_MODE"
    echo "📄 配置文件: $COMPOSE_FILE"
    echo ""
    echo "📍 服务地址:"
    echo "   本地访问: http://localhost:8000"
    echo "   API 文档: http://localhost:8000/docs"
    echo ""
    echo "📋 常用命令:"
    echo "   监控服务:   ./scripts/monitor.sh"
    echo "   备份数据:   ./scripts/backup.sh"
    echo "   更新部署:   ./scripts/update.sh"
    echo "   查看日志:   docker compose -f $COMPOSE_FILE logs -f"
    echo "   重启服务:   docker compose -f $COMPOSE_FILE restart"
    echo "   停止服务:   docker compose -f $COMPOSE_FILE down"
    echo ""
    
    if [ "$DEPLOY_MODE" = "development" ]; then
        echo "💡 开发模式提示:"
        echo "   - 代码已挂载到容器，修改代码会自动重载"
        echo "   - 适合本地开发和调试"
        echo "   - 不建议用于生产环境"
        echo ""
    fi
    
    echo "📁 重要目录:"
    echo "   向量数据库: ./rag_local_storage"
    echo "   输出文件:   ./output"
    echo "   日志文件:   ./logs"
    echo ""
    echo "🔧 测试命令:"
    echo "   # 上传文件"
    echo "   curl -X POST 'http://localhost:8000/insert?doc_id=test' \\"
    echo "        -F 'file=@your_file.pdf'"
    echo ""
    echo "   # 查询"
    echo "   curl -X POST 'http://localhost:8000/query' \\"
    echo "        -H 'Content-Type: application/json' \\"
    echo "        -d '{\"query\": \"你的问题\", \"mode\": \"mix\"}'"
    echo ""
    echo "======================================================================"
}

# 主函数
main() {
    echo ""
    echo "======================================================================"
    echo "              RAG API 一键部署脚本 v1.1"
    echo "======================================================================"
    echo ""
    
    # 检查环境
    detect_os
    check_root
    
    # 选择部署模式
    select_deploy_mode
    
    # 安装依赖
    install_docker
    install_docker_compose
    
    # 配置项目
    setup_env
    create_directories
    optimize_system
    
    # 启动服务
    start_services
    
    # 等待服务就绪
    if wait_for_service; then
        show_status
        show_info
    else
        log_error "部署失败，请检查错误信息"
        echo ""
        echo "查看详细日志:"
        echo "  docker compose -f $COMPOSE_FILE logs"
        exit 1
    fi
}

# 执行主函数
main

