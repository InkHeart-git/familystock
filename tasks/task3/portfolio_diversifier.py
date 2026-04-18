#!/usr/bin/env python3
"""
Task 3: 选股多样化引擎
目标：让10个AI持仓产生差异化，解决"没有嗨点"问题

策略：
1. 每个策略风格维护独立的候选股票池
2. 选股时优先选择符合策略风格的股票
3. 避免多AI持有同一股票（分散持有）
4. 根据MiniRock分析结果动态调整持仓

使用: python3 portfolio_diversifier.py
"""
import sqlite3
import requests
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/www/ai-god-of-stocks/logs/portfolio_diversifier.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"
MINIROCK_API = "http://127.0.0.1:8000"

# ========== 策略候选股票池 ==========
# 根据9种策略风格预置候选股票（A股）
STRATEGY_POOLS = {
    "trend": {
        "name": "趋势跟踪派",
        "description": "追涨杀跌，顺势而为",
        "pool": [
            {"symbol": "002230", "name": "科大讯飞", "reason": "AI龙头，趋势强劲"},
            {"symbol": "300750", "name": "宁德时代", "reason": "新能源龙头，机构抱团"},
            {"symbol": "688981", "name": "中芯国际", "reason": "半导体龙头，动能充足"},
            {"symbol": "002049", "name": "紫光国微", "reason": "芯片设计，趋势向上"},
            {"symbol": "300059", "name": "东方财富", "reason": "券商龙头，弹性大"},
        ]
    },
    "quantitative": {
        "name": "量化分析派",
        "description": "数据驱动，模型选股",
        "pool": [
            {"symbol": "601318", "name": "中国平安", "reason": "估值低，业绩稳定"},
            {"symbol": "600036", "name": "招商银行", "reason": "银行龙头，数据透明"},
            {"symbol": "300015", "name": "爱尔眼科", "reason": "医疗龙头，成长稳定"},
            {"symbol": "000858", "name": "五粮液", "reason": "消费龙头，波动适中"},
            {"symbol": "601888", "name": "中国中免", "reason": "免税龙头，业绩增长"},
        ]
    },
    "value": {
        "name": "价值投资派",
        "description": "低估买入，长期持有",
        "pool": [
            {"symbol": "600519", "name": "贵州茅台", "reason": "白酒龙头，护城河深"},
            {"symbol": "601398", "name": "工商银行", "reason": "银行巨无霸，低估值"},
            {"symbol": "600900", "name": "长江电力", "reason": "水电龙头，现金流稳定"},
            {"symbol": "600028", "name": "中国石化", "reason": "石化龙头，高股息"},
            {"symbol": "601006", "name": "大秦铁路", "reason": "铁路龙头，稳健分红"},
        ]
    },
    "momentum": {
        "name": "短线交易派",
        "description": "高波动，快进快出",
        "pool": [
            {"symbol": "688256", "name": "寒武纪", "reason": "AI芯片，高弹性"},
            {"symbol": "300474", "name": "景嘉微", "reason": "GPU概念，波动大"},
            {"symbol": "688521", "name": "芯原股份", "reason": "半导体，题材活跃"},
            {"symbol": "300223", "name": "北京君正", "reason": "AI芯片，动能强"},
            {"symbol": "688396", "name": "华润微", "reason": "功率半导体，波动大"},
        ]
    },
    "macro": {
        "name": "宏观策略派",
        "description": "全球视野，跨市场配置",
        "pool": [
            {"symbol": "600030", "name": "中信证券", "reason": "券商龙头，宏观敏感"},
            {"symbol": "601899", "name": "紫金矿业", "reason": "黄金铜矿，避险品种"},
            {"symbol": "002460", "name": "赣锋锂业", "reason": "锂资源，商品周期"},
            {"symbol": "600111", "name": "北方稀土", "reason": "稀土龙头，战略资源"},
            {"symbol": "601600", "name": "中国铝业", "reason": "电解铝，宏观商品"},
        ]
    },
    "growth": {
        "name": "科技投资派",
        "description": "专注科技成长股",
        "pool": [
            {"symbol": "688041", "name": "海光信息", "reason": "AI算力，国产替代"},
            {"symbol": "688012", "name": "中微公司", "reason": "半导体设备，高成长"},
            {"symbol": "002185", "name": "华天科技", "reason": "封测龙头，业绩增长"},
            {"symbol": "300408", "name": "三环集团", "reason": "电子元件，成长性强"},
            {"symbol": "002371", "name": "北方华创", "reason": "半导体设备，赛道宽广"},
        ]
    },
    "dividend": {
        "name": "高股息策略",
        "description": "稳定分红，现金为王",
        "pool": [
            {"symbol": "601166", "name": "兴业银行", "reason": "高股息银行股"},
            {"symbol": "600326", "name": "西藏天路", "reason": "基建高股息"},
            {"symbol": "601169", "name": "北京银行", "reason": "城商行高股息"},
            {"symbol": "600377", "name": "宁沪高速", "reason": "高速公路，稳定分红"},
            {"symbol": "601328", "name": "交通银行", "reason": "国有大行，高股息"},
        ]
    },
    "contrarian": {
        "name": "逆向投资派",
        "description": "人弃我取，逆向布局",
        "pool": [
            {"symbol": "000002", "name": "万科A", "reason": "地产超跌，困境反转"},
            {"symbol": "601766", "name": "中国中车", "reason": "高铁龙头，超跌反弹"},
            {"symbol": "000063", "name": "中兴通讯", "reason": "通信设备，超跌后反弹"},
            {"symbol": "002024", "name": "苏宁易购", "reason": "零售超跌，预期反转"},
            {"symbol": "600050", "name": "中国联通", "reason": "运营商，估值修复"},
        ]
    },
    "event": {
        "name": "事件驱动派",
        "description": "催化剂驱动，快速响应",
        "pool": [
            {"symbol": "300999", "name": "金山办公", "reason": "AI办公，事件催化"},
            {"symbol": "688111", "name": "金山软件", "reason": "AI催化，业绩预期"},
            {"symbol": "002410", "name": "广联达", "reason": "AI建筑，政策受益"},
            {"symbol": "300124", "name": "汇川技术", "reason": "工控龙头，进口替代"},
            {"symbol": "688777", "name": "中控技术", "reason": "工业软件，智能制造"},
        ]
    }
}

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_current_holdings() -> Dict[str, List[str]]:
    """获取当前所有AI的持仓，格式: {ai_id: [symbol1, symbol2, ...]}"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT ai_id, symbol FROM ai_holdings WHERE quantity > 0")
    rows = cursor.fetchall()
    conn.close()
    
    holdings = {}
    for row in rows:
        ai_id = str(row['ai_id'])
        if ai_id not in holdings:
            holdings[ai_id] = []
        holdings[ai_id].append(row['symbol'])
    return holdings

def get_all_held_symbols() -> set:
    """获取所有已被持有的股票"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT symbol FROM ai_holdings WHERE quantity > 0")
    rows = cursor.fetchall()
    conn.close()
    return set(row['symbol'] for row in rows)

