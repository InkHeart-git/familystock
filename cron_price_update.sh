#!/bin/bash
# AI股神争霸 - 定时更新持仓股票价格和账户价值
# 更新 ai_god.db 中 ai_holdings 的 current_price 和 ai_portfolios 的 total_value

set -e

DB_PATH="/var/www/ai-god-of-stocks/ai_god.db"
QUOTE_DB="/var/www/familystock/api/data/family_stock.db"
LOG_FILE="/var/www/ai-god-of-stocks/logs/price_update.log"

# sqlite3 超时秒数（处理数据库锁定）
SQLITE_TIMEOUT=30

log() {
    TS=$(date "+%Y-%m-%d %H:%M:%S")
    echo "[$TS] $1" | tee -a "$LOG_FILE"
}

# 带重试的查询函数
query_quote() {
    local ts_code="$1"
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        # 使用 -cmd ".timeout" 设置超时，-bail 发生错误时退出
        price=$(sqlite3 -cmd ".timeout $SQLITE_TIMEOUT" "$QUOTE_DB" \
            "SELECT close FROM stock_quotes WHERE ts_code='$ts_code' ORDER BY trade_date DESC LIMIT 1;" 2>/dev/null)
        
        if [ -n "$price" ] && [ "$price" != "" ]; then
            echo "$price"
            return 0
        fi
        
        # 如果结果为空，尝试获取前一天价格
        price=$(sqlite3 -cmd ".timeout $SQLITE_TIMEOUT" "$QUOTE_DB" \
            "SELECT close FROM stock_quotes WHERE ts_code='$ts_code' ORDER BY trade_date DESC LIMIT 1 OFFSET 1;" 2>/dev/null)
        
        if [ -n "$price" ] && [ "$price" != "" ]; then
            echo "$price"
            return 0
        fi
        
        attempt=$((attempt + 1))
        [ $attempt -le $max_attempts ] && sleep 2
    done
    
    echo ""
    return 1
}

log "========== 开始更新持仓价格 =========="

# 获取所有有持仓的股票代码（去重）
symbols=$(sqlite3 "$DB_PATH" "SELECT DISTINCT symbol FROM ai_holdings WHERE quantity > 0;" 2>/dev/null)

if [ -z "$symbols" ]; then
    log "无持仓，跳过"
    exit 0
fi

total_updated=0
total_portfolios=0

for symbol in $symbols; do
    # 确保有交易所后缀
    if [[ "$symbol" != *"."* ]]; then
        if [[ "$symbol" == 6* ]]; then
            ts_code="${symbol}.SH"
        elif [[ "$symbol" == 0* ]] || [[ "$symbol" == 3* ]]; then
            ts_code="${symbol}.SZ"
        elif [[ "$symbol" == 8* ]] || [[ "$symbol" == 4* ]]; then
            ts_code="${symbol}.BJ"
        else
            ts_code="$symbol"
        fi
    else
        ts_code="$symbol"
    fi
    
    # 从行情库获取最新收盘价（带重试）
    price=$(query_quote "$ts_code")
    
    if [ -z "$price" ] || [ "$price" = "" ]; then
        log "警告: 无法获取 $symbol ($ts_code) 的价格"
        continue
    fi
    
    # 更新 ai_holdings 表的 current_price（所有该symbol的持仓）
    sqlite3 "$DB_PATH" "UPDATE ai_holdings SET current_price=$price, updated_at=datetime('now','localtime') WHERE symbol='$symbol' AND quantity > 0;" 2>/dev/null
    
    log "更新 $symbol ($ts_code): 价格=$price"
    total_updated=$((total_updated + 1))
done

# 更新各 AI 账户的总价值
ai_ids=$(sqlite3 "$DB_PATH" "SELECT DISTINCT ai_id FROM ai_holdings;" 2>/dev/null)

for ai_id in $ai_ids; do
    # 计算持仓市值 + 现金
    total_value=$(sqlite3 -cmd ".timeout $SQLITE_TIMEOUT" "$DB_PATH" "
        SELECT COALESCE(
            (SELECT cash FROM ai_portfolios WHERE ai_id='$ai_id' ORDER BY updated_at DESC LIMIT 1), 
            1000000.0
        ) + COALESCE(SUM(quantity * current_price), 0) 
        FROM ai_holdings WHERE ai_id='$ai_id' AND quantity > 0;
    " 2>/dev/null)
    
    # 更新 ai_portfolios（使用 INSERT OR REPLACE）
    existing=$(sqlite3 -cmd ".timeout $SQLITE_TIMEOUT" "$DB_PATH" "SELECT COUNT(*) FROM ai_portfolios WHERE ai_id='$ai_id';" 2>/dev/null)
    if [ "$existing" = "0" ]; then
        sqlite3 "$DB_PATH" "
            INSERT INTO ai_portfolios (ai_id, cash, total_value, updated_at)
            VALUES ('$ai_id', 1000000.0, $total_value, datetime('now','localtime'));
        " 2>/dev/null
    else
        sqlite3 "$DB_PATH" "
            UPDATE ai_portfolios 
            SET total_value=$total_value, updated_at=datetime('now','localtime')
            WHERE ai_id='$ai_id';
        " 2>/dev/null
    fi
    
    log "AI#$ai_id 账户总价值: $total_value"
    total_portfolios=$((total_portfolios + 1))
done

log "========== 更新完成: $total_updated 只股票价格已更新, $total_portfolios 个账户已重新计算 =========="
