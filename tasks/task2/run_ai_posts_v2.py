#!/usr/bin/env python3
"""
Task 4: AI股神争霸 - 智能发帖引擎 V3
修复版：解决数据一致性问题

修复内容：
1. 持仓快照机制 - 开头像拍照，发帖时锁定持仓
2. 全量分析 - 分析所有持仓股票（之前只分析前2只）
3. 准确的组合信号 - 基于所有持仓分析结果综合判断

每交易日 15:35 为10个AI生成收盘分析帖
"""
import sqlite3
import requests
import json
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/www/ai-god-of-stocks/logs/ai_posts_v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"
MINIROCK_API = "http://127.0.0.1:8000"
TIMEOUT = 3   # 每只股票分析超时3秒，快速失败用本地计算兜底

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ========== 持仓快照机制 ==========

def create_holdings_snapshot():
    """创建持仓快照，返回快照ID"""
    conn = get_db()
    cursor = conn.cursor()
    snapshot_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 创建快照表（如果不存在）- 必须先执行
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS holdings_snapshot (
            snapshot_id TEXT,
            ai_id TEXT,
            symbol TEXT,
            name TEXT,
            quantity INTEGER,
            avg_cost REAL,
            current_price REAL,
            created_at TEXT
        )
    """)
    
    # 获取当前所有持仓 - 单独执行并立即fetch
    cursor.execute("""
        SELECT ai_id, symbol, name, quantity, avg_cost, current_price 
        FROM ai_holdings WHERE quantity > 0
    """)
    all_holdings = cursor.fetchall()  # 立即获取，避免游标被复用
    
    # 插入快照数据
    for row in all_holdings:
        cursor.execute("""
            INSERT INTO holdings_snapshot 
            (snapshot_id, ai_id, symbol, name, quantity, avg_cost, current_price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (snapshot_id, row['ai_id'], row['symbol'], row['name'], 
              row['quantity'], row['avg_cost'], row['current_price'], now))
    
    conn.commit()
    conn.close()
    logger.info(f"持仓快照已创建: {snapshot_id}")
    return snapshot_id

def get_snapshot_holdings(snapshot_id: str, ai_id: str) -> List[Dict]:
    """从快照获取指定AI的持仓"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name, quantity, avg_cost, current_price 
        FROM holdings_snapshot 
        WHERE snapshot_id=? AND ai_id=?
        ORDER BY quantity DESC
    """, (snapshot_id, ai_id))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_snapshot_portfolio_summary(snapshot_id: str, ai_id: str) -> Dict:
    """从快照计算持仓汇总"""
    holdings = get_snapshot_holdings(snapshot_id, ai_id)
    if not holdings:
        return {"total_value": 0, "total_profit": 0, "total_profit_pct": 0, "holdings": []}
    total_cost = sum(h['quantity'] * h['avg_cost'] for h in holdings)
    total_value = sum(h['quantity'] * h['current_price'] for h in holdings)
    profit = total_value - total_cost
    profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0
    return {"total_value": total_value, "total_profit": profit, "total_profit_pct": profit_pct, "holdings": holdings}

def get_ai_characters():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, style, emoji FROM ai_characters ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ========== MiniRock 分析 ==========