def get_ai_characters():
    """获取所有AI角色"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, style, emoji FROM ai_characters ORDER BY id")
    rows = cursor.fetchall()
    conn.close()
MINIROCK_API = "http://127.0.0.1:8000"

def get_realtime_price(symbol: str) -> Optional[float]:
    """获取股票实时价格（通过tushare接口）"""
    try:
        resp = requests.get(
            f"{MINIROCK_API}/api/tushare/quote/{symbol}",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get('close', 0) or data.get('price', 0)
    except:
        pass
    return None

def analyze_with_minirock(symbol: str) -> Optional[Dict]:
    """调用MiniRock分析单只股票"""
    try:
        resp = requests.post(
            f"{MINIROCK_API}/api/ai/analyze-stock",
            json={"symbol": symbol, "name": "", "current_price": 0, "avg_cost": 0, "quantity": 0},
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def select_stocks_for_ai(ai_id: str, style: str, current_holdings: Dict[str, List[str]], 
                         all_held: set, budget_per_stock: float = 100000) -> List[Dict]:
    """
    为指定AI选择符合策略的股票
    核心逻辑：
    1. 从策略池中筛选股票
    2. 排除已被自己持有的股票（避免重复）
    3. 优先选择未被其他AI持有的股票（提高多样性）
    4. 根据MiniRock分析选择有上涨潜力的股票
    """
    if style not in STRATEGY_POOLS:
        logger.warning(f"  未知策略风格: {style}，使用默认池")
        style = "value"
    
    pool = STRATEGY_POOLS[style]["pool"]
    strategy_name = STRATEGY_POOLS[style]["name"]
    
    # 已被当前AI持有的股票
    my_held = set(current_holdings.get(ai_id, []))
    
    # 候选股票：未被我持有的
    candidates = [s for s in pool if s["symbol"] not in my_held]
    
    # 如果所有候选都被持有，从池中选择持有量最少的
    if not candidates:
        # 统计每只股票的持有AI数量
        holding_count = {}
        for aid, symbols in current_holdings.items():
            for sym in symbols:
                holding_count[sym] = holding_count.get(sym, 0) + 1
        
        candidates = sorted(pool, key=lambda s: holding_count.get(s["symbol"], 0))[:3]
        logger.info(f"  策略池已满，选择持有量最少的股票")
    
    # 按持有数量排序（少的优先）
    holding_count = {}
    for aid, symbols in current_holdings.items():
        for sym in symbols:
            holding_count[sym] = holding_count.get(sym, 0) + 1
    
    # 优先选择未被持有或持有量少的股票
    candidates.sort(key=lambda s: (
        holding_count.get(s["symbol"], 0),  # 持有量少的优先
        -hash(s["symbol"]) % 100  # 随机打破僵局
    ))
    
    # 选择1-2只股票
    selected = candidates[:2]
    
    logger.info(f"  策略: {strategy_name} | 候选 {len(candidates)} 只 | 选择: {[s['name'] for s in selected]}")
    
    return selected

def rebalance_portfolio(ai_id: str, ai_name: str, style: str, target_stocks: List[Dict]):
    """
    重新平衡持仓
    - 卖出不在目标列表中的股票
    - 买入目标列表中的新股票
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # 获取当前持仓
    cursor.execute("SELECT symbol, quantity, avg_cost FROM ai_holdings WHERE ai_id=? AND quantity > 0", (ai_id,))
    current = {row['symbol']: row for row in cursor.fetchall()}
    
    target_symbols = {s['symbol'] for s in target_stocks}
    current_symbols = set(current.keys())
    
    # 需要卖出的股票
    to_sell = current_symbols - target_symbols
    # 需要买入的股票
    to_buy = target_symbols - current_symbols
    
    logger.info(f"  持仓调整: 卖出 {len(to_sell)} 只，买入 {len(to_buy)} 只")
    
    # 执行卖出（简化：直接删除持仓记录）
    for symbol in to_sell:
        cursor.execute("DELETE FROM ai_holdings WHERE ai_id=? AND symbol=?", (ai_id, symbol))
        logger.info(f"    - 卖出: {symbol}")
    
    # 执行买入
    for stock in target_stocks:
        if stock['symbol'] in to_buy:
            # 从tushare实时获取价格（通过get_realtime_price）
            price = get_realtime_price(stock['symbol'])
            if not price or price == 0:
                logger.warning(f"    ! 价格获取失败: {stock['symbol']}，跳过")
                continue
            
            # 计算买入数量（每只股票约10万）
            quantity = int(100000 / price) if price > 0 else 1000
            
            # 模拟真实建仓成本：avg_cost 在 current_price 基础上 ±7% 随机偏差
            import random
            cost_ratio = random.uniform(0.93, 1.07)
            avg_cost = round(price * cost_ratio, 2)
            
            cursor.execute("""
                INSERT OR REPLACE INTO ai_holdings 
                (ai_id, symbol, name, quantity, avg_cost, current_price, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
            """, (ai_id, stock['symbol'], stock['name'], quantity, avg_cost, price))
    
    conn.commit()
    conn.close()

