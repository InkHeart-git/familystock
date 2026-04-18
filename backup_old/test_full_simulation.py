#!/usr/bin/env python3
"""
AI股神争霸赛 - 全流程测试脚本 (10个AI)
风云五虎（100万）+ 灵动五小（10万）
使用周四(4月3日)收盘价作为买入价，模拟完整交易日
"""

import asyncio
import sys
import os
import random
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime, time
from core.characters import get_all_characters, get_character, get_characters_by_group
from core.bbs import BBSSystem, PostType

# 模拟周四(4月3日)的市场数据
MOCK_MARKET_DATA = {
    "trade_date": "2025-04-03",
    "market_summary": "周四市场震荡整理，上证指数微涨0.12%，深成指涨0.35%。成交额约8500亿元，北向资金净流入23亿元。板块方面，通信、电子、计算机领涨，煤炭、钢铁、房地产跌幅居前。",
    "hot_sectors": ["通信", "电子", "计算机", "新能源"],
    "market_sentiment": "neutral",
}

# 模拟股票池 - 周四收盘价
MOCK_STOCKS = [
    {"symbol": "000063.SZ", "name": "中兴通讯", "close": 28.50, "pct_chg": 5.23, "industry": "通信"},
    {"symbol": "002475.SZ", "name": "立讯精密", "close": 32.80, "pct_chg": 4.15, "industry": "电子"},
    {"symbol": "300750.SZ", "name": "宁德时代", "close": 198.60, "pct_chg": 3.82, "industry": "新能源"},
    {"symbol": "600519.SH", "name": "贵州茅台", "close": 1658.00, "pct_chg": 1.25, "industry": "白酒"},
    {"symbol": "000858.SZ", "name": "五粮液", "close": 142.30, "pct_chg": 0.98, "industry": "白酒"},
    {"symbol": "601088.SH", "name": "中国神华", "close": 28.20, "pct_chg": -2.15, "industry": "煤炭"},
    {"symbol": "000001.SZ", "name": "平安银行", "close": 10.85, "pct_chg": -0.82, "industry": "银行"},
    {"symbol": "002594.SZ", "name": "比亚迪", "close": 218.50, "pct_chg": 2.35, "industry": "汽车"},
    {"symbol": "300059.SZ", "name": "东方财富", "close": 18.60, "pct_chg": 3.15, "industry": "金融科技"},
    {"symbol": "600036.SH", "name": "招商银行", "close": 35.20, "pct_chg": 0.55, "industry": "银行"},
    {"symbol": "000725.SZ", "name": "京东方A", "close": 4.25, "pct_chg": 2.85, "industry": "电子"},
    {"symbol": "300124.SZ", "name": "汇川技术", "close": 58.30, "pct_chg": 1.95, "industry": "工业自动化"},
]

# 每个AI的选股偏好
AI_PREFERENCES = {
    # 风云五虎（大资金组）
    "trend_chaser": ["中兴通讯", "立讯精密", "宁德时代"],
    "quant_queen": ["中兴通讯", "比亚迪", "立讯精密"],
    "value_veteran": ["贵州茅台", "五粮液", "中国神华", "招商银行"],
    "scalper_fairy": ["中兴通讯", "立讯精密", "京东方A"],
    "macro_master": ["宁德时代", "比亚迪", "中兴通讯", "东方财富"],
    # 灵动五小（小投入组）
    "tech_whiz": ["立讯精密", "京东方A", "汇川技术", "宁德时代"],
    "dividend_hunter": ["贵州茅台", "五粮液", "招商银行", "平安银行"],
    "turnaround_pro": ["京东方A", "中国神华", "平安银行"],
    "momentum_kid": ["中兴通讯", "立讯精密", "东方财富"],
    "event_driven": ["比亚迪", "宁德时代", "东方财富", "汇川技术"],
}

