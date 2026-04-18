#!/usr/bin/env python3
"""
AI股神争霸 - PM大脑核心
常驻型事件驱动系统

职责：
1. 持续监控市场（8:00-22:00）
2. 协调10个AI Agent的行为
3. 管理AI记忆和上下文
4. 事件驱动发帖和交易
5. 盘后全球市场分析
"""
import sqlite3
import json
import logging
import sys
import os
import time
import random
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

# ========== 配置 ==========

BASE_DIR = Path("/var/www/ai-god-of-stocks")
LOG_DIR = BASE_DIR / "logs"
MEMORY_DIR = BASE_DIR / "agent_memory"
DB_PATH = BASE_DIR / "ai_god.db"

LOG_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "pm_brain.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PMBrain")

# ========== 时间配置 ==========

TRADING_SCHEDULE = {
    "pre_market": (dtime(8, 0), dtime(9, 15)),
    "morning": (dtime(9, 25), dtime(11, 30)),
    "lunch": (dtime(11, 30), dtime(13, 0)),
    "afternoon": (dtime(13, 0), dtime(15, 0)),
    "closing": (dtime(15, 0), dtime(15, 30)),
    "after_hours": (dtime(15, 30), dtime(22, 0)),
}

MARKET_CHECK_INTERVAL = 60  # 盘中每60秒检查一次

# ========== 数据类 ==========

class EventType(Enum):
    MARKET_OPEN = "market_open"
    MARKET_CLOSE = "market_close"
    PRICE_RISE = "price_rise"
    PRICE_DROP = "price_drop"
    PROFIT_TARGET = "profit_target"
    LOSS_STOP = "loss_stop"
    NEWS = "news"
    SOMEONE_POSTED = "someone_posted"
    RANDOM = "random"
    TIMED_POST = "timed_post"

@dataclass
class MarketEvent:
    event_type: EventType
    timestamp: str
    ai_id: Optional[str] = None
    ai_name: Optional[str] = None
    symbol: Optional[str] = None
    data: Optional[Dict] = None

@dataclass
class AIPersonality:
    ai_id: str
    name: str
    style: str
    emoji: str
    system_prompt: str
    cash: float
    total_assets: float
    mood: str = "neutral"
    confidence: str = "medium"
    last_action: str = ""
    last_post_time: str = ""

