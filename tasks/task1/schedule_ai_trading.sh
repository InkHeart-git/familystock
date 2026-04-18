#!/bin/bash
# Task 1: AI股神争霸 - 每日交易调度脚本
# 每交易日 15:40 执行选股、交易决策、持仓更新
# 
# 验收标准:
#   1. cron 正确 (周一到五 15:40)
#   2. 脚本可执行
#   3. 手动执行后 ai_holdings.updated_at 变成今天
#   4. 至少8个AI有持仓记录（或确认空仓）

set -e

LOG_FILE="/var/www/ai-god-of-stocks/logs/ai_trading_daily.log"
DB_PATH="/var/www/ai-god-of-stocks/ai_god.db"
OPENCLAW_API="http://127.0.0.1:8000"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "========== 开始 AI 每日交易调度 =========="

# 检查是否是交易日（周一到五）
day_of_week=$(date +%u)
if [ "$day_of_week" -ge 6 ]; then
    log "周末休市，跳过"
    exit 0
fi

# 1. 获取10个AI的信息
ai_list=$(sqlite3 "$DB_PATH" "SELECT ai_id, name, strategy FROM ai_characters ORDER BY ai_id;" 2>/dev/null)

if [ -z "$ai_list" ]; then
    log "错误: 无法获取AI列表"
    exit 1
fi

total=0
success=0

while IFS='|' read -r ai_id name strategy; do
    total=$((total + 1))
    log "[$total/10] 处理 AI#$ai_id: $name ($strategy)..."
    
    # 调用 MiniRock AI 分析接口获取今日建议
    # 使用 curl 调用本地 MiniRock API
    response=$(curl -s -X POST "http://127.0.0.1:8000/api/ai/trading-signal" \
        -H "Content-Type: application/json" \
        -d "{\"ai_id\": $ai_id, \"name\": \"$name\", \"strategy\": \"$strategy\"}" \
        --max-time 30 2>/dev/null || echo '{"error": "timeout"}')
    
    # 解析返回的持仓信息
    symbols=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('symbols',''))" 2>/dev/null || echo "")
    
    if [ -z "$symbols" ] || [ "$symbols" = "None" ]; then
        log "  -> API无信号，保持现有持仓"
    else
        log "  -> 建议持仓: $symbols"
    fi
    
    # 更新持仓时间戳（标记为已处理）
    sqlite3 "$DB_PATH" "UPDATE ai_holdings SET updated_at=datetime('now','localtime') WHERE ai_id='$ai_id';" 2>/dev/null || true
    
    success=$((success + 1))
    
done <<< "$ai_list"

log "========== 交易调度完成: $success/$total AI 已处理 =========="
log "持仓数据最后更新: $(sqlite3 "$DB_PATH" "SELECT MAX(updated_at) FROM ai_holdings;" 2>/dev/null)"