async def run_full_simulation():
    """运行全流程模拟"""
    print("=" * 80)
    print("🎮 AI股神争霸赛 - 全流程测试（10个AI）")
    print(f"📅 模拟日期: 周四 (2025-04-03)")
    print("=" * 80)
    
    # 初始化系统
    bbs = BBSSystem()
    characters = get_all_characters()
    
    # 分组
    big_funds = get_characters_by_group("风云五虎")
    small_funds = get_characters_by_group("灵动五小")
    
    print(f"\n📊 参赛队伍:")
    print(f"   🐯 风云五虎（大资金组）: 5个AI，初始资金各100万")
    for char_id, char in big_funds.items():
        print(f"      {char.avatar} {char.name}")
    print(f"\n   🐹 灵动五小（小投入组）: 5个AI，初始资金各10万")
    for char_id, char in small_funds.items():
        print(f"      {char.avatar} {char.name}")
    
    print(f"\n📊 市场概况:")
    print(f"   {MOCK_MARKET_DATA['market_summary'][:80]}...")
    print(f"   热点板块: {', '.join(MOCK_MARKET_DATA['hot_sectors'])}")
    
    # 每个AI的持仓和资金
    portfolios = {}
    for char_id, character in characters.items():
        portfolios[char_id] = {
            "cash": character.initial_capital,
            "holdings": [],
            "total_value": character.initial_capital,
            "trades": [],
            "group": character.group,
            "initial_capital": character.initial_capital
        }
    
    # ========== 1. 开盘前分析 ==========
    print("\n" + "=" * 80)
    print("🌅 阶段一: 开盘前分析 (9:00)")
    print("=" * 80)
    
    # 风云五虎
    print("\n🐯 风云五虎（大资金组）观点:")
    for char_id, character in big_funds.items():
        print(f"\n   {character.avatar} {character.name} ({character.style})")
        post = await bbs.on_market_open(char_id, MOCK_MARKET_DATA["market_summary"])
        if post:
            bbs.save_post(post)
            print(f"   📝 {post.content[:100]}...")
        await asyncio.sleep(0.2)
    
    # 灵动五小
    print("\n🐹 灵动五小（小投入组）观点:")
    for char_id, character in small_funds.items():
        print(f"\n   {character.avatar} {character.name} ({character.style})")
        post = await bbs.on_market_open(char_id, MOCK_MARKET_DATA["market_summary"])
        if post:
            bbs.save_post(post)
            print(f"   📝 {post.content[:100]}...")
        await asyncio.sleep(0.2)
    
    # ========== 2. 交易决策 ==========
    print("\n" + "=" * 80)
    print("📈 阶段二: 交易决策 (9:30-11:30, 13:00-15:00)")
    print("=" * 80)
    
    # 风云五虎交易
    print("\n🐯 风云五虎（大资金组）交易:")
    for char_id, character in big_funds.items():
        await execute_trades(char_id, character, portfolios, bbs, "大资金")
        await asyncio.sleep(0.2)
    
    # 灵动五小交易
    print("\n🐹 灵动五小（小投入组）交易:")
    for char_id, character in small_funds.items():
        await execute_trades(char_id, character, portfolios, bbs, "小投入")
        await asyncio.sleep(0.2)
    
    # ========== 3. 收盘总结 ==========
    print("\n" + "=" * 80)
    print("🌙 阶段三: 收盘总结 (15:05)")
    print("=" * 80)
    
    # 风云五虎收盘
    print("\n🐯 风云五虎（大资金组）收盘:")
    for char_id, character in big_funds.items():
        await closing_summary(char_id, character, portfolios, bbs)
        await asyncio.sleep(0.2)
    
    # 灵动五小收盘
    print("\n🐹 灵动五小（小投入组）收盘:")
    for char_id, character in small_funds.items():
        await closing_summary(char_id, character, portfolios, bbs)
        await asyncio.sleep(0.2)
    
    # ========== 4. 排行榜 ==========
    print("\n" + "=" * 80)
    print("🏆 今日收益排行榜")
    print("=" * 80)
    
    # 风云五虎排名
    print("\n🐯 风云五虎（大资金组）排名:")
    show_rankings(big_funds, portfolios)
    
    # 灵动五小排名
    print("\n🐹 灵动五小（小投入组）排名:")
    show_rankings(small_funds, portfolios)
    
    # 总排名
    print("\n📊 总排名（10个AI）:")
    show_rankings(characters, portfolios, show_group=True)
    
    # ========== 5. 交易统计 ==========
    print("\n" + "=" * 80)
    print("📊 交易统计")
    print("=" * 80)
    
    show_statistics(big_funds, portfolios, "风云五虎")
    show_statistics(small_funds, portfolios, "灵动五小")
    
    print("\n" + "=" * 80)
    print("✅ 全流程测试完成!")
    print("=" * 80)

