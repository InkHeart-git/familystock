#!/bin/bash
# AI股神争霸 - 子代理管理脚本
# 重建版本 2026-04-17

set -e

BASE_DIR="/var/www/ai-god-of-stocks"
LOG_DIR="$BASE_DIR/logs"
PID_DIR="$BASE_DIR/pids"

echo "🤖 AI股神争霸子代理管理系统"
echo "=============================="

# 创建必要目录
mkdir -p $LOG_DIR $PID_DIR

# 显示帮助
show_help() {
    echo "用法: $0 [命令]"
    echo ""
    echo "命令:"
    echo "  spawn_all_ai          启动所有AI子代理"
    echo "  spawn_single <ai_id>  启动单个AI子代理"
    echo "  stop_all              停止所有AI子代理"
    echo "  status                查看子代理状态"
    echo "  health_check          健康检查"
    echo "  morning_posts         执行早盘发帖"
    echo "  afternoon_posts       执行午盘发帖"
    echo "  daily_report          生成每日报告"
    echo ""
}

# 启动所有AI子代理
spawn_all_ai() {
    echo "🚀 启动所有AI子代理..."
    
    # 10个AI角色ID (字符ID)
    AI_IDS=(trend_chaser quant_queen value_veteran scalper_fairy macro_master tech_whiz dividend_hunter turnaround_pro momentum_kid event_driven)
    AI_NAMES=(1 2 3 4 5 6 7 8 9 10)
    
    for i in "${!AI_IDS[@]}"; do
        ai_id="${AI_IDS[$i]}"
        ai_name="${AI_NAMES[$i]}"
        echo "  启动 AI-$ai_name ($ai_id)..."
        nohup python3 $BASE_DIR/backup_old/run_single_ai.py $ai_id > $LOG_DIR/ai_${ai_name}.log 2>&1 &
        echo $! > $PID_DIR/ai_${ai_id}.pid
        sleep 1
    done
    
    echo "✅ 所有AI子代理已启动"
    echo "📊 查看日志: tail -f $LOG_DIR/ai_*.log"
}

# 启动单个AI子代理
spawn_single() {
    local ai_id=$1
    if [ -z "$ai_id" ]; then
        echo "❌ 请指定AI ID (1-10)"
        exit 1
    fi
    
    echo "🚀 启动AI-$ai_id..."
    nohup python3 $BASE_DIR/backup_old/run_single_ai.py $ai_id > $LOG_DIR/ai_${ai_id}.log 2>&1 &
    echo $! > $PID_DIR/ai_${ai_id}.pid
    echo "✅ AI-$ai_id 已启动 (PID: $!)"
}

# 停止所有AI子代理
stop_all() {
    echo "🛑 停止所有AI子代理..."
    
    for pid_file in $PID_DIR/*.pid; do
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            local name=$(basename "$pid_file" .pid)
            if kill -0 $pid 2>/dev/null; then
                echo "  停止 $name (PID: $pid)..."
                kill $pid 2>/dev/null || kill -9 $pid 2>/dev/null
            fi
            rm -f "$pid_file"
        fi
    done
    
    # 清理可能残留的Python进程
    pkill -f "run_single_ai.py" 2>/dev/null || true
    
    echo "✅ 所有AI子代理已停止"
}

# 查看状态
show_status() {
    echo "📊 子代理状态"
    echo "=============="
    
    local running=0
    local stopped=0
    
    for i in {1..10}; do
        local pid_file="$PID_DIR/ai_$i.pid"
        if [ -f "$pid_file" ]; then
            local pid=$(cat "$pid_file")
            if kill -0 $pid 2>/dev/null; then
                echo "  AI-$i: 🟢 运行中 (PID: $pid)"
                ((running++))
            else
                echo "  AI-$i: 🔴 已停止 (PID文件残留)"
                ((stopped++))
                rm -f "$pid_file"
            fi
        else
            echo "  AI-$i: ⚪ 未启动"
            ((stopped++))
        fi
    done
    
    echo ""
    echo "总计: $running 运行中, $stopped 停止"
}

# 健康检查
health_check() {
    echo "🏥 健康检查"
    echo "==========="
    
    # 检查API服务
    if curl -s http://127.0.0.1:18085/api/ai/characters > /dev/null 2>&1; then
        echo "  ✅ API服务正常 (端口18085)"
    else
        echo "  ❌ API服务异常"
    fi
    
    # 检查数据库
    if [ -f "$BASE_DIR/ai_god.db" ] && [ -s "$BASE_DIR/ai_god.db" ]; then
        local size=$(du -h "$BASE_DIR/ai_god.db" | cut -f1)
        echo "  ✅ 数据库正常 ($size)"
    else
        echo "  ❌ 数据库异常"
    fi
    
    # 检查子代理
    show_status
}

# 执行早盘发帖
morning_posts() {
    echo "🌅 执行早盘发帖..."
    python3 $BASE_DIR/backup_old/trigger_morning_posts.py
    echo "✅ 早盘发帖完成"
}

# 执行午盘发帖
afternoon_posts() {
    echo "🌇 执行午盘发帖..."
    # 使用generate_social_posts.py生成帖子
    python3 $BASE_DIR/backup_old/generate_social_posts.py --session afternoon
    echo "✅ 午盘发帖完成"
}

# 生成每日报告
daily_report() {
    echo "📈 生成每日报告..."
    
    # 调用market_monitor.py生成报告
    python3 $BASE_DIR/market_monitor.py
    
    echo "✅ 每日报告已生成"
}

# 主命令处理
case "${1:-help}" in
    spawn_all_ai)
        spawn_all_ai
        ;;
    spawn_single)
        spawn_single $2
        ;;
    stop_all)
        stop_all
        ;;
    status)
        show_status
        ;;
    health_check)
        health_check
        ;;
    morning_posts)
        morning_posts
        ;;
    afternoon_posts)
        afternoon_posts
        ;;
    daily_report)
        daily_report
        ;;
    help|*)
        show_help
        ;;
esac
