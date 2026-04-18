#!/bin/bash
# Dual Agent Health Check Script
# Phase 1: 稳定性保障层 - 心跳监控与故障切换

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/var/log/ai-god-of-stocks/health.log"

# 飞书PM通道配置
FEISHU_CHAT_ID="${FEISHU_PM_CHAT_ID:-oc_aa3d709656605d612491d47abe9da0b9}"

# 健康检查阈值
HEALTH_CHECK_INTERVAL=60
SUBAGENT_TIMEOUT=30
MAX_RETRY=3

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查子代理健康状态
check_subagent_health() {
    local agent_name=$1
    local agent_url=$2
    
    log "Checking health of $agent_name at $agent_url"
    
    for i in $(seq 1 $MAX_RETRY); do
        if curl -sf --max-time $SUBAGENT_TIMEOUT "$agent_url/health" > /dev/null 2>&1; then
            log "$agent_name is healthy"
            return 0
        fi
        log "Attempt $i/$MAX_RETRY failed for $agent_name"
        sleep 2
    done
    
    log "ERROR: $agent_name is unhealthy after $MAX_RETRY attempts"
    return 1
}

# 发送飞书告警
send_feishu_alert() {
    local message=$1
    local priority=${2:-"normal"}
    
    log "Sending $priority alert: $message"
    
    # 写入告警日志，由主代理处理发送
    echo "$(date -Iseconds)|$priority|$message" >> "/var/www/ai-god-of-stocks/data/alerts.log"
}

# 主健康检查循环
main_health_check() {
    log "=== Starting Dual Agent Health Check ==="
    
    # 检查主代理 (Lingxi/OpenClaw)
    if ! check_subagent_health "lingxi" "http://127.0.0.1:18086"; then
        send_feishu_alert "主代理 Lingxi 无响应" "critical"
    fi
    
    # 检查 Hermes Gateway
    if ! pgrep -f "hermes-gateway" > /dev/null; then
        send_feishu_alert "Hermes Gateway 进程未运行" "critical"
    fi
    
    # 检查子代理状态
    if [ -f "/var/www/ai-god-of-stocks/data/subagent_state.json" ]; then
        local last_update=$(stat -c %Y "/var/www/ai-god-of-stocks/data/subagent_state.json" 2>/dev/null || echo 0)
        local current_time=$(date +%s)
        local time_diff=$((current_time - last_update))
        
        if [ $time_diff -gt 300 ]; then
            send_feishu_alert "子代理状态超过5分钟未更新" "warning"
        fi
    fi
    
    log "=== Health Check Complete ==="
}

# 执行主检查
main_health_check
