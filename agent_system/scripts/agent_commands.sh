#!/bin/bash
# Agent Commands - 子代理管理脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="/var/log/ai-god-of-stocks"
PID_DIR="/var/run/ai-god-of-stocks"

mkdir -p "$LOG_DIR" "$PID_DIR"

HERMES_PID_FILE="$PID_DIR/hermes-gateway.pid"
AGENT_TOOLS_PID_FILE="$PID_DIR/agent-tools.pid"

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

start_hermes() {
    log_info "Starting Hermes Gateway..."
    
    if [ -f "$HERMES_PID_FILE" ] && kill -0 $(cat "$HERMES_PID_FILE") 2>/dev/null; then
        log_warn "Hermes Gateway already running (PID: $(cat "$HERMES_PID_FILE"))"
        return 0
    fi
    
    cd /root/.hermes/hermes-agent
    nohup python3 -m gateway.run > "$LOG_DIR/hermes-gateway.log" 2>&1 &
    echo $! > "$HERMES_PID_FILE"
    
    sleep 2
    if kill -0 $(cat "$HERMES_PID_FILE") 2>/dev/null; then
        log_info "Hermes Gateway started (PID: $(cat "$HERMES_PID_FILE"))"
    else
        log_error "Failed to start Hermes Gateway"
        return 1
    fi
}

stop_hermes() {
    log_info "Stopping Hermes Gateway..."
    
    if [ -f "$HERMES_PID_FILE" ]; then
        local pid=$(cat "$HERMES_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                log_warn "Force killing Hermes Gateway..."
                kill -9 "$pid"
            fi
        fi
        rm -f "$HERMES_PID_FILE"
        log_info "Hermes Gateway stopped"
    else
        log_warn "Hermes Gateway is not running"
    fi
}

restart_hermes() {
    stop_hermes
    sleep 1
    start_hermes
}

status_hermes() {
    if [ -f "$HERMES_PID_FILE" ] && kill -0 $(cat "$HERMES_PID_FILE") 2>/dev/null; then
        log_info "Hermes Gateway: RUNNING (PID: $(cat "$HERMES_PID_FILE"))"
    else
        log_warn "Hermes Gateway: STOPPED"
    fi
}

health_check() {
    log_info "Running health check..."
    
    local all_healthy=true
    
    if [ -f "$HERMES_PID_FILE" ] && kill -0 $(cat "$HERMES_PID_FILE") 2>/dev/null; then
        log_info "✓ Hermes Gateway is healthy"
    else
        log_error "✗ Hermes Gateway is not running"
        all_healthy=false
    fi
    
    if python3 "$SCRIPT_DIR/../shared_memory_system.py" status > /dev/null 2>&1; then
        log_info "✓ Shared Memory System is accessible"
    else
        log_warn "⚠ Shared Memory System status unknown"
    fi
    
    if $all_healthy; then
        log_info "All systems are healthy!"
        return 0
    else
        log_error "Some systems are unhealthy!"
        return 1
    fi
}

backup_data() {
    local backup_dir="/var/backups/ai-god-of-stocks/$(date +%Y%m%d_%H%M%S)"
    log_info "Creating backup at $backup_dir..."
    
    mkdir -p "$backup_dir"
    cp -r "$PROJECT_DIR/data" "$backup_dir/"
    cp -r "$PROJECT_DIR/config" "$backup_dir/" 2>/dev/null || true
    cp -r "$PROJECT_DIR/agent_system" "$backup_dir/" 2>/dev/null || true
    
    log_info "Backup completed: $backup_dir"
    echo "$backup_dir"
}

case "${1:-}" in
    start)
        case "${2:-all}" in
            hermes) start_hermes ;;
            all) start_hermes ;;
            *) log_error "Unknown component: $2"; exit 1 ;;
        esac
        ;;
    
    stop)
        case "${2:-all}" in
            hermes) stop_hermes ;;
            all) stop_hermes ;;
            *) log_error "Unknown component: $2"; exit 1 ;;
        esac
        ;;
    
    restart)
        case "${2:-all}" in
            hermes) restart_hermes ;;
            all) restart_hermes ;;
            *) log_error "Unknown component: $2"; exit 1 ;;
        esac
        ;;
    
    status)
        status_hermes
        ;;
    
    health)
        health_check
        ;;
    
    backup)
        backup_data
        ;;
    
    *)
        echo "Usage: $0 <command> [component]"
        echo ""
        echo "Commands:"
        echo "  start [hermes|all]    - Start services"
        echo "  stop [hermes|all]     - Stop services"
        echo "  restart [hermes|all]  - Restart services"
        echo "  status                - Show status"
        echo "  health                - Run health check"
        echo "  backup                - Create data backup"
        exit 1
        ;;
esac