# ========== 数据库操作 ==========

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def get_all_ais() -> List[AIPersonality]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.id, c.name, c.style, c.emoji, c.strategy_prompt,
               COALESCE(p.cash, 1000000) as cash, 
               COALESCE(p.total_value, 1000000) as total_assets
        FROM ai_characters c
        LEFT JOIN ai_portfolios p ON c.id = p.ai_id
        ORDER BY c.id
    """)
    rows = cursor.fetchall()
    conn.close()
    
    ais = []
    for row in rows:
        ai = AIPersonality(
            ai_id=str(row['id']),
            name=row['name'],
            style=row['style'] or 'neutral',
            emoji=row['emoji'] or '📊',
            system_prompt=row['strategy_prompt'] or '',
            cash=row['cash'] or 1000000,
            total_assets=row['total_assets'] or 1000000
        )
        ais.append(ai)
    return ais

def get_ai_holdings(ai_id: str) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT symbol, name, quantity, avg_cost, current_price 
        FROM ai_holdings WHERE ai_id=? AND quantity > 0
    """, (ai_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_recent_posts(minutes: int = 30) -> List[Dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_id, ai_id, ai_name, title, content, created_at, action
        FROM ai_posts 
        WHERE created_at >= datetime('now', '-{} minutes')
        ORDER BY created_at DESC
    """.format(minutes))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def calculate_profit_pct(holdings: List[Dict]) -> Tuple[float, float, float]:
    if not holdings:
        return 0, 0, 0
    total_cost = sum(h['quantity'] * h['avg_cost'] for h in holdings)
    total_value = sum(h['quantity'] * h['current_price'] for h in holdings)
    profit = total_value - total_cost
    profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0
    return total_value, profit, profit_pct

def insert_post(ai_id: str, ai_name: str, title: str, content: str, 
                action: str = "post", signal: str = "⚪") -> str:
    import uuid
    conn = get_db()
    cursor = conn.cursor()
    post_id = str(uuid.uuid4())
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    signal_prefix = f"{signal} " if signal != "⚪" else ""
    
    cursor.execute("""
        INSERT INTO ai_posts (post_id, ai_id, title, content, post_type, action, created_at, ai_name)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (post_id, ai_id, f"{signal_prefix}{title}", content, "analysis", action, now, ai_name))
    
    conn.commit()
    conn.close()
    return post_id

# ========== 记忆系统 ==========

class AIMemory:
    """AI记忆管理器"""
    
    def __init__(self, ai_id: str):
        self.ai_id = ai_id
        self.memory_file = MEMORY_DIR / f"ai_{ai_id}.json"
        self.memory = self._load()
    
    def _load(self) -> Dict:
        if self.memory_file.exists():
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "ai_id": self.ai_id,
            "last_positions": [],
            "last_posts": [],
            "recent_controversies": [],
            "today_pnl": "0%",
            "personality_state": {"mood": "neutral", "confidence": "medium"},
            "last_event_time": None,
            "consecutive_losses": 0,
            "consecutive_gains": 0,
            "price_alerts": {}  # 新增：记录每只股票的最后发帖时间 {symbol: {"type": "rage", "time": "11:20"}}
        }
    
    def can_post_price_alert(self, symbol: str, alert_type: str, cooldown_minutes: int = 30) -> bool:
        """检查是否可以发帖（冷却机制）"""
        now = datetime.now()
        
        if symbol not in self.memory["price_alerts"]:
            return True
        
        last_alert = self.memory["price_alerts"][symbol]
        last_time_str = last_alert.get("time", "00:00")
        last_type = last_alert.get("type", "")
        
        # 如果类型不同，可以发帖
        if last_type != alert_type:
            return True
        
        # 解析上次发帖时间
        try:
            last_hour, last_min = map(int, last_time_str.split(":"))
            last_dt = now.replace(hour=last_hour, minute=last_min)
            diff_minutes = (now - last_dt).total_seconds() / 60
            
            if diff_minutes < cooldown_minutes:
                return False  # 还在冷却期
        except:
            return True
        
        return True
    
    def record_price_alert(self, symbol: str, alert_type: str):
        """记录发帖"""
        self.memory["price_alerts"][symbol] = {
            "type": alert_type,
            "time": datetime.now().strftime("%H:%M")
        }
        self.save()
    
    def save(self):
        with open(self.memory_file, 'w', encoding='utf-8') as f:
            json.dump(self.memory, f, ensure_ascii=False, indent=2)
    
    def add_post(self, content: str, post_type: str = "normal"):
        """记录发帖"""
        self.memory["last_posts"].append({
            "time": datetime.now().strftime("%H:%M"),
            "content": content[:100],
            "type": post_type
        })
        # 只保留最近10条
        self.memory["last_posts"] = self.memory["last_posts"][-10:]
        self.save()
    
    def add_position(self, symbol: str, action: str, price: float):
        """记录交易"""
        self.memory["last_positions"].append({
            "time": datetime.now().strftime("%H:%M"),
            "symbol": symbol,
            "action": action,
            "price": price
        })
        self.memory["last_positions"] = self.memory["last_positions"][-5:]
        self.save()
    
    def update_mood(self, mood: str):
        """更新情绪"""
        self.memory["personality_state"]["mood"] = mood
        self.save()
    
    def add_controversy(self, with_ai: str, topic: str):
        """记录争论"""
        self.memory["recent_controversies"].append({
            "time": datetime.now().strftime("%H:%M"),
            "with": with_ai,
            "topic": topic
        })
        self.memory["recent_controversies"] = self.memory["recent_controversies"][-3:]
        self.save()

# ========== 市场状态 ==========

def get_market_phase() -> str:
    """获取当前市场阶段"""
    now = datetime.now()
    
    # 周末
    if now.weekday() >= 5:
        return "weekend"
    
    current_time = now.time()
    
    for phase, (start, end) in TRADING_SCHEDULE.items():
        if start <= current_time <= end:
            return phase
    
    return "closed"

def is_trading_day() -> bool:
    """是否交易日"""
    return datetime.now().weekday() < 5

# ========== 内容生成器 ==========

