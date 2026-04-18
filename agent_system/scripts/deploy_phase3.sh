#!/bin/bash
# Phase 3 部署脚本 - 职能分工与记忆增强体系

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/ai-god-of-stocks"
PID_DIR="/var/run/ai-god-of-stocks"

mkdir -p "$LOG_DIR" "$PID_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 启动 Dual Agent API Server
start_api_server() {
    log_info "Starting Dual Agent API Server..."
    
    local pid_file="$PID_DIR/dual-agent-api.pid"
    
    if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
        log_warn "API Server already running (PID: $(cat "$pid_file"))"
        return 0
    fi
    
    cd "$PROJECT_DIR"
    nohup python3 agent_system/dual_agent_api.py --port 18087 > "$LOG_DIR/dual-agent-api.log" 2>&1 &
    echo $! > "$pid_file"
    
    sleep 2
    if kill -0 $(cat "$pid_file") 2>/dev/null; then
        log_info "API Server started (PID: $(cat "$pid_file"), Port: 18087)"
    else
        log_error "Failed to start API Server"
        return 1
    fi
}

# 停止 API Server
stop_api_server() {
    log_info "Stopping Dual Agent API Server..."
    
    local pid_file="$PID_DIR/dual-agent-api.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            sleep 1
        fi
        rm -f "$pid_file"
        log_info "API Server stopped"
    fi
}

# 启动任务调度器
start_scheduler() {
    log_info "Starting Task Scheduler..."
    
    local pid_file="$PID_DIR/task-scheduler.pid"
    
    if [ -f "$pid_file" ] && kill -0 $(cat "$pid_file") 2>/dev/null; then
        log_warn "Task Scheduler already running (PID: $(cat "$pid_file"))"
        return 0
    fi
    
    cd "$PROJECT_DIR"
    nohup python3 agent_system/task_coordinator.py start-scheduler 10 > "$LOG_DIR/task-scheduler.log" 2>&1 &
    echo $! > "$pid_file"
    
    sleep 1
    if kill -0 $(cat "$pid_file") 2>/dev/null; then
        log_info "Task Scheduler started (PID: $(cat "$pid_file"))"
    else
        log_warn "Task Scheduler may need manual start"
    fi
}

# 停止任务调度器
stop_scheduler() {
    log_info "Stopping Task Scheduler..."
    
    local pid_file="$PID_DIR/task-scheduler.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
        fi
        rm -f "$pid_file"
        log_info "Task Scheduler stopped"
    fi
}

# 部署 Phase 3
deploy_phase3() {
    log_info "=== Deploying Phase 3: 职能分工与记忆增强 ==="
    
    # 设置权限
    chmod +x "$PROJECT_DIR/agent_system"/*.py 2>/dev/null || true
    chmod +x "$SCRIPT_DIR"/*.sh 2>/dev/null || true
    
    # 创建必要目录
    mkdir -p "$PROJECT_DIR/data/task_queue"
    mkdir -p "$PROJECT_DIR/data/cross_agent_memory"
    
    # 启动服务
    start_api_server
    start_scheduler
    
    log_info "=== Phase 3 Deployment Complete ==="
    log_info ""
    log_info "Services:"
    log_info "  - Dual Agent API: http://127.0.0.1:18087"
    log_info "  - Task Scheduler: Running (auto-assign every 10s)"
    log_info "  - Shared Memory: Active"
    log_info "  - Memory Bridge: Active"
    log_info ""
    log_info "API Endpoints:"
    log_info "  GET  /health              - 健康检查"
    log_info "  GET  /agents              - 获取所有代理状态"
    log_info "  POST /agents/status       - 更新代理状态"
    log_info "  POST /tasks               - 创建任务"
    log_info "  GET  /tasks/pending       - 获取待处理任务"
    log_info "  POST /memory              - 添加记忆"
    log_info "  GET  /memory/stats        - 记忆统计"
}

# 停止所有 Phase 3 服务
stop_phase3() {
    log_info "=== Stopping Phase 3 Services ==="
    stop_scheduler
    stop_api_server
    log_info "Phase 3 services stopped"
}

# 健康检查
health_check() {
    log_info "=== Phase 3 Health Check ==="
    
    local all_healthy=true
    
    # 检查 API Server
    if curl -sf http://127.0.0.1:18087/health > /dev/null 2>&1; then
        log_info "✓ Dual Agent API is healthy"
    else
        log_error "✗ Dual Agent API is not responding"
        all_healthy=false
    fi
    
    # 检查共享内存
    if python3 "$PROJECT_DIR/agent_system/shared_memory_system.py" cache-stats > /dev/null 2>&1; then
        log_info "✓ Shared Memory System is accessible"
    else
        log_warn "⚠ Shared Memory System status unknown"
    fi
    
    # 检查任务协调器
    if python3 "$PROJECT_DIR/agent_system/task_coordinator.py" stats > /dev/null 2>&1; then
        log_info "✓ Task Coordinator is accessible"
    else
        log_warn "⚠ Task Coordinator status unknown"
    fi
    
    if $all_healthy; then
        log_info "Phase 3 services are healthy!"
        return 0
    else
        log_error "Some Phase 3 services are unhealthy!"
        return 1
    fi
}

# 主命令处理
case "${1:-}" in
    deploy)
        deploy_phase3
        ;;
    
    stop)
        stop_phase3
        ;;
    
    restart)
        stop_phase3
        sleep 1
        deploy_phase3
        ;;
    
    health)
        health_check
        ;;
    
    *)
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  deploy    - Deploy Phase 3 services"
        echo "  stop      - Stop Phase 3 services"
        echo "  restart   - Restart Phase 3 services"
        echo "  health    - Health check"
        exit 1
        ;;
esac
