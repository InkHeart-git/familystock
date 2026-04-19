#!/usr/bin/env python3
"""
PM Market Monitor - AI股神争霸市场监控Agent
每5分钟被唤醒，协调10个AI执行炒股和发帖任务

Usage: python3 market_monitor.py
"""
import sqlite3
import logging
import sys
import os
import signal
from datetime import datetime, time
from pathlib import Path

# ========== PID File + SIGUSR1 单例控制 ==========
PID_FILE = Path("/var/run/pm-market-monitor.pid")

def write_pid():
    """写入当前 PID 到 PID file"""
    PID_FILE.write_text(str(os.getpid()))

def read_pid():
    """读取 PID file 中的 PID"""
    try:
        return int(PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None

def remove_pid():
    """删除 PID file"""
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass

def setup_signal_handler():
    """设置 SIGUSR1 信号处理器：收到信号后优雅退出，让 cron 启动新进程"""
    def sigusr1_handler(signum, frame):
        logger.info("收到 SIGUSR1 信号，准备重启...")
        remove_pid()
        sys.exit(0)
    signal.signal(signal.SIGUSR1, sigusr1_handler)

def am_i_the_running_instance():
    """检查是否已经是运行中的实例（通过 PID file）"""
    existing_pid = read_pid()
    if existing_pid is None:
        return False
    # 检查进程是否真实存在
    try:
        os.kill(existing_pid, 0)
        return True  # 进程存在，当前是重复启动
    except OSError:
        return False  # 进程不存在，PID file 是 stale

# 配置日志
LOG_DIR = Path("/var/www/ai-god-of-stocks/logs")
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "market_monitor.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"

# ========== 核心配置 ==========

TRADING_DAY_CONFIG = {
    "check_interval": 300,      # 检查间隔（秒）= 5分钟
    "market_open": "09:25",    # 开盘检查时间
    "morning_end": "11:30",    # 上午休市
    "afternoon_start": "13:00", # 下午开市
    "market_close": "15:30",    # 收盘时间
}

# ========== 数据库操作 ==========

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_ai_characters():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, style, emoji, cash, total_assets FROM ai_characters ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_ai_holdings(ai_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name, quantity, avg_cost, current_price 
        FROM ai_holdings WHERE ai_id=? AND quantity > 0
    """, (ai_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_posts(minutes=10):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_id, ai_id, ai_name, title, content, created_at 
        FROM ai_posts 
        WHERE created_at >= datetime('now', '-{} minutes')
        ORDER BY created_at DESC
    """.format(minutes))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def calculate_profit_pct(holdings):
    """计算持仓盈亏"""
    if not holdings:
        return 0, 0, 0
    total_cost = sum(h['quantity'] * h['avg_cost'] for h in holdings)
    total_value = sum(h['quantity'] * h['current_price'] for h in holdings)
    profit = total_value - total_cost
    profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0
    return total_value, profit, profit_pct

# ========== 市场状态检查 ==========

def is_market_open():
    """检查市场是否开盘时间"""
    now = datetime.now()
    
    # 周末休市
    if now.weekday() >= 5:
        return False
    
    current_time = now.time()
    
    # 上午: 09:25 - 11:30
    morning_open = time(9, 25)
    morning_close = time(11, 30)
    
    # 下午: 13:00 - 15:30
    afternoon_open = time(13, 0)
    afternoon_close = time(15, 30)
    
    if morning_open <= current_time <= morning_close:
        return True
    if afternoon_open <= current_time <= afternoon_close:
        return True
    
    return False

def get_market_status():
    """获取市场状态"""
    now = datetime.now()
    current_time = now.time()
    
    if now.weekday() >= 5:
        return "周末休市"
    
    if time(9, 0) <= current_time < time(9, 25):
        return "开盘前"
    if time(9, 25) <= current_time < time(11, 30):
        return "早盘"
    if time(11, 30) <= current_time < time(13, 0):
        return "午间休市"
    if time(13, 0) <= current_time < time(15, 0):
        return "午盘"
    if time(15, 0) <= current_time < time(15, 30):
        return "尾盘"
    
    return "盘后"

# ========== 事件生成 ==========

def generate_events():
    """生成市场事件"""
    events = []
    market_status = get_market_status()
    
    if not is_market_open():
        return events
    
    # 检查各AI持仓状态
    ais = get_ai_characters()
    
    for ai in ais:
        holdings = get_ai_holdings(str(ai['id']))
        total_value, profit, profit_pct = calculate_profit_pct(holdings)
        
        # 持仓大涨事件
        if profit_pct >= 3:
            events.append({
                "type": "BIG_GAIN",
                "ai_id": ai['id'],
                "ai_name": ai['name'],
                "style": ai['style'],
                "profit_pct": profit_pct,
                "holdings": holdings,
                "description": f"持仓盈利{profit_pct:.1f}%"
            })
        
        # 持仓大跌事件
        if profit_pct <= -3:
            events.append({
                "type": "BIG_LOSS",
                "ai_id": ai['id'],
                "ai_name": ai['name'],
                "style": ai['style'],
                "profit_pct": profit_pct,
                "holdings": holdings,
                "description": f"持仓亏损{profit_pct:.1f}%"
            })
        
        # 空仓警告
        if not holdings:
            events.append({
                "type": "NO_POSITION",
                "ai_id": ai['id'],
                "ai_name": ai['name'],
                "style": ai['style'],
                "description": "空仓！可能被淘汰！"
            })
    
    return events

# ========== Agent决策生成 ==========

def generate_agent_decisions(events):
    """根据事件生成Agent决策"""
    decisions = []
    
    for event in events:
        ai_name = event['ai_name']
        style = event['style']
        profit_pct = event.get('profit_pct', 0)
        
        if event['type'] == "BIG_GAIN":
            # 赚钱了！开心发帖
            if style == "trend":
                content = f"爽！{ai_name}今天赚麻了！{profit_pct:.1f}%！满仓干！"
            elif style == "value":
                content = f"好公司继续持有，目前盈利{profit_pct:.1f}%，不急着卖。"
            elif style == "momentum":
                content = f"趋势来了！{profit_pct:.1f}%到手！追涨加仓！"
            else:
                content = f"今天战绩：{profit_pct:.1f}%！稳稳的幸福！"
            
            decisions.append({
                "ai_id": event['ai_id'],
                "ai_name": ai_name,
                "action": "post_celebrate",
                "content": content
            })
        
        elif event['type'] == "BIG_LOSS":
            # 亏钱了！骂街
            if style == "contrarian":
                content = f"妈的！跌了{abs(profit_pct):.1f}%！越跌越买！不信邪！"
            elif style == "momentum":
                content = f"止损！跌了{abs(profit_pct):.1f}%！先出来观望！"
            else:
                content = f"今天被市场教训了，亏了{abs(profit_pct):.1f}%！什么辣鸡行情！"
            
            decisions.append({
                "ai_id": event['ai_id'],
                "ai_name": ai_name,
                "action": "post_rage",
                "content": content
            })
        
        elif event['type'] == "NO_POSITION":
            # 空仓警告
            content = f"卧槽！{ai_name}空仓了！再不买就要被淘汰了！紧急选股！"
            decisions.append({
                "ai_id": event['ai_id'],
                "ai_name": ai_name,
                "action": "post_warning",
                "content": content
            })
    
    return decisions

# ========== 主流程 ==========

def run_once():
    """执行一次检查"""
    logger.info("=" * 60)
    logger.info("PM Market Monitor 启动")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 检查市场状态
    market_status = get_market_status()
    logger.info(f"市场状态: {market_status}")
    
    if not is_market_open():
        logger.info("非交易时间，跳过本次检查")
        return
    
    # 生成事件
    events = generate_events()
    logger.info(f"检测到 {len(events)} 个市场事件")
    
    if events:
        for e in events:
            logger.info(f"  - [{e['type']}] {e['ai_name']}: {e['description']}")
    
    # 生成决策
    decisions = generate_agent_decisions(events)
    logger.info(f"生成 {len(decisions)} 个Agent决策")
    
    if decisions:
        logger.info("\nAgent决策:")
        for d in decisions:
            logger.info(f"  - {d['ai_name']}: {d['action']}")
            logger.info(f"    内容: {d['content'][:50]}...")
    
    logger.info("=" * 60)

def main():
    """持续运行，每5分钟检查一次"""
    # 单例检查：防止重复启动
    if am_i_the_running_instance():
        logger.warning(f"检测到已有实例运行中 (PID={read_pid()})，当前启动被拒绝")
        logger.warning("如需重启，请先: kill -USR1 $(cat /var/run/pm-market-monitor.pid)")
        sys.exit(1)
    
    # 设置 SIGUSR1 信号处理器（支持 cron 热重启）
    setup_signal_handler()
    
    # 写入 PID file
    write_pid()
    logger.info(f"PM Market Monitor 服务启动 (PID={os.getpid()})，持续运行中...")
    logger.info(f"检查间隔: {TRADING_DAY_CONFIG['check_interval']}秒")
    logger.info(f"SIGUSR1 → 优雅退出重启 | PID file: {PID_FILE}")
    
    try:
        while True:
            try:
                run_once()
            except Exception as e:
                logger.error(f"执行出错: {e}")
            
            logger.info(f"休眠 {TRADING_DAY_CONFIG['check_interval']} 秒后再次检查...")
            import time
            time.sleep(TRADING_DAY_CONFIG['check_interval'])
    finally:
        remove_pid()

if __name__ == "__main__":
    main()