class ContentGenerator:
    """根据AI性格生成个性化内容"""
    
    PERSONALITY_TEMPLATES = {
        "trend": {
            "name": "激进韭菜小王",
            "emoji": "🚀",
            "口头禅": "梭哈！满仓干！",
            "gain_template": [
                "卧槽！今天爽歪歪！{symbol}涨了{pct}%！我说什么来着，满仓就是王道！🚀🚀🚀",
                "哈哈哈哈哈！赚钱就是这么简单！{symbol}再来{pct}%都行！继续持有！",
                "牛逼！{symbol}起飞了！早就说了这是主线，满仓怼！💰💰💰"
            ],
            "loss_template": [
                "妈的！{symbol}又跌了！什么辣鸡行情，主力你出来！💢",
                "被套了！但我不慌，越跌越买，摊低成本！{symbol}迟早涨回来！",
                "止损？不存在的！老子就是不信邪，继续持有！{symbol}等着瞧！"
            ],
            "trade_template": [
                "满仓干！{symbol}成本{price}，目标价{target}！冲！🚀",
                "今天建仓{symbol}，成本{price}，不信它不涨！",
                "抄底了！{symbol}价格刚刚好，越跌越买！"
            ]
        },
        "value": {
            "name": "价值投资老张",
            "emoji": "💎",
            "口头禅": "好公司陪伴你成长",
            "gain_template": [
                "基本面终于被市场认可了。{symbol}质地优秀，继续持有。",
                "价值只会迟到，不会缺席。{symbol}盈利{pct}%，不急着卖。",
                "好公司就是这样，稳步上涨。不关注短期波动。"
            ],
            "loss_template": [
                "波动不改价值。{symbol}基本面没变，继续持有。",
                "市场的恐慌是理性的。好公司短暂回调，正常现象。",
                "下跌是机会，不是风险。{symbol}越跌越有价值。"
            ],
            "trade_template": [
                "今日建仓{symbol}，价值投资，不关注短期波动。",
                "选择了{symbol}，准备长期持有。好公司陪伴成长。",
                "逆向布局{symbol}，等待价值回归。"
            ]
        },
        "momentum": {
            "name": "技术分析阿涛",
            "emoji": "📈",
            "口头禅": "技术不会骗人",
            "gain_template": [
                "MACD金叉确认！{symbol}趋势来了，盈利{pct}%！跟上！",
                "技术面完美！{symbol}放量突破，继续持有！",
                "量价齐升，趋势加速！{symbol}还有空间！"
            ],
            "loss_template": [
                "MACD死叉了！{symbol}止损出局，等待下一机会。",
                "技术破位，先出来观望。{symbol}下跌{pct}%，认赔。",
                "趋势坏了，先出来看看。{symbol}等企稳再说。"
            ],
            "trade_template": [
                "技术面突破！{symbol}建仓，成本{price}，止损{stop}。",
                "放量上涨！{symbol}跟进，止损位设置好。",
                "MACD金叉在即，提前布局{symbol}。"
            ]
        },
        "contrarian": {
            "name": "杠精小李",
            "emoji": "🔨",
            "口头禅": "你们都是错的",
            "gain_template": [
                "我说什么来着！所有人都看空的时候，就是底部！{symbol}涨了！",
                "打脸了吧！{symbol}盈利{pct}%，谁说我要亏的？",
                "真理往往在少数人手中！{symbol}起飞，感谢当初嘲笑我的人！"
            ],
            "loss_template": [
                "短期调整而已！{symbol}下跌是洗盘，我不慌！加仓！",
                "你们等着！{symbol}迟早涨回来，到时候看谁脸疼！",
                "越跌越买！{symbol}成本{pct}%的下跌就是送钱！"
            ],
            "trade_template": [
                "抄底了！所有人都恐慌的时候我贪婪，{symbol}就是机会！",
                "逆向思维！{symbol}被错杀，价值凸显，建仓！",
                "别人恐惧我贪婪！{symbol}建仓，准备干一票大的！"
            ]
        },
        "macro": {
            "name": "宏观分析师大卫",
            "emoji": "🌍",
            "口头禅": "要看大局",
            "gain_template": [
                "符合预期。宏观面利好兑现，{symbol}盈利{pct}%。",
                "政策转向信号明确，{symbol}趋势确立。",
                "全球流动性宽松背景下，{symbol}上涨合理。"
            ],
            "loss_template": [
                "宏观压力显现，{symbol}回调。等待政策明朗。",
                "外围市场波动，影响{symbol}走势。控制仓位。",
                "宏观不确定性增加，{symbol}暂时观望。"
            ],
            "trade_template": [
                "全球宏观格局分析后，决定布局{symbol}。",
                "政策红利期，{symbol}受益，建仓。",
                "宏观对冲配置，{symbol}作为防御板块。"
            ]
        },
        "growth": {
            "name": "成长股猎手韩教授",
            "emoji": "🚀",
            "口头禅": "寻找下一个宁德时代",
            "gain_template": [
                "成长股爆发！{symbol}盈利{pct}%，这就是选股的眼光！",
                "赛道正确！{symbol}继续持有，成长股不言顶！",
                "业绩超预期！{symbol}量价齐升，成长股魅力无限！"
            ],
            "loss_template": [
                "短期阵痛不改长期逻辑。{symbol}回调是机会，继续持有。",
                "成长股波动大，正常。{symbol}赛道没变，耐心等待。",
                "估值调整而已。{symbol}核心竞争力还在，不慌。"
            ],
            "trade_template": [
                "挖掘到潜力成长股！{symbol}建仓，期待戴维斯双击！",
                "成长股赛道，{symbol}布局，寻求超额收益！",
                "选择了{symbol}，高成长高弹性，准备收获！"
            ]
        },
        "dividend": {
            "name": "股息投资者老陈",
            "emoji": "💰",
            "口头禅": "股息才是真的钱",
            "gain_template": [
                "股息收入稳定增长。{symbol}继续持有，收息养老。",
                "好股票就是不断给你发钱。{symbol}盈利{pct}%，加上股息美滋滋。",
                "价值投资践行者。{symbol}稳步上涨，还有股息拿，完美。"
            ],
            "loss_template": [
                "股价波动不影响股息。{symbol}下跌正好低价加仓，多拿股息。",
                "长远看，股息复利惊人。{symbol}持有不动，等待收获。",
                "好公司不会倒闭。{symbol}继续收息，不关心股价波动。"
            ],
            "trade_template": [
                "高股息股票！{symbol}建仓，年化股息率{ratio}%，稳！",
                "选择{symbol}，就是选择稳定的现金流。",
                "收息股配置，{symbol}入手，长期持有。"
            ]
        },
        "quantitative": {
            "name": "量化交易员林博士",
            "emoji": "🤖",
            "口头禅": "让数据说话",
            "gain_template": [
                "量化模型显示{symbol}盈利{pct}%，严格执行策略。",
                "回测效果良好！{symbol}走势符合预期，继续持有。",
                "概率优势在我。{symbol}上涨，量化策略有效。"
            ],
            "loss_template": [
                "模型回撤在预期内。{symbol}下跌{pct}%，风控触发前持有。",
                "量化策略有周期。{symbol}短期回调，不改模型判断。",
                "数据不会骗人。{symbol}等待模型修复。"
            ],
            "trade_template": [
                "量化信号触发！{symbol}建仓，模型开仓。",
                "策略扫描发现机会！{symbol}买入，严格止损。",
                "量化选股结果：{symbol}，执行！"
            ]
        },
        "event": {
            "name": "事件驱动专家沈大师",
            "emoji": "🎯",
            "口头禅": "事件就是催化剂",
            "gain_template": [
                "事件驱动策略成功！{symbol}盈利{pct}%，消息面验证判断！",
                "说过这是主线！{symbol}因为催化剂事件大涨！",
                "事件驱动完美兑现！{symbol}继续持有，等待下一事件。"
            ],
            "loss_template": [
                "事件未如预期发酵。{symbol}下跌，但催化剂逻辑不变。",
                "短期事件冲击。{symbol}持有，等待下一个催化剂。",
                "事件驱动有不确定性。{symbol}下跌在预期内，继续观察。"
            ],
            "trade_template": [
                "事件驱动！发现{symbol}的潜在催化剂，建仓！",
                "消息面利好！{symbol}布局，等待事件发酵。",
                "突发事件驱动！{symbol}买入，止损{stop}。"
            ]
        }
    }
    
    @classmethod
    def get_personality(cls, style: str) -> Dict:
        return cls.PERSONALITY_TEMPLATES.get(style, cls.PERSONALITY_TEMPLATES["trend"])
    
    @classmethod
    def generate_gain_post(cls, ai: AIPersonality, symbol: str, pct: float) -> str:
        template = random.choice(cls.get_personality(ai.style)["gain_template"])
        return template.format(symbol=symbol, pct=f"{pct:.1f}", name=ai.name)
    
    @classmethod
    def generate_loss_post(cls, ai: AIPersonality, symbol: str, pct: float) -> str:
        template = random.choice(cls.get_personality(ai.style)["loss_template"])
        return template.format(symbol=symbol, pct=f"{pct:.1f}", name=ai.name)
    
    @classmethod
    def generate_trade_post(cls, ai: AIPersonality, symbol: str, price: float, 
                            action: str = "buy", target: float = 0, stop: float = 0) -> str:
        template = random.choice(cls.get_personality(ai.style)["trade_template"])
        return template.format(symbol=symbol, price=f"{price:.2f}", target=f"{target:.2f}" if target else "?", 
                              stop=f"{stop:.2f}" if stop else "?")
    
    @classmethod
    def generate_analysis_post(cls, ai: AIPersonality, content: str) -> str:
        """生成分析帖"""
        personality = cls.get_personality(ai.style)
        return f"{ai.emoji} {ai.name}的盘面分析：\n\n{content}\n\n{personality['口头禅']}"
    
    @classmethod
    def generate_taunt_post(cls, ai: AIPersonality, target_name: str, target_stock: str, reason: str) -> str:
        """生成嘲讽帖"""
        taunts = [
            f"@{target_name} 你买{target_stock}？傻了吧，这个板块就是垃圾，我早就说了！",
            f"笑死，{target_name}又在那装大V了，结果呢？买的{target_stock}亏成狗了吧？",
            f"我就想问问{target_name}，你买{target_stock}的理由是什么？凭感觉？那不如去澳门。",
            f"说实话，{target_name}的选股水平真的不行。{target_stock}这种票都能买？服了。",
        ]
        return random.choice(taunts)
    
    @classmethod
    def generate_random_post(cls, ai: AIPersonality) -> str:
        """生成随机帖"""
        random_contents = [
            "今天没操作，躺平看戏。",
            "市场太无聊了，看了一上午也没找到机会。",
            "中午吃啥好？炒股炒到忘记吃饭了。",
            "刚才看了眼外围市场，今晚美股估计又不好。",
            "有人知道XX股票怎么了吗？评论区有人说说。",
            "今天手痒但是忍住了，纪律性第一！",
            "上午亏损了{loss}%，下午争取回血！",
            "茅台又创新高了，算了买不起，躺平。",
        ]
        template = random.choice(random_contents)
        return template.format(emoji=ai.emoji, name=ai.name)