async def execute_trades(char_id, character, portfolios, bbs, group_type):
    """执行交易"""
    portfolio = portfolios[char_id]
    print(f"\n   {character.avatar} {character.name} ({group_type}):")
    print(f"   💰 初始资金: ¥{portfolio['initial_capital']:,.2f}")
    print(f"   📊 当前持仓: {len(portfolio['holdings'])} 只股票")
    
    # 根据AI偏好选股
    preferred_stocks = AI_PREFERENCES.get(char_id, [])
    available_stocks = [s for s in MOCK_STOCKS if s['name'] in preferred_stocks]
    
    if not available_stocks:
        available_stocks = MOCK_STOCKS[:3]
    
    # 随机选1-2只买入
    num_to_buy = random.randint(1, 2)
    selected = random.sample(available_stocks, min(num_to_buy, len(available_stocks)))
    
    print(f"   🔍 选股: {len(selected)} 只")
    for s in selected:
        print(f"      - {s['name']} ({s['symbol']}): ¥{s['close']:.2f}")
    
    # 执行买入
    for stock in selected:
        # 根据组别调整仓位比例
        if group_type == "大资金":
            position_pct = random.uniform(0.10, 0.20)  # 大资金10-20%
        else:
            position_pct = random.uniform(0.30, 0.50)  # 小资金30-50%
        
        amount = portfolio['cash'] * position_pct
        quantity = int(amount / stock['close'] / 100) * 100
        
        if quantity < 100:
            continue
        
        actual_amount = quantity * stock['close']
        
        if actual_amount > portfolio['cash']:
            continue
        
        # 执行交易
        portfolio['cash'] -= actual_amount
        holding = {
            "symbol": stock['symbol'],
            "name": stock['name'],
            "quantity": quantity,
            "avg_cost": stock['close'],
            "current_price": stock['close'],
            "industry": stock['industry']
        }
        portfolio['holdings'].append(holding)
        
        trade = {
            "action": "买入",
            "symbol": stock['symbol'],
            "name": stock['name'],
            "price": stock['close'],
            "quantity": quantity,
            "amount": actual_amount,
            "reason": f"基于{character.style}策略，看好{stock['industry']}板块"
        }
        portfolio['trades'].append(trade)
        
        print(f"   ✅ 买入 {stock['name']}: {quantity}股 @ ¥{stock['close']:.2f} = ¥{actual_amount:,.2f}")
        
        # 生成交易帖子
        await create_trade_post(bbs, char_id, trade, character)
    
    # 更新总资产
    holdings_value = sum(h['quantity'] * h['current_price'] for h in portfolio['holdings'])
    portfolio['total_value'] = portfolio['cash'] + holdings_value
    
    print(f"   💵 现金: ¥{portfolio['cash']:,.2f} | 持仓: ¥{holdings_value:,.2f} | 总: ¥{portfolio['total_value']:,.2f}")

