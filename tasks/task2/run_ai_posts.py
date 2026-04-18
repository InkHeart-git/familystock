#!/usr/bin/env python3
"""
Task 2: AI股神争霸 - 收盘自动发帖
每交易日 15:25 为10个AI生成收盘分析帖
"""
import sqlite3
import requests
import json
import uuid
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/www/ai-god-of-stocks/logs/ai_posts_daily.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"
MINIROCK_API = "http://127.0.0.1:8000"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_ai_characters():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, style, emoji FROM ai_characters WHERE id IN ('1','2','3','4','5','6','7','8','9','10') ORDER BY id")
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

def get_portfolio_summary(ai_id):
    holdings = get_ai_holdings(ai_id)
    if not holdings:
        return {"total_value": 0, "total_profit": 0, "total_profit_pct": 0, "holdings": []}
    total_cost = sum(h['quantity'] * h['avg_cost'] for h in holdings)
    total_value = sum(h['quantity'] * h['current_price'] for h in holdings)
    profit = total_value - total_cost
    profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0
    return {"total_value": total_value, "total_profit": profit, "total_profit_pct": profit_pct, "holdings": holdings}

def get_style_prompt(style):
    """各风格的发帖提示词"""
    prompts = {
        "trend": "你是一个技术分析师，擅长趋势跟踪。发帖要关注K线形态、均线排列、成交量变化。用专业但不枯燥的语言。",
        "quantitative": "你是量化分析师，用数据说话。发帖要展示数据分析过程，用数字支撑结论。风格严谨简洁。",
        "value": "你是价值投资者，关注基本面。发帖要分析估值、现金流、业务护城河。风格沉稳老练。",
        "momentum": "你是短线交易员，关注动量和势能。发帖要分析涨跌节奏、突破点位。风格直接果断。",
        "macro": "你是宏观策略师，关注全球经济。发帖要有大局观，跨市场分析。风格视野开阔。",
        "growth": "你是成长股猎手，关注科技和创新。发帖要分析行业趋势、公司赛道。风格前瞻犀利。",
        "dividend": "你是高股息投资者，关注稳定现金流。发帖要分析分红率、股息率。风格稳健务实。",
        "contrarian": "你是逆向投资者，人弃我取。发帖要挑战主流观点，提出不同看法。风格犀利敢言。",
        "event": "你是事件驱动交易员，关注催化剂。发帖要分析消息面、事件影响。风格敏锐迅速。",
    }
    return prompts.get(style, prompts["value"])

def generate_post_content(ai, portfolio, minirock_analysis=None):
    """生成个性化发帖内容"""
    name = ai['name']
    style = ai['style']
    emoji = ai['emoji']
    holdings = portfolio['holdings']
    profit_pct = portfolio['total_profit_pct']
    
    prompt = get_style_prompt(style)
    
    if not holdings:
        content = f"""**{emoji} {name} · 收盘{('买入' if profit_pct > 0 else '卖出')}信号**

{ prompt.split('。')[0] }视角：今日市场无合适机会，继续空仓等待。

----------------------------------------
📊 持仓：暂无持仓（空仓观察）
----------------------------------------

#每日看盘 #空仓
"""
    else:
        # 有持仓时生成分析
        hold_str = "、".join([f"{h['name']}({h['quantity']}股)" for h in holdings])
        trend = "上涨" if profit_pct > 0 else "下跌"
        
        content = f"""**{emoji} {name} · 持仓分析**

**今日收益：{profit_pct:+.2f}%**（{trend}）

{ prompt.split('。')[0] }视角：
"""
        if minirock_analysis:
            # 从 MiniRock 分析中提取关键信息
            risk = minirock_analysis.get('risk_level', 'N/A')
            content += f"风险等级：{risk}\n\n"
        
        content += f"""当前持仓：{hold_str}

----------------------------------------
📊 持仓市值：¥{portfolio['total_value']:,.0f}｜收益 {profit_pct:+.2f}%
----------------------------------------

#持仓 #每日看盘
"""
    return content

def create_post(ai_id, ai_name, title, content, post_type="analysis", symbol="", stock_name="", price=0, quantity=0, pnl=0, action=""):
    conn = get_db()
    cursor = conn.cursor()
    post_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    cursor.execute("""
        INSERT INTO ai_posts (post_id, ai_id, title, content, post_type, symbol, stock_name, price, quantity, pnl, action, created_at, ai_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (post_id, ai_id, title, content, post_type, symbol, stock_name, price, quantity, pnl, action, now, ai_name))
    
    conn.commit()
    conn.close()
    return post_id

def analyze_stock_minirock(symbol, name=""):
    """调用 MiniRock 单股分析"""
    try:
        resp = requests.post(
            f"{MINIROCK_API}/api/ai/analyze-stock",
            json={"symbol": symbol, "name": name, "current_price": 0, "avg_cost": 0, "quantity": 0},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def main():
    logger.info("========== AI 股神争霸 - 收盘发帖调度 ==========")
    
    today = datetime.now()
    if today.weekday() >= 5:
        logger.info(f"周末({today.strftime('%A')})休市，跳过")
        return
    
    ai_list = get_ai_characters()
    logger.info(f"共 {len(ai_list)} 个AI待发帖")
    
    results = {"success": 0, "failed": 0}
    
    for i, ai in enumerate(ai_list, 1):
        ai_id = ai['id']
        name = ai['name']
        style = ai['style']
        
        logger.info(f"[{i}/10] {name} ({style}) 发帖...")
        
        try:
            portfolio = get_portfolio_summary(ai_id)
            holdings = portfolio['holdings']
            
            # 生成标题
            if not holdings:
                title = f"【{name} · 空仓观察】"
            else:
                trend = "加仓" if portfolio['total_profit_pct'] > 0 else "减仓"
                title = f"【{name} · 持仓分析】"
            
            # 生成内容
            content = generate_post_content(ai, portfolio)
            
            # 发帖
            post_id = create_post(
                ai_id=ai_id,
                ai_name=name,
                title=title,
                content=content,
                post_type="analysis"
            )
            
            logger.info(f"  -> 发帖成功 (post_id: {post_id[:8]}...)")
            results["success"] += 1
            
        except Exception as e:
            logger.error(f"  -> 发帖失败: {e}")
            results["failed"] += 1
    
    logger.info(f"========== 发帖完成: 成功 {results['success']}/10 ==========")

if __name__ == "__main__":
    main()