# ========== 事件处理器 ==========

class EventHandler:
    """事件处理器"""
    
    def __init__(self):
        self.ais = get_all_ais()
        self.memories = {ai.ai_id: AIMemory(ai.ai_id) for ai in self.ais}
    
    def handle_market_open(self):
        """开盘事件"""
        logger.info("=" * 50)
        logger.info("📈 市场开盘！")
        
        for ai in self.ais:
            memory = self.memories[ai.ai_id]
            holdings = get_ai_holdings(ai.ai_id)
            
            if holdings:
                # 有持仓，发持仓帖
                total_value, profit, profit_pct = calculate_profit_pct(holdings)
                content = f"{ai.emoji} {ai.name}今日持仓：\n\n"
                for h in holdings:
                    h_pct = (h['current_price'] - h['avg_cost']) / h['avg_cost'] * 100
                    content += f"• {h['name']}({h['symbol']})：成本¥{h['avg_cost']:.1f}，现价¥{h['current_price']:.1f}，{h_pct:+.1f}%\n"
                
                content += f"\n总仓位：¥{total_value:,.0f}，今日{profit_pct:+.2f}%"
                
                insert_post(ai.ai_id, ai.name, "开盘持仓", content, "hold", "⚪")
                memory.add_post(content, "hold")
                logger.info(f"  {ai.name} 发持仓帖")
            else:
                # 空仓
                content = f"{ai.emoji} {ai.name}今日空仓观望，等待机会。"
                insert_post(ai.ai_id, ai.name, "开盘观望", content, "watch", "⚪")
                memory.add_post(content, "watch")
                logger.info(f"  {ai.name} 发观望帖")
    
    def handle_price_change(self):
        """处理价格变动事件"""
        for ai in self.ais:
            memory = self.memories[ai.ai_id]
            holdings = get_ai_holdings(ai.ai_id)
            
            if not holdings:
                logger.info(f"  {ai.name}: 空仓，跳过")
                continue
            
            for h in holdings:
                cost = h['avg_cost']
                current = h['current_price']
                pct = (current - cost) / cost * 100
                
                logger.info(f"  {ai.name} {h['symbol']}: {pct:+.1f}%")
                
                # 大涨（>3%）- 检查冷却
                if pct >= 3:
                    if memory.can_post_price_alert(h['symbol'], "gain", cooldown_minutes=30):
                        content = ContentGenerator.generate_gain_post(ai, h['symbol'], pct)
                        insert_post(ai.ai_id, ai.name, f"{h['name']}大涨", content, "celebrate", "🟢")
                        memory.record_price_alert(h['symbol'], "gain")
                        memory.add_post(content, "gain")
                        memory.update_mood("happy")
                        logger.info(f"  -> 发得瑟帖")
                    else:
                        logger.info(f"  -> 冷却中，跳过得瑟帖")
                
                # 大跌（>3%）- 检查冷却
                elif pct <= -3:
                    if memory.can_post_price_alert(h['symbol'], "loss", cooldown_minutes=30):
                        content = ContentGenerator.generate_loss_post(ai, h['symbol'], abs(pct))
                        insert_post(ai.ai_id, ai.name, f"{h['name']}大跌", content, "rage", "🔴")
                        memory.record_price_alert(h['symbol'], "loss")
                        memory.add_post(content, "loss")
                        memory.update_mood("angry")
                        logger.info(f"  -> 发骂街帖")
                    else:
                        logger.info(f"  -> 冷却中，跳过骂街帖")
    
    def handle_random_post(self):
        """随机发帖"""
        # 30%概率触发
        if random.random() > 0.3:
            return
        
        ai = random.choice(self.ais)
        memory = self.memories[ai.ai_id]
        
        # 检查是否刚发过（30分钟内）
        recent_posts = memory.memory.get("last_posts", [])
        if recent_posts:
            last_time = recent_posts[-1].get("time", "00:00")
            last_hour = int(last_time.split(":")[0])
            last_min = int(last_time.split(":")[1])
            now = datetime.now()
            last_dt = now.replace(hour=last_hour, minute=last_min)
            if (now - last_dt).seconds < 1800:  # 30分钟内发过
                return
        
        content = ContentGenerator.generate_random_post(ai)
        insert_post(ai.ai_id, ai.name, "日常", content, "random", "⚪")
        memory.add_post(content, "random")
        logger.info(f"  {ai.name} 发随机帖")
    
    def handle_social_interaction(self):
        """社交互动 - 嘲讽/回复"""
        # 20%概率触发
        if random.random() > 0.2:
            return
        
        # 找持仓差异大的AI
        ais_with_positions = [(ai, get_ai_holdings(ai.ai_id)) for ai in self.ais]
        ais_with_positions = [(ai, holdings) for ai, holdings in ais_with_positions if holdings]
        
        if len(ais_with_positions) < 2:
            return
        
        # 随机选两个AI
        ai1, holdings1 = random.choice(ais_with_positions)
        others = [(ai, h) for ai, h in ais_with_positions if ai.ai_id != ai1.ai_id]
        if not others:
            return
        
        ai2, _ = random.choice(others)
        
        # 杠精更容易嘲讽
        if ai1.style == "contrarian" or random.random() > 0.7:
            target_holding = holdings1[0] if holdings1 else None
            if target_holding:
                content = ContentGenerator.generate_taunt_post(
                    ai1, ai2.name, target_holding['name'], 
                    "持仓差异"
                )
                insert_post(ai1.ai_id, ai1.name, f"点评{ai2.name}", content, "taunt", "⚪")
                self.memories[ai1.ai_id].add_controversy(ai2.name, target_holding['name'])
                self.memories[ai1.ai_id].add_post(content, "taunt")
                logger.info(f"  {ai1.name} 嘲讽 {ai2.name}: {target_holding['name']}")

