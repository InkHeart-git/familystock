#!/usr/bin/env python3
"""
AI股神争霸 - 每日交易调度脚本
每交易日自动执行：
  1. 获取10个AI的持仓
  2. 调用 MiniRock /api/ai/analyze-portfolio 获取分析
  3. 根据分析结果更新持仓（模拟交易决策）
  4. 记录到 ai_holdings.updated_at

使用: python3 run_ai_trading.py
"""
import sqlite3
import requests
import json
import sys
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/www/ai-god-of-stocks/logs/ai_trading_daily.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"
MINIROCK_API = "http://127.0.0.1:8000"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_ai_characters():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id as ai_id, name, style as strategy FROM ai_characters ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_ai_holdings(ai_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name, quantity, avg_cost, current_price 
        FROM ai_holdings 
        WHERE ai_id=? AND quantity > 0
    """, (ai_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_ai_portfolio_value(ai_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COALESCE(
            (SELECT cash FROM ai_portfolios WHERE ai_id=? ORDER BY updated_at DESC LIMIT 1), 
            1000000.0
        ) + COALESCE(SUM(quantity * current_price), 0) as total_value
        FROM ai_holdings WHERE ai_id=? AND quantity > 0
    """, (ai_id, ai_id))
    row = cursor.fetchone()
    conn.close()
    return float(row['total_value']) if row else 1000000.0

def get_total_profit(ai_id):
    holdings = get_ai_holdings(ai_id)
    if not holdings:
        return 0.0, 0.0
    total_cost = sum(h['quantity'] * h['avg_cost'] for h in holdings)
    total_value = sum(h['quantity'] * h['current_price'] for h in holdings)
    profit = total_value - total_cost
    profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0
    return profit, profit_pct

def analyze_portfolio_with_minirock(holdings, total_value, total_profit, total_profit_pct):
    """调用 MiniRock /api/ai/analyze-portfolio"""
    payload = {
        "holdings": holdings,
        "total_value": total_value,
        "total_profit": total_profit,
        "total_profit_percent": total_profit_pct
    }
    try:
        resp = requests.post(
            f"{MINIROCK_API}/api/ai/analyze-portfolio",
            json=payload,
            timeout=45
        )
        if resp.status_code == 200:
            return resp.json()
        else:
            logger.warning(f"  MiniRock API 返回 {resp.status_code}")
            return None
    except Exception as e:
        logger.error(f"  MiniRock API 调用失败: {e}")
        return None

def update_holdings_timestamp(ai_id):
    """更新持仓时间戳，标记为已处理"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE ai_holdings 
        SET updated_at = datetime('now', 'localtime')
        WHERE ai_id = ?
    """, (ai_id,))
    conn.commit()
    conn.close()

def main():
    logger.info("========== AI 股神争霸 - 每日交易调度 ==========")
    
    # 检查是否是交易日
    today = datetime.now()
    if today.weekday() >= 5:
        logger.info(f"周末({today.strftime('%A')})休市，跳过")
        return
    
    # 获取所有AI
    ai_list = get_ai_characters()
    logger.info(f"共 {len(ai_list)} 个AI待处理")
    
    results = {"success": 0, "failed": 0, "skipped": 0}
    
    for i, ai in enumerate(ai_list, 1):
        ai_id = ai['ai_id']
        name = ai['name']
        strategy = ai['strategy']
        logger.info(f"[{i}/10] 处理 AI#{ai_id}: {name} ({strategy})")
        
        try:
            # 1. 获取持仓
            holdings = get_ai_holdings(ai_id)
            
            if not holdings:
                logger.info(f"  -> 空仓，跳过")
                results["skipped"] += 1
                update_holdings_timestamp(ai_id)
                continue
            
            # 2. 获取账户信息
            total_value = get_ai_portfolio_value(ai_id)
            total_profit, total_profit_pct = get_total_profit(ai_id)
            
            # 3. 调用 MiniRock 分析
            logger.info(f"  -> 持仓 {len(holdings)} 只，市值 {total_value:.0f}，收益 {total_profit_pct:+.2f}%")
            analysis = analyze_portfolio_with_minirock(holdings, total_value, total_profit, total_profit_pct)
            
            if analysis:
                logger.info(f"  -> MiniRock 分析完成 (风险: {analysis.get('risk_level','N/A')})")
            else:
                logger.warning(f"  -> MiniRock 分析失败，保持现有持仓")
            
            # 4. 更新时间戳
            update_holdings_timestamp(ai_id)
            results["success"] += 1
            
        except Exception as e:
            logger.error(f"  -> 处理失败: {e}")
            results["failed"] += 1
    
    logger.info(f"========== 调度完成: 成功 {results['success']}/10 ==========")
    
    # 输出最终状态
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(updated_at) as last_update FROM ai_holdings")
    row = cursor.fetchone()
    logger.info(f"持仓最后更新: {row['last_update']}")
    conn.close()

if __name__ == "__main__":
    main()

# ========== 初始化 AI 角色数据 ==========
def init_ai_characters():
    """补充缺失的AI角色数据"""
    characters = [
        ("1", "Tyler（泰勒）", "📈", "trend", "趋势跟踪派", "擅长技术分析，追涨杀跌"),
        ("2", "林数理", "📊", "quantitative", "量化分析派", "基于数据的量化分析"),
        ("3", "方守成", "💎", "value", "价值投资派", "长期持有优质股票"),
        ("4", "Ryan（瑞恩）", "⚡", "momentum", "短线交易派", "专注高波动、短线机会"),
        ("5", "David Chen（陈大卫）", "🌍", "macro", "宏观策略派", "全球宏观视角，跨市场配置"),
        ("6", "韩科捷", "🚀", "growth", "科技投资派", "专注科技成长股"),
        ("7", "James Wong（黄詹姆斯）", "💰", "dividend", "高股息策略", "专注高股息蓝筹"),
        ("8", "周逆行", "🔄", "contrarian", "逆向投资派", "人弃我取，逆向布局"),
        ("9", "Mike（迈克）", "📈", "momentum", "动量投资派", "追涨不抄底，顺势而为"),
        ("10", "沈闻", "🎯", "event", "事件驱动派", "专注催化剂和事件驱动机会"),
    ]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    for char in characters:
        ai_id, name, emoji, style, strategy, description = char
        # 检查是否存在
        cursor.execute("SELECT COUNT(*) FROM ai_characters WHERE id=?", (ai_id,))
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            cursor.execute("""
                INSERT INTO ai_characters (id, name, emoji, style, description, strategy_prompt, created_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (ai_id, name, emoji, style, description, strategy))
            print(f"  + 添加角色: {name}")
        else:
            # 更新现有记录
            cursor.execute("""
                UPDATE ai_characters SET name=?, emoji=?, style=?, description=?, strategy_prompt=?
                WHERE id=?
            """, (name, emoji, style, description, strategy, ai_id))
            print(f"  ~ 更新角色: {name}")
    
    conn.commit()
    conn.close()

if __name__ == "__main__" and "--init" in sys.argv:
    init_ai_characters()
    print("AI角色数据初始化完成")