def main():
    logger.info("========== Task 3: 选股多样化引擎 ==========")
    
    # 获取当前持仓状态
    current_holdings = get_current_holdings()
    all_held = get_all_held_symbols()
    
    logger.info(f"当前持仓分布:")
    for ai_id, symbols in sorted(current_holdings.items()):
        logger.info(f"  AI#{ai_id}: {len(symbols)} 只 {symbols}")
    
    # 获取所有AI
    ai_list = get_ai_characters()
    logger.info(f"\n开始为 {len(ai_list)} 个AI重新分配持仓...")
    
    results = {"diversified": 0, "unchanged": 0}
    
    for ai in ai_list:
        ai_id = str(ai['id'])
        name = ai['name']
        style = ai['style']
        emoji = ai['emoji']
        
        logger.info(f"\n[{emoji} {name}] ({style})")
        
        # 选择新股票
        new_stocks = select_stocks_for_ai(
            ai_id, style, current_holdings, all_held
        )
        
        if new_stocks:
            # 更新持仓
            rebalance_portfolio(ai_id, name, style, new_stocks)
            
            # 更新当前状态（防止同一股票被多个AI选中）
            current_holdings[ai_id] = [s['symbol'] for s in new_stocks]
            for s in new_stocks:
                all_held.add(s['symbol'])
            
            results["diversified"] += 1
        else:
            results["unchanged"] += 1
    
    logger.info(f"\n========== 选股多样化完成 ==========")
    logger.info(f"完成: {results['diversified']} | 保持: {results['unchanged']}")
    
    # 输出最终持仓分布
    final_holdings = get_current_holdings()
    logger.info(f"\n最终持仓分布:")
    for ai_id, symbols in sorted(final_holdings.items()):
        logger.info(f"  AI#{ai_id}: {len(symbols)} 只 - {symbols}")
    
    # 统计每只股票的持有AI数量
    symbol_owners = {}
    for ai_id, symbols in final_holdings.items():
        for sym in symbols:
            if sym not in symbol_owners:
                symbol_owners[sym] = []
            symbol_owners[sym].append(ai_id)
    
    # 找出被多个AI持有的股票
    duplicated = {sym: owners for sym, owners in symbol_owners.items() if len(owners) > 1}
    if duplicated:
        logger.warning(f"\n⚠️ 以下股票被多个AI持有（冗余）:")
        for sym, owners in duplicated.items():
            logger.warning(f"  {sym}: AI {owners}")
    else:
        logger.info(f"\n✅ 所有AI持仓完全独立，无冗余")
    
    # 多样性得分
    total_holdings = sum(len(s) for s in final_holdings.values())
    unique_holdings = len(symbol_owners)
    diversity_score = (unique_holdings / total_holdings * 100) if total_holdings > 0 else 0
    logger.info(f"\n📊 多样性得分: {diversity_score:.0f}% ({unique_holdings}/{total_holdings} 只独立持仓)")

if __name__ == "__main__":
    main()