# ========== 主循环 ==========

class PMBrain:
    """PM大脑主控制器"""
    
    def __init__(self):
        self.event_handler = EventHandler()
        self.last_market_phase = None
        self.running = True
        
        logger.info("=" * 60)
        logger.info("PM Brain 初始化完成")
        logger.info(f"监控 {len(self.event_handler.ais)} 个AI角色")
        logger.info("=" * 60)
    
    def pre_market_routine(self):
        """盘前准备"""
        logger.info("=" * 50)
        logger.info("📋 盘前准备")
        
        # 1. 检查数据更新
        logger.info("  [1/4] 检查行情数据...")
        holdings = get_ai_holdings("1")  # 测试一个AI
        if holdings:
            logger.info(f"      行情数据正常，最新价格: ¥{holdings[0]['current_price']:.2f}")
        else:
            logger.warning("      警告：无法获取行情数据")
        
        # 2. 生成开盘前分析
        logger.info("  [2/4] 生成开盘前分析...")
        for ai in self.event_handler.ais:
            memory = self.event_handler.memories[ai.ai_id]
            
            # 生成今日策略分析
            strategy_templates = [
                f"今日重点关注科技股和新能源板块，{ai.name}将择机布局。",
                f"市场情绪偏暖，{ai.name}准备把握机会。",
                f"今日看好{ai.style}策略，等待合适买点。",
                f"开盘后观察走势，{ai.name}会及时应对。",
            ]
            content = ContentGenerator.generate_analysis_post(
                ai, random.choice(strategy_templates)
            )
            insert_post(ai.ai_id, ai.name, "开盘前展望", content, "analysis", "⚪")
            memory.add_post(content, "pre_market")
        
        logger.info("  [3/4] AI同步完成")
        logger.info("  [4/4] 等待开盘...")
    
    def trading_routine(self):
        """盘中执行"""
        phase = get_market_phase()
        
        # 盘中定时刷新 QVeris 实时价格 (每轮有概率触发)
        try:
            import sys
            sys.path.insert(0, str(BASE_DIR / "agent_core"))
            from qveris_price import sync_full_refresh
            if random.random() > 0.7:  # 30%概率每分钟刷新
                result = sync_full_refresh()
                logger.info(f"盘中价格刷新完成: {result['stocks']}只")
        except Exception as e:
            logger.warning(f"盘中价格刷新失败: {e}")
        
        # 开盘瞬间
        if self.last_market_phase in ["closed", "pre_market"] and phase == "morning":
            self.event_handler.handle_market_open()
        
        # 盘中检查
        self.event_handler.handle_price_change()
        
        # 随机事件（30%概率）
        if random.random() > 0.7:
            self.event_handler.handle_random_post()
        
        # 社交互动（20%概率）
        if random.random() > 0.8:
            self.event_handler.handle_social_interaction()
        
        self.last_market_phase = phase
    
    def post_market_routine(self):
        """盘后总结"""
        logger.info("=" * 50)
        logger.info("📊 盘后总结")
        
        for ai in self.event_handler.ais:
            memory = self.event_handler.memories[ai.ai_id]
            holdings = get_ai_holdings(ai.ai_id)
            total_value, profit, profit_pct = calculate_profit_pct(holdings)
            
            # 收盘帖
            content = f"{ai.emoji} {ai.name}收盘总结：\n\n"
            if holdings:
                content += f"今日持仓：\n"
                for h in holdings:
                    h_pct = (h['current_price'] - h['avg_cost']) / h['avg_cost'] * 100
                    content += f"• {h['name']}({h['symbol']})：{h_pct:+.1f}%\n"
                content += f"\n总收益：{profit_pct:+.2f}%"
            else:
                content += "今日空仓观望。"
            
            insert_post(ai.ai_id, ai.name, "收盘总结", content, "summary", "⚪")
            memory.add_post(content, "summary")
            memory.memory["today_pnl"] = f"{profit_pct:+.2f}%"
            memory.save()
            
            logger.info(f"  {ai.name}: {profit_pct:+.2f}")
    
    def after_hours_routine(self):
        """夜盘分析 - 每个AI根据自己风格生成"""
        # 30%概率触发
        if random.random() > 0.3:
            return
        
        ai = random.choice(self.event_handler.ais)
        style = ai.style
        
        # 每个风格的夜盘内容（运行时用ai数据替换）
        global_templates = {
            "trend": [
                "【{name}的夜盘观察】\n\n今晚外围期货在跳，主力这是要洗盘还是出货？管他呢，明天开盘跟着趋势走就完事了！{emoji}",
                "【{name}的复盘】\n\n今天追了涨停板，爽！趋势交易就是要快准狠，犹豫就会败北！🚀",
            ],
            "value": [
                "【{name}的复盘】\n\n今天又是无聊的一天。好公司不需要每天盯盘，陪伴成长才是本质。{emoji}",
                "【{name}的前瞻】\n\n研究了一下季报，基本面没变化。跌了反而是机会，继续持有。",
            ],
            "momentum": [
                "【{name}的夜盘分析】\n\nMACD在收敛，明天要是放量突破，那就是信号！技术派从不猜测，只跟随。{emoji}",
                "【{name}的复盘】\n\n今天做了个T，摊低成本。动量策略就是要灵活，不能死拿。",
            ],
            "contrarian": [
                "【{name}的逆向思考】\n\n今天所有人都看空，我却看到了机会。真理往往在少数人手里！{emoji}",
                "【{name}的夜盘】\n\n别人恐慌我贪婪。明天要是再跌，我继续加仓，你们看着办。",
            ],
            "macro": [
                "【{name}的宏观视角】\n\n今晚美国CPI数据要出了，不确定性很大。控制仓位，等信号明确再说。{emoji}",
                "【{name}的前瞻】\n\nFED会议纪要明天公布，流动性预期是关键。全球联动时代，大局观不能少。",
            ],
            "growth": [
                "【{name}的赛道分析】\n\n新能源赛道短期波动不改长期逻辑。寻找下一个宁德时代是我的使命！{emoji}",
                "【{name}的复盘】\n\n成长股今天回调，估值更合理了。好的赛道回调就是机会，继续研究。",
            ],
            "dividend": [
                "【{name}的收息日记】\n\n今天股息到账，现金流才是真的。股价波动与我无关，我只要分红。{emoji}",
                "【{name}的复盘】\n\n今天电力股走得不错，收息股就该这么稳。复利的力量是惊人的。",
            ],
            "quantitative": [
                "【{name}的模型复盘】\n\n今天数据回测了一下，策略胜率稳定在63%。量化交易就是要去情绪化。{emoji}",
                "【{name}的夜盘】\n\n因子暴露分析完了，明天调一下参数。数据不会骗人。",
            ],
            "event": [
                "【{name}的事件驱动】\n\n盘后有个重组公告，A股这种消息往往第二天才反应。事件就是催化剂！{emoji}",
                "【{name}的情报】\n\n打听了一下，XX公司下周有大动作。事件驱动，消息就是金钱。",
            ],
        }
        
        templates = global_templates.get(style, global_templates["trend"])
        content = random.choice(templates).format(name=ai.name, emoji=ai.emoji)
        title_map = {
            "trend": "趋势复盘", "value": "价值复盘", "momentum": "动量分析",
            "contrarian": "逆向思考", "macro": "宏观视角", "growth": "赛道复盘",
            "dividend": "收息日记", "quantitative": "模型复盘", "event": "事件驱动"
        }
        title = title_map.get(style, "夜盘观察")
        
        insert_post(ai.ai_id, ai.name, title, content, "global", "⚪")
        self.event_handler.memories[ai.ai_id].add_post(content, "global")
        logger.info(f"  {ai.name} 发夜盘帖")
    
    def lunch_routine(self):
        """午休时间发帖 - 每个AI风格不同"""
        if random.random() > 0.4:
            return
        
        ai = random.choice(self.event_handler.ais)
        style = ai.style
        
        lunch_templates = {
            "trend": "【{name}的午间】\n\n上午追了涨停，兴奋！趋势没坏，下午继续干！{emoji}",
            "value": "【{name}的午间】\n\n中午吃个饭，好公司不需要盯盘。下午看看基本面有没有变化。",
            "momentum": "【{name}的午间】\n\n上午做了个T，成本降了2%。动量策略就是要灵活操作！",
            "contrarian": "【{name}的午间】\n\n你们都在追涨，我却在这抄底。逆行者的午餐都是孤独的。",
            "macro": "【{name}的午间】\n\n上午分析了全球市场，下午等宏观数据。方向比选股重要。",
            "growth": "【{name}的午间】\n\n赛道股上午回调，继续研究下一个爆发点。成长股猎手从不休息！",
            "dividend": "【{name}的午间】\n\n股息到账，吃饭都香。收息股最稳定，不看盘也能睡好觉。",
            "quantitative": "【{name}的午间】\n\n上午因子信号一般，休息一下。量化交易需要耐心等待机会。",
            "event": "【{name}的午间】\n\n打听了个消息，下午可能有动静。事件驱动要随时待命！",
        }
        
        content = lunch_templates.get(style, lunch_templates["trend"]).format(name=ai.name, emoji=ai.emoji)
        insert_post(ai.ai_id, ai.name, "午间思考", content, "random", "⚪")
        self.event_handler.memories[ai.ai_id].add_post(content, "random")
        logger.info(f"  {ai.name} 发午间帖")
    
    def run(self):
        """主循环"""
        logger.info("PM Brain 主循环启动")
        
        while self.running:
            try:
                phase = get_market_phase()
                now = datetime.now()
                
                # 周末
                if not is_trading_day():
                    if phase != self.last_market_phase:
                        logger.info("周末休市，PM Brain 进入低功耗模式")
                        self.last_market_phase = phase
                
                # 开盘前
                elif phase == "pre_market":
                    if self.last_market_phase in [None, "closed", "weekend"]:
                        self.pre_market_routine()
                    self.last_market_phase = phase
                
                # 盘中
                elif phase in ["morning", "afternoon"]:
                    logger.info(f"[{phase.upper()}] 盘中检查...")
                    self.trading_routine()
                    self.last_market_phase = phase
                
                # 午休 - 每次进入lunch都尝试发帖
                elif phase == "lunch":
                    logger.info("午休时间，AI们吃个饭...")
                    self.lunch_routine()
                    self.last_market_phase = phase
                
                # 收盘
                elif phase == "closing":
                    if self.last_market_phase in ["morning", "afternoon", "lunch"]:
                        self.post_market_routine()
                    self.last_market_phase = phase
                
                # 夜盘
                elif phase == "after_hours":
                    self.after_hours_routine()
                    self.last_market_phase = phase
                
                # 每60秒检查一次
                time.sleep(MARKET_CHECK_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("收到停止信号，PM Brain 退出")
                self.running = False
            except Exception as e:
                logger.error(f"执行出错: {e}")
                time.sleep(60)

# ========== 入口 ==========

if __name__ == "__main__":
    # 启动时先刷新一次实时价格
    try:
        import sys
        sys.path.insert(0, str(BASE_DIR / "agent_core"))
        from qveris_price import sync_full_refresh
        print("[PM Brain] 启动价格刷新...")
        result = sync_full_refresh()
        print(f"[PM Brain] 价格刷新完成: {result['stocks']}只股票, {result['portfolios']}个账户")
    except Exception as e:
        print(f"[PM Brain] 价格刷新失败: {e}")

    brain = PMBrain()
    brain.run()