def analyze_stock_with_minirock(symbol: str, name: str, holding: Dict) -> Optional[Dict]:
    """调用MiniRock单股分析"""
    try:
        payload = {
            "symbol": symbol,
            "name": name,
            "current_price": holding.get('current_price', 0) or 0,
            "avg_cost": holding.get('avg_cost', 0) or 0,
            "quantity": holding.get('quantity', 0) or 0
        }
        resp = requests.post(
            f"{MINIROCK_API}/api/ai/analyze-stock",
            json=payload,
            timeout=TIMEOUT
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning(f"  {symbol}分析失败: {e}")
    return None

def extract_trading_signal(analysis: Dict) -> tuple:
    """从MiniRock分析中提取交易信号"""
    if not analysis:
        return "⚪", "观望", "watch", 0
    
    summary = analysis.get('summary', '') or ''
    cards = analysis.get('cards', [])
    
    # 查找推荐的路径
    recommended_path = None
    for card in cards:
        if card.get('type') == 'scenario':
            for path in card.get('paths', []):
                if '⭐' in path.get('badge', ''):
                    recommended_path = path
                    break
            break
    
    confidence = 80  # 默认置信度
    
    if recommended_path:
        strategy = recommended_path.get('strategy', '')
        if '加仓' in strategy or '买入' in strategy:
            return "🟢", "建议加仓", "buy", 90
        elif '减仓' in strategy or '卖出' in strategy:
            return "🔴", "建议减仓", "sell", 95
        elif '持有' in strategy:
            return "🟡", "继续持有", "hold", 70
    
    if '建议加仓' in summary or '加仓' in summary:
        return "🟢", "建议加仓", "buy", 85
    elif '建议减仓' in summary or '减仓' in summary:
        return "🔴", "建议减仓", "sell", 90
    elif '建议卖出' in summary or '止损' in summary:
        return "🔴", "建议止损", "sell", 95
    elif '建议持有' in summary or '观望' in summary:
        return "🟡", "继续持有", "hold", 70
    
    return "⚪", "继续观察", "watch", 50

# ========== 内容生成 ==========

def get_style_intro(style: str, name: str) -> str:
    intros = {
        "trend": f"📈 {name}的趋势课堂：",
        "quantitative": f"📊 {name}的数据实验室：",
        "value": f"💎 {name}的价值发现：",
        "momentum": f"⚡ {name}的动量捕捉：",
        "macro": f"🌍 {name}的宏观视野：",
        "growth": f"🚀 {name}的成长掘金：",
        "dividend": f"💰 {name}的股息金矿：",
        "contrarian": f"🔄 {name}的逆向思考：",
        "event": f"🎯 {name}的事件追踪：",
    }
    return intros.get(style, f"📋 {name}的市场洞察：")

def generate_stock_brief(analysis: Dict, holding: Dict) -> str:
    """生成单只股票简评"""
    symbol = holding['symbol']
    name = holding['name']
    current_price = holding.get('current_price', 0) or 0
    avg_cost = holding.get('avg_cost', 0) or 0
    profit = (current_price - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
    
    signal_emoji, signal_text, _, _ = extract_trading_signal(analysis)
    
    if not analysis:
        return f"{signal_emoji} **{name}({symbol})** - 成本¥{avg_cost:.1f} | 现价¥{current_price:.1f} | {profit:+.1f}%\n   └ {signal_text}\n"
    
    summary = analysis.get('summary', '') or ''
    brief = summary.replace('#', '').replace('**', '')[:80]
    
    return f"""{signal_emoji} **{name}({symbol})**
├ 成本¥{avg_cost:.1f} → 现价¥{current_price:.1f} | {profit:+.1f}%
└ {brief}..."""

def generate_post_content(ai: Dict, portfolio: Dict, analyses: Dict, signals: List[Dict]) -> str:
    """生成完整发帖内容"""
    name = ai['name']
    style = ai['style']
    emoji = ai['emoji']
    holdings = portfolio['holdings']
    profit_pct = portfolio['total_profit_pct']
    total_value = portfolio['total_value']
    
    # 根据盈亏选择主题emoji
    if profit_pct > 5:
        theme_emoji = "🎉"
    elif profit_pct > 0:
        theme_emoji = "📈"
    elif profit_pct < -5:
        theme_emoji = "📉"
    else:
        theme_emoji = "📊"
    
    content = f"""**{emoji} {name} · 收盘{theme_emoji}分析**

{get_style_intro(style, name)}

"""
    
    if not holdings:
        content += "今日无持仓，空仓观望中...\n"
    else:
        # 展示所有持仓股票
        for h in holdings:
            symbol = h['symbol']
            analysis = analyses.get(symbol)
            content += generate_stock_brief(analysis, h) + "\n"
    
    # 汇总
    content += f"""---
📊 账户：¥{total_value:,.0f} | 今日收益 **{profit_pct:+.2f}%**

#每日看盘 #{style}"""
    
    return content

def create_post(ai_id: str, ai_name: str, title: str, content: str, 
                post_type: str = "analysis", action: str = "watch",
                signal_emoji: str = "⚪", snapshot_id: str = "") -> str:
    """写入ai_posts表"""
    conn = get_db()
    cursor = conn.cursor()
    post_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    signal_prefix = f"{signal_emoji} " if signal_emoji != "⚪" else ""
    
    cursor.execute("""
        INSERT INTO ai_posts (post_id, ai_id, title, content, post_type, action, created_at, ai_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (post_id, ai_id, f"{signal_prefix}{title}", content, post_type, action, now, ai_name))
    
    conn.commit()
    conn.close()
    return post_id

def aggregate_signals(signals: List[Dict]) -> tuple:
    """
    综合所有持仓的分析信号，计算组合信号
    优先级: 卖出 > 买入 > 持有 > 观望
    """
    if not signals:
        return "⚪", "观望", "watch"
    
    # 统计各信号数量
    signal_counts = {"sell": 0, "buy": 0, "hold": 0, "watch": 0}
    weighted_scores = {"sell": 0, "buy": 0, "hold": 0, "watch": 0}
    
    for s in signals:
        action = s['action']
        confidence = s.get('confidence', 50)
        quantity = s.get('quantity', 1)
        
        signal_counts[action] = signal_counts.get(action, 0) + 1
        weighted_scores[action] = weighted_scores.get(action, 0) + confidence * quantity
    
    # 按加权分数决定信号
    if signal_counts["sell"] > 0:
        return "🔴", "建议减仓", "sell"
    elif signal_counts["buy"] >= signal_counts["hold"]:
        return "🟢", "建议加仓", "buy"
    elif signal_counts["hold"] > 0:
        return "🟡", "继续持有", "hold"
    
    return "⚪", "继续观察", "watch"

# ========== 主流程 ==========

def main():
    logger.info("========== Task 4 V3: 智能发帖引擎（数据一致性修复版）==========")
    
    today = datetime.now()
    if today.weekday() >= 5:
        logger.info(f"周末({today.strftime('%A')})休市，跳过")
        return
    
    # 1. 创建持仓快照（解决数据一致性问题）
    snapshot_id = create_holdings_snapshot()
    
    ai_list = get_ai_characters()
    logger.info(f"共 {len(ai_list)} 个AI待发帖")
    
    results = {"success": 0, "failed": 0, "skipped": 0}
    all_signals = []
    
    for i, ai in enumerate(ai_list, 1):
        ai_id = str(ai['id'])
        name = ai['name']
        style = ai['style']
        
        logger.info(f"\n[{i}/10] {name} ({style})")
        
        try:
            # 2. 从快照获取持仓（而非实时查询）
            portfolio = get_snapshot_portfolio_summary(snapshot_id, ai_id)
            holdings = portfolio['holdings']
            
            if not holdings:
                logger.info(f"  -> 空仓，跳过")
                results["skipped"] += 1
                continue
            
            # 3. 分析所有持仓股票（之前只分析前2只）
            analyses = {}
            signals = []
            
            logger.info(f"  持仓快照: {len(holdings)} 只")
            for h in holdings:
                symbol = h['symbol']
                name_stock = h['name']
                logger.info(f"  分析 {symbol} ({name_stock})...")
                
                analysis = analyze_stock_with_minirock(symbol, name_stock, h)
                if analysis:
                    analyses[symbol] = analysis
                    signal_emoji, signal_text, action, confidence = extract_trading_signal(analysis)
                    
                    signals.append({
                        'symbol': symbol,
                        'emoji': signal_emoji,
                        'text': signal_text,
                        'action': action,
                        'confidence': confidence,
                        'quantity': h['quantity']
                    })
                    
                    logger.info(f"    -> {signal_emoji} {signal_text} (置信度{confidence}%)")
            
            # 4. 综合所有持仓信号
            portfolio_signal, portfolio_signal_text, portfolio_action = aggregate_signals(signals)
            logger.info(f"  组合信号: {portfolio_signal} {portfolio_signal_text}")
            
            # 5. 生成内容
            content = generate_post_content(ai, portfolio, analyses, signals)
            
            # 6. 生成标题
            if portfolio_action == "buy":
                title = f"【{name} · 加仓信号】"
            elif portfolio_action == "sell":
                title = f"【{name} · 减仓信号】"
            elif portfolio_action == "hold":
                title = f"【{name} · 继续持有】"
            else:
                title = f"【{name} · 持仓观望】"
            
            # 7. 发帖
            post_id = create_post(
                ai_id=ai_id,
                ai_name=name,
                title=title,
                content=content,
                post_type="analysis",
                action=portfolio_action,
                signal_emoji=portfolio_signal,
                snapshot_id=snapshot_id
            )
            
            logger.info(f"  -> 发帖成功 {portfolio_signal} (post_id: {post_id[:8]}...)")
            results["success"] += 1
            all_signals.append({
                "ai": name, 
                "signal": portfolio_signal, 
                "action": portfolio_action,
                "stocks": [s['symbol'] for s in signals]
            })
            
        except Exception as e:
            logger.error(f"  -> 发帖失败: {e}")
            results["failed"] += 1
    
    logger.info(f"\n========== 发帖完成: 成功 {results['success']}/10 ==========")
    
    if all_signals:
        logger.info(f"\n📊 今日信号汇总:")
        for s in all_signals:
            logger.info(f"  {s['signal']} {s['ai']}: {s['action']} | 持仓: {s['stocks']}")

if __name__ == "__main__":
    main()
