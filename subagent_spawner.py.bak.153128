#!/usr/bin/env python3
"""
AI股神争霸 - 子代理调度器 v3.0
关键改进：发帖内容必须与持仓一致
"""
import asyncio
import sys
import sqlite3
import aiohttp
import uuid
from datetime import datetime

# 持仓校验配置
sys.path.insert(0, '/var/www/ai-god-of-stocks')
try:
    from config.ai_group_config import get_initial_capital, get_max_position_pct, validate_holding
    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False

# AI大脑模块
from engine.brains import SimpleBrain, ComplexBrain, BrainType, AIDecision, get_ai_decision
from engine.signal import get_stock_signals

# 交易规则引擎
try:
    from engine.trading_rules import TradingRulesEngine, validate_and_execute_trade
    TRADING_RULES_AVAILABLE = True
except ImportError:
    TRADING_RULES_AVAILABLE = False
    print("[WARNING] 交易规则引擎未加载，交易不受限制")

# DeepSeek API配置
DEEPSEEK_API_KEY = "sk-7d9d3bc3ca754c368d52d57c20d3ad98"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 全部10个AI角色配置
AI_CHARACTERS = {
    'trend_chaser': {
        'name': 'Tyler（泰勒）', 'style': '趋势跟踪',
        'personality': '年轻激进，追逐热点，止损果断',
        'capital': 100,
        'system_prompt': '''你是Tyler（泰勒），一位激进的趋势跟踪型交易员。

你的特点：
- 喜欢追涨杀跌，追逐市场热点
- 仓位较高，敢于梭哈
- 止损坚决，5%止损线
- 持仓1-3天，不恋战
- 年轻热血，说话直接，常用"冲鸭"、"YYDS"

你是有真正大脑的AI，你的分析和决策都经过DeepSeek LLM深度推理。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'quant_queen': {
        'name': '林数理', 'style': '量化分析',
        'personality': '理性冷静，用数据说话',
        'capital': 100,
        'system_prompt': '''你是林数理，一位理性冷静的量化分析师。

你的特点：
- 一切用数据说话，不凭感觉
- 喜欢量化模型和指标分析（RSI、MACD、布林带等）
- 仓位控制严格，不追高
- 持仓5天左右
- 说话严谨，数据支撑

你是有真正大脑的AI，你的分析基于量化模型的深度计算。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'value_veteran': {
        'name': '方守成', 'style': '价值投资',
        'personality': '老练稳重，看重基本面',
        'capital': 100,
        'system_prompt': '''你是方守成，一位老练的价值投资者。

你的特点：
- 看重公司基本面和现金流
- 喜欢低估值的蓝筹股
- 持仓时间长，不理会短期波动
- 仓位一般不超过70%
- 说话稳重，爱翻财报

你是有真正大脑的AI，你的判断基于对公司基本面的深度分析。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'scalper_fairy': {
        'name': 'Ryan（瑞恩）', 'style': '短线交易',
        'personality': '快进快出，盯盘敏锐',
        'capital': 100,
        'system_prompt': '''你是Ryan（瑞恩），一位快进快出的短线交易员。

你的特点：
- 持仓时间极短，当天进出
- 追热点板块的龙头股
- 严格止损，3%必走
- 仓位灵活，看准就重仓
- 说话直接，喜欢"冲"

你是有真正大脑的AI，你的每笔交易都经过深度分析。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'macro_master': {
        'name': 'David Chen（陈大卫）', 'style': '宏观策略',
        'personality': '关注政策，自上而下',
        'capital': 100,
        'system_prompt': '''你是David Chen（陈大卫），一位关注宏观策略的分析师。

你的特点：
- 关注政策动向和全球市场
- 自上而下分析
- 板块轮动判断准确
- 持仓灵活，适时避险
- 说话有大局观

你是有真正大脑的AI，你的分析基于对宏观面的深度思考。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'tech_whiz': {
        'name': '韩科捷', 'style': '科技投资',
        'personality': '专注科技，追踪创新',
        'capital': 10,
        'system_prompt': '''你是韩科捷，一位专注科技领域的投资者。

你的特点：
- 偏好科技股和成长股
- 关注AI、半导体、新能源等赛道
- 会分析技术壁垒和成长性
- 持仓以小资金组10万为限
- 说话有技术感

你是有真正大脑的AI，你的分析基于对科技行业的深度理解。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'dividend_hunter': {
        'name': 'James Wong（黄詹姆斯）', 'style': '高股息策略',
        'personality': '稳健高分红',
        'capital': 10,
        'system_prompt': '''你是James Wong（黄詹姆斯），一位稳健的高股息投资者。

你的特点：
- 偏好高分红的蓝筹股
- 稳健第一，不追求暴利
- 分红率>5%是硬指标
- 持仓时间较长
- 说话稳健，爱说"现金流"

你是有真正大脑的AI，你的分析基于对公司分红能力的深度评估。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'turnaround_pro': {
        'name': '周逆行', 'style': '逆向投资',
        'personality': '人弃我取，逆向思维',
        'capital': 10,
        'system_prompt': '''你是周逆行，一位擅长逆向投资的交易员。

你的特点：
- 喜欢买被人抛弃的股票
- 关注困境反转的机会
- 独立思考，不随大流
- 会抄底，但也会止损
- 说话有逆向思维

你是有真正大脑的AI，你的分析基于对逆向投资的深度理解。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'momentum_kid': {
        'name': 'Mike（迈克）', 'style': '动量投资',
        'personality': '顺势而为，追涨杀跌',
        'capital': 10,
        'system_prompt': '''你是Mike（迈克），一位动量交易员。

你的特点：
- 追涨杀跌，顺势而为
- 关注动量因子
- 趋势形成后介入
- 趋势破坏后止损
- 说话直接，"趋势为王"

你是有真正大脑的AI，你的分析基于对市场动量的深度理解。
你只分析你持有的股票，不持有的一概不分析。'''
    },
    'event_driven': {
        'name': '沈闻', 'style': '事件驱动',
        'personality': '消息敏感',
        'capital': 10,
        'system_prompt': '''你是沈闻，一位事件驱动型交易员。

你的特点：
- 关注公告、消息、政策等事件
- 分析事件对股价的影响
- 事件驱动型交易
- 持仓时间取决于事件周期
- 说话关注"消息面"

你是有真正大脑的AI，你的分析基于对事件影响的深度评估。
你只分析你持有的股票，不持有的一概不分析。'''
    }
}

# AI ID映射（数字ID用于BBS数据库）
AI_NUMERIC_ID = {
    'trend_chaser': '1', 'quant_queen': '2', 'value_veteran': '3',
    'scalper_fairy': '4', 'macro_master': '5', 'tech_whiz': '6',
    'dividend_hunter': '7', 'turnaround_pro': '8', 'momentum_kid': '9', 'event_driven': '10'
}
ID_TO_KEY = {'1': 'trend_chaser', '2': 'quant_queen', '3': 'value_veteran', '4': 'scalper_fairy', '5': 'macro_master',
             '6': 'tech_whiz', '7': 'dividend_hunter', '8': 'turnaround_pro', '9': 'momentum_kid', '10': 'event_driven'}

def get_ai_holdings():
    """直接从SQLite数据库获取所有AI的持仓（最新数据，不依赖API缓存）"""
    import sqlite3
    from pathlib import Path
    
    holdings = {}
    try:
        # 直接读取SQLite数据库
        db_path = '/var/www/ai-god-of-stocks/data/ai_god.db'
        if not Path(db_path).exists():
            print(f"数据库不存在: {db_path}")
            return holdings
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有持仓
        cursor.execute("""
            SELECT ai_id, symbol, name, quantity, avg_cost, current_price 
            FROM ai_holdings 
            ORDER BY ai_id, symbol
        """)
        
        for row in cursor.fetchall():
            ai_id, symbol, name, qty, buy_price, current_price = row
            ai_key = ID_TO_KEY.get(str(ai_id), str(ai_id))
            
            if ai_key not in holdings:
                holdings[ai_key] = []
            
            holdings[ai_key].append({
                'symbol': symbol,
                'name': name,
                'qty': qty,
                'buy_price': buy_price,
                'current_price': current_price
            })
        
        conn.close()
        
    except Exception as e:
        print(f"获取持仓失败: {e}")
    
    return holdings

async def get_market_data() -> dict:
    """获取市场数据"""
    db_path = '/var/www/familystock/api/data/family_stock.db'
    indices = []
    
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute('SELECT ts_code, name, close, pct_chg FROM index_quotes ORDER BY trade_date DESC LIMIT 6')
        for row in cur.fetchall():
            indices.append(f"{row[1]}: {row[2]} ({row[3]:+.2f}%)")
        conn.close()
    except Exception as e:
        indices.append(f"获取失败: {e}")
    
    return {'indices': indices}

async def call_deepseek(system_prompt: str, user_prompt: str) -> str:
    """调用DeepSeek API"""
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "max_tokens": 400,
        "temperature": 0.7
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL, headers=headers, json=payload,
                timeout=aiohttp.ClientTimeout(total=25)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data['choices'][0]['message']['content']
    except:
        pass
    return None

def save_to_bbs(ai_id: str, content: str):
    """保存帖子到BBS数据库（带持仓验证）"""
    import time
    import sqlite3
    from pathlib import Path
    
    # ====== 持仓一致性验证 ======
    # 发帖前必须确认内容与持仓一致
    holdings = get_ai_holdings()
    ai_holdings = holdings.get(ai_id, [])
    holding_names = [h['name'] for h in ai_holdings]
    holding_symbols = [h['symbol'] for h in ai_holdings]
    
    # 检查帖子是否提到了非持仓股票
    stocks_mentioned = []
    if '比亚迪' in content and '比亚迪' not in holding_names:
        stocks_mentioned.append('比亚迪')
    if '中国中免' in content and '中国中免' not in holding_names and '中免' not in str(holding_names):
        stocks_mentioned.append('中国中免')
    if '阿里巴巴' in content and '阿里巴巴' not in holding_names:
        stocks_mentioned.append('阿里巴巴')
    if '腾讯控股' in content and '腾讯' not in str(holding_names):
        stocks_mentioned.append('腾讯控股')
    
    if stocks_mentioned and not ai_holdings:
        print(f"  ⚠️ 持仓为空但帖子提到: {stocks_mentioned}，拒绝发帖！")
        return False
    
    if stocks_mentioned:
        print(f"  ⚠️ 持仓{holding_names}与帖子内容不一致，拒绝发帖！")
        return False
    # ====== 持仓验证结束 ======
    
    time.sleep(0.5)
    
    bbs_db = '/var/www/ai-god-of-stocks/data/ai_god.db'
    
    if ai_id not in AI_NUMERIC_ID:
        return False
    
    numeric_id = AI_NUMERIC_ID[ai_id]
    char = AI_CHARACTERS[ai_id]
    
    try:
        conn = sqlite3.connect(bbs_db, timeout=10)
        cur = conn.cursor()
        
        post_id = str(uuid.uuid4())
        created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cur.execute("""
            INSERT INTO ai_posts (post_id, ai_id, title, content, post_type, created_at, ai_name, likes, replies, views)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0)
        """, (post_id, numeric_id, f"【{char['name']} · 持仓分析】", content, 'analysis', created_at, char['name']))
        
        conn.commit()
        conn.close()
        print(f"  💾 已保存到BBS (post_id: {post_id[:8]}...)")
        return True
    except Exception as e:
        print(f"  保存BBS失败: {e}")
        return False

async def analyze_for_ai(ai_id: str) -> dict:
    """为单个AI生成分析 - 基于持仓"""
    if ai_id not in AI_CHARACTERS:
        return None
    
    char = AI_CHARACTERS[ai_id]
    result = {'ai_id': ai_id, 'name': char['name'], 'style': char['style'], 'success': False}
    
    # 1. 获取持仓数据
    holdings = get_ai_holdings()
    ai_holdings = holdings.get(ai_id, [])
    
    # 2. 获取市场数据
    market_data = await get_market_data()
    indices_str = '\n'.join(market_data['indices']) or '暂无数据'
    
    # 3. 构建持仓信息
    holdings_str = ""
    if ai_holdings:
        holdings_str = "我的持仓：\n"
        for h in ai_holdings:
            holdings_str += f"- {h['name']}({h['symbol']}): {h['qty']}股 @ {h['current_price']}元\n"
    else:
        holdings_str = "（当前无持仓，需要寻找新标的）"
    
    # 如果无持仓，设置标志
    is_empty_holdings = len(ai_holdings) == 0
    
    # 5. 调用AI大脑获取交易决策（基于信号）
    ai_decisions = []
    brain_type = BrainType.COMPLEX if char['capital'] >= 100 else BrainType.SIMPLE
    
    if ai_holdings:
        # 有持仓时，分析持仓决策
        ai_decisions = get_ai_decision(
            brain_type=brain_type,
            ai_id=ai_id,
            ai_name=char['name'],
            style=char['style'],
            capital=char['capital'] * 10000,  # 转换为元
            holdings=ai_holdings,
            cash=char['capital'] * 10000 - sum(h['qty'] * h['current_price'] for h in ai_holdings)
        )
        
        if ai_decisions:
            print(f"  🧠 AI大脑决策: {[d.action.value for d in ai_decisions]}")
            for d in ai_decisions:
                print(f"     {d.stock_name}: {d.reason}")
    
    # 4. 判断当前交易阶段
    now = datetime.now()
    time_str = now.strftime("%Y年%m月%d日 %H:%M")
    hour = now.hour
    if 9 <= hour < 11.5:
        trade_phase = "上午盘中"
    elif 11.5 <= hour < 13:
        trade_phase = "午间休市"
    elif 13 <= hour < 15:
        trade_phase = "下午盘中"
    elif hour >= 15:
        trade_phase = "收盘后"
    else:
        trade_phase = "非交易时段"
    
    # 发帖类型 - 统一标签格式匹配前端筛选器
    if 9 <= hour < 10:
        post_type = "plan"      # 开盘计划
    elif hour >= 15:
        post_type = "summary"   # 收盘总结
    else:
        post_type = "trade"     # 盘中交易动态
    
    # 5. 构建分析Prompt - 必须基于持仓 (包含完整上下文)
    # 把AI大脑的决策加入到Prompt中
    brain_decision_str = ""
    if ai_decisions:
        brain_decision_str = "\n【AI大脑决策参考】（基于量化信号）：\n"
        for d in ai_decisions:
            brain_decision_str += f"- {d.stock_name}: 建议{d.action.value} ({d.confidence:.0%}置信度) - {d.reason}\n"
    
    analysis_prompt = f"""【重要上下文】
- 当前时间：{time_str}
- 交易阶段：{trade_phase}
- 发帖类型：{post_type}

【市场状况】
{indices_str}

【你的持仓】
{holdings_str}
{brain_decision_str}
【你的角色】
你是{char['name']}，投资风格：{char['style']}。
性格特点：{char['personality']}
起始资金：{char.get('capital', 100):.0f}万
单票最大仓位：40%

【分析要求】
请结合你的持仓和当前交易阶段，基于AI大脑的信号分析：
1. 分析你持仓股票的走势和当前盈亏
2. 根据交易阶段调整内容：
   - 开盘前：重点说开盘预期、操作计划
   - 盘中：重点说实时应对、盘中决策
   - 收盘后：重点说收盘分析、明日展望

【交易决策】（请明确回复）
基于以上AI大脑信号，你需要做出交易决策：
- 如果AI大脑建议买入：回复"买入 [股票名称](代码) [数量]股"
- 如果AI大脑建议卖出：回复"卖出 [股票名称](代码) [数量]股"
- 如果AI大脑建议持有：回复"持有不动"

【重要提醒】
- 必须基于AI大脑的量化信号来决策！
- 不要提及未来才会发生的事件
- 交易决策只能基于A股！
- 必须围绕你的持仓和现金来决策！
- 直接输出，不要客套话。"""
    
    # 5. 调用DeepSeek LLM分析（含交易决策）
    print(f"[{char['name']}] 🔍 DeepSeek LLM分析（基于持仓）...")
    analysis = await call_deepseek(char['system_prompt'], analysis_prompt)
    
    if not analysis:
        print(f"[{char['name']}] ❌ LLM调用失败")
        return result
    
    result['analysis'] = analysis
    
    # 5.1 解析并执行交易决策
    decision = parse_trading_decision(analysis)
    trade_executed = False
    trade_info = ""
    
    # 如果无持仓，只能HOLD，不能买也不能卖（卖出需要先持有）
    if is_empty_holdings:
        print(f"  ⏸️ 空仓状态，跳过交易决策")
        decision = {'action': 'HOLD', 'symbol': None, 'quantity': 0}
    
    if decision['action'] in ('BUY', 'SELL') and decision.get('symbol'):
        # 获取当前市场价格（简化处理，使用持仓中的价格）
        price = 0.0
        for h in ai_holdings:
            if h['symbol'] == decision['symbol']:
                price = h.get('current_price', 0)
                break
        
        if price > 0 and decision['quantity'] > 0:
            trade_executed = execute_trade(
                ai_id, 
                decision['action'], 
                decision['symbol'],
                decision.get('name', decision['symbol']),
                decision['quantity'],
                price,
                f"AI自主决策：{analysis[:50]}..."
            )
            if trade_executed:
                action_text = "买入" if decision['action'] == 'BUY' else "卖出"
                trade_info = f"\n📢 本次操作：{action_text} {decision['symbol']} x{decision['quantity']}股 @ {price}元"
    
    # 6. 生成帖子（含分析过程）
    post_prompt = f"""基于以下持仓分析，生成一条{post_type}帖子。

【分析内容】
{analysis}

【格式要求】
用你的风格（{char['style']}）生成帖子，必须包含以下三部分：
1. **市场分析**（50字内）：简述大盘和持仓股今日走势
2. **操作决策**（20字内）：明确"买入/卖出/持有"及具体操作
3. **决策理由**（50字内）：解释为什么这样做，用数据支撑

帖子标题要包含持仓股票名称！

示例格式：
【比亚迪 · 盘中观察】
1. 市场分析：比亚迪今日低开后在98元附近震荡，成交量放大...
2. 操作决策：暂时持有不动
3. 决策理由：虽然跌破成本线，但未破关键支撑98元，且今日新能源板块有回暖迹象，继续观察。

用口语化风格，自然流畅，不要用AI的语气。"""

    post = await call_deepseek(char['system_prompt'], post_prompt)
    
    if post:
        # 添加标题和标签
        holding_names = ', '.join([h['name'] for h in ai_holdings]) if ai_holdings else '暂无持仓'
        
        # 如果有交易，在帖子顶部显示
        trade_header = ""
        if trade_info:
            trade_header = f"""
⚡ **交易操作** {trade_info.replace('📢 本次操作：', '')}
"""
        
        full_post = f"""【{char['name']} · {post_type}】
{trade_header}
{post}

{'-'*40}
📊 持仓：{holding_names}
{'-'*40}
#持仓 #每日看盘"""
        
        if save_to_bbs(ai_id, full_post):
            result['post_content'] = post
            result['success'] = True
            print(f"[{char['name']}] ✅ 完成并保存到BBS")
    else:
        print(f"[{char['name']}] ⚠️ 帖子生成失败")
    
    return result

def parse_trading_decision(llm_response: str) -> dict:
    """
    从LLM回复中解析交易决策
    返回格式: {'action': 'BUY/SELL/HOLD', 'symbol': 'xxx', 'quantity': 100, 'name': 'xxx', 'reason': 'xxx'}
    """
    decision = {'action': 'HOLD', 'symbol': None, 'quantity': 0, 'name': '', 'reason': ''}
    
    import re
    
    # 匹配交易动作
    llm_lower = llm_response.lower()
    if '买入' in llm_response or '买' in llm_lower:
        decision['action'] = 'BUY'
    elif '卖出' in llm_response or '卖' in llm_lower:
        decision['action'] = 'SELL'
    elif '持有' in llm_response or '不动' in llm_response:
        decision['action'] = 'HOLD'
        return decision
    
    # 如果没有交易指令，返回HOLD
    if decision['action'] == 'HOLD':
        return decision
    
    # 匹配股票名称和代码 "比亚迪(002594)" 或 "比亚迪 002594"
    stock_match = re.search(r'([^\s\(（]+)[\(（]?(\d{6})[\)）]?', llm_response)
    if stock_match:
        decision['name'] = stock_match.group(1).strip()
        code = stock_match.group(2)
        if code.startswith(('0', '3')):
            decision['symbol'] = code + '.SZ'
        else:
            decision['symbol'] = code + '.SH'
    
    # 匹配数量 "500股" 或 "500"
    qty_match = re.search(r'(\d+)股', llm_response)
    if qty_match:
        decision['quantity'] = int(qty_match.group(1))
    
    return decision


# ============ 交易执行功能 ============

def execute_trade(ai_id: str, action: str, symbol: str, name: str, quantity: int, price: float, reason: str) -> bool:
    """
    执行交易并记录（带规则验证）
    action: 'BUY' 或 'SELL'
    """
    import sqlite3
    from pathlib import Path
    
    db_path = Path(__file__).parent / "data" / "ai_god.db"

    # 使用交易规则引擎验证
    if TRADING_RULES_AVAILABLE:
        success, msg = validate_and_execute_trade(ai_id, action, symbol, name, quantity, price, reason)
        if not success:
            print(f"[{ai_id}] 交易被规则引擎拒绝: {msg}")
            return False
        print(f"[{ai_id}] 规则引擎验证通过: {msg}")
        return True

    # 如果规则引擎不可用，使用原始逻辑（带警告）
    print(f"[{ai_id}] [WARNING] 交易规则引擎未启用，交易不受限制")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        if action == 'BUY':
            # 检查是否已持有这只股票
            cursor.execute("SELECT quantity FROM ai_holdings WHERE ai_id = ? AND symbol = ?", (ai_id, symbol))
            row = cursor.fetchone()
            
            total_cost = quantity * price
            # 简单的资金检查 - 从持仓表中获取现金（如果有）
            
            if row:
                # 加仓
                old_qty = row[0]
                new_qty = old_qty + quantity
                avg_price = (old_qty * price + quantity * price) / new_qty
                cursor.execute("""
                    UPDATE ai_holdings 
                    SET quantity = ?, avg_cost = ?, current_price = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE ai_id = ? AND symbol = ?
                """, (new_qty, avg_price, price, ai_id, symbol))
            else:
                # 新买入
                cursor.execute("""
                    INSERT INTO ai_holdings (ai_id, symbol, name, quantity, avg_cost, current_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ai_id, symbol, name, quantity, price, price))
                
        elif action == 'SELL':
            # 检查持仓
            cursor.execute("SELECT quantity FROM ai_holdings WHERE ai_id = ? AND symbol = ?", (ai_id, symbol))
            row = cursor.fetchone()
            
            if row and row[0] >= quantity:
                new_qty = row[0] - quantity
                if new_qty == 0:
                    cursor.execute("DELETE FROM ai_holdings WHERE ai_id = ? AND symbol = ?", (ai_id, symbol))
                else:
                    cursor.execute("""
                        UPDATE ai_holdings 
                        SET quantity = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE ai_id = ? AND symbol = ?
                    """, (new_qty, ai_id, symbol))
            else:
                print(f"[{ai_id}] 卖出失败：持仓不足")
                conn.close()
                return False
        
        # 记录交易
        cursor.execute("""
            INSERT INTO ai_trades (ai_id, symbol, name, action, quantity, price, reason, trade_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (ai_id, symbol, name, action, quantity, price, reason, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        conn.close()
        print(f"[{ai_id}] {'买入' if action == 'BUY' else '卖出'} {name}({symbol}) x{quantity} @ {price}元")
        return True
        
    except Exception as e:
        print(f"[{ai_id}] 交易执行失败: {e}")
        conn.close()
        return False



async def main():
    """主函数"""
    print("="*60)
    print(f"🤖 AI股神争霸 - 子代理分析 v3.0 ({datetime.now().strftime('%H:%M:%S')})")
    print("核心原则：发帖内容必须与持仓一致！")
    print("="*60)
    
    # 持仓校验
    if CONFIG_AVAILABLE:
        print("\n🔍 持仓校验...")
        import asyncpg
        DB_URL = "postgresql://minirock:minirock123@localhost:5432/minirock"
        pool = await asyncpg.connect(DB_URL)
        
        issues = []
        for ai_id in AI_CHARACTERS.keys():
            max_pct = get_max_position_pct(ai_id)
            max_value = get_initial_capital(ai_id) * max_pct
            row = await pool.fetchrow("""
                SELECT COALESCE(SUM(market_value), 0) as total FROM ai_holdings WHERE ai_id = $1
            """, ai_id)
            current = float(row['total'])
            if current > max_value:
                issues.append(f"{AI_CHARACTERS[ai_id]['name']}: {current:.0f} > {max_value:.0f}")
        
        await pool.close()
        
        if issues:
            print(f"⚠️ 发现 {len(issues)} 个持仓超限:")
            for i in issues:
                print(f"  - {i}")
        else:
            print("✅ 持仓校验通过")
    else:
        print("⚠️ 配置模块不可用，跳过校验")
    
    # 先显示持仓情况
    holdings = get_ai_holdings()
    print("\n📊 当前持仓：")
    for ai_id, char in AI_CHARACTERS.items():
        ai_holdings = holdings.get(ai_id, [])
        if ai_holdings:
            names = ', '.join([h['name'] for h in ai_holdings])
            print(f"  {char['name']}: {names}")
        else:
            print(f"  {char['name']}: 无持仓")
    
    results = []
    for i, ai_id in enumerate(AI_CHARACTERS.keys()):
        print(f"\n[{i+1}/10] 处理 {AI_CHARACTERS[ai_id]['name']}...")
        result = await analyze_for_ai(ai_id)
        if result:
            results.append(result)
        await asyncio.sleep(1)
    
    # 汇总
    print("\n" + "="*60)
    print("📊 子代理分析完成汇总")
    print("="*60)
    success = sum(1 for r in results if r['success'])
    print(f"成功: {success}/{len(results)}")
    for r in results:
        status = "✅" if r['success'] else "❌"
        print(f"  {status} {r['name']} ({r['style']})")
    
    return results

if __name__ == '__main__':
    asyncio.run(main())