async def closing_summary(char_id, character, portfolios, bbs):
    """收盘总结"""
    portfolio = portfolios[char_id]
    
    # 模拟周五涨跌
    for holding in portfolio['holdings']:
        change_pct = random.uniform(-0.03, 0.05)
        holding['current_price'] = holding['avg_cost'] * (1 + change_pct)
    
    holdings_value = sum(h['quantity'] * h['current_price'] for h in portfolio['holdings'])
    total_value = portfolio['cash'] + holdings_value
    
    today_pnl = total_value - portfolio['initial_capital']
    today_pnl_pct = (today_pnl / portfolio['initial_capital']) * 100
    
    print(f"\n   {character.avatar} {character.name}")
    print(f"   💰 总资产: ¥{total_value:,.2f} | 盈亏: {today_pnl_pct:+.2f}% (¥{today_pnl:+,.0f})")
    
    if portfolio['holdings']:
        print(f"   📊 持仓:")
        for h in portfolio['holdings']:
            pnl_pct = (h['current_price'] / h['avg_cost'] - 1) * 100
            print(f"      - {h['name']}: {h['quantity']}股 ({pnl_pct:+.2f}%)")
    
    post = await bbs.on_market_close(char_id, today_pnl, today_pnl_pct)
    if post:
        bbs.save_post(post)

def show_rankings(characters, portfolios, show_group=False):
    """显示排名"""
    rankings = []
    for char_id, character in characters.items():
        portfolio = portfolios[char_id]
        holdings_value = sum(h['quantity'] * h['current_price'] for h in portfolio['holdings'])
        total_value = portfolio['cash'] + holdings_value
        today_pnl = total_value - portfolio['initial_capital']
        today_pnl_pct = (today_pnl / portfolio['initial_capital']) * 100
        group = portfolio['group'] if show_group else ""
        rankings.append((char_id, character, today_pnl, today_pnl_pct, total_value, group))
    
    rankings.sort(key=lambda x: x[3], reverse=True)
    
    for i, (char_id, char, pnl, pct, total, group) in enumerate(rankings, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        group_tag = f"[{group}]" if show_group else ""
        print(f"   {medal} 第{i}名: {char.avatar} {char.name:12s} {group_tag:12s} 收益: {pct:+6.2f}% (¥{pnl:+8,.0f}) 资产: ¥{total:,.0f}")

def show_statistics(characters, portfolios, group_name):
    """显示统计"""
    print(f"\n   {group_name}:")
    total_trades = sum(len(portfolios[char_id]['trades']) for char_id in characters.keys())
    total_buy = sum(
        sum(t['amount'] for t in portfolios[char_id]['trades'])
        for char_id in characters.keys()
    )
    
    print(f"      交易笔数: {total_trades}")
    print(f"      买入金额: ¥{total_buy:,.2f}")
    
    # 持仓分布
    all_holdings = {}
    for char_id in characters.keys():
        for h in portfolios[char_id]['holdings']:
            name = h['name']
            if name not in all_holdings:
                all_holdings[name] = 0
            all_holdings[name] += 1
    
    if all_holdings:
        print(f"      热门持仓: ", end="")
        top_holdings = sorted(all_holdings.items(), key=lambda x: x[1], reverse=True)[:3]
        print(", ".join([f"{name}({count}人)" for name, count in top_holdings]))

async def create_trade_post(bbs, char_id, trade, character):
    """创建交易帖子"""
    from core.bbs import Post, PostType
    from datetime import datetime
    import uuid
    
    content = f"""【交易动态】

{character.avatar} **{character.name}** {trade['action']}操作

**股票**: {trade['name']} ({trade['symbol']})
**数量**: {trade['quantity']} 股
**价格**: ¥{trade['price']:.2f}
**金额**: ¥{trade['amount']:,.2f}

**交易理由**:
{trade['reason']}

---
*{character.style}*
"""
    
    post = Post(
        id=str(uuid.uuid4()),
        ai_id=char_id,
        ai_name=character.name,
        ai_avatar=character.avatar,
        post_type=PostType.TRADE,
        content=content,
        timestamp=datetime.now(),
        likes=random.randint(0, 5),
        replies=random.randint(0, 3)
    )
    
    post.trade_info = {
        'symbol': trade['symbol'],
        'stock_name': trade['name'],
        'price': trade['price'],
        'quantity': trade['quantity'],
        'action': trade['action'],
        'pnl': 0
    }
    
    bbs.posts.append(post)
    bbs.save_post(post)

if __name__ == "__main__":
    asyncio.run(run_full_simulation())
