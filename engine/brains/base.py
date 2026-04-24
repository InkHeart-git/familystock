"""
AI 股神争霸 - 统一智能大脑
Base Brain - 所有AI大脑的抽象基类

每个AI都有独立的:
- Memory (记忆): 持仓历史、盈亏曲线、帖子记录、市场印象
- TradingDecisionEngine (交易决策): 根据性格 + 数据生成决策
- ContentGenerator (内容生成): 生成拟人化发帖
- SocialEngine (社交引擎): 与其他AI互动

设计原则:
1. 每个AI大脑是自治的，不共享状态（通过SharedContext偶尔通信）
2. 交易决策基于: 性格参数 + 实时行情 + 持仓状态 + 记忆上下文
3. 发帖内容必须与持仓一致（这是铁律）
4. 社交互动是事件驱动，不是定时广播
"""

import asyncio
import json
import logging
import random
import sqlite3
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, date, time as dtime
from enum import Enum
from typing import Dict, List, Optional, Any, Set
from pathlib import Path

import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from engine.memory.ai_memory import AIMemory, MemoryItem
from engine.memory.ai_memory import SharedContext
from engine.posting.content_generator import ContentGenerator, PostType
from engine.posting.post_coordinator import PostCoordinator
from engine.social.interaction_engine import InteractionEngine
from engine.trading.decision_engine import TradingDecision, DecisionSignal, Action

logger = logging.getLogger("Brain")


# ==================== 时间窗口配置 ====================

class Session(Enum):
    PRE_MARKET = "pre_market"      # 08:00-09:25
    OPENING = "opening"            # 09:25-09:35
    MORNING = "morning"           # 09:30-11:30
    NOON = "noon"                 # 11:30-13:00
    AFTERNOON = "afternoon"        # 13:00-14:55
    CLOSING = "closing"            # 14:55-15:05
    AFTER_HOURS = "after_hours"   # 15:05-22:00
    CLOSED = "closed"              # 22:00-08:00


SESSION_TIMES = {
    Session.PRE_MARKET:  (dtime(8, 0),  dtime(9, 25)),
    Session.OPENING:    (dtime(9, 25), dtime(9, 35)),
    Session.MORNING:    (dtime(9, 30), dtime(11, 30)),
    Session.NOON:       (dtime(11, 30), dtime(13, 0)),
    Session.AFTERNOON:  (dtime(13, 0), dtime(14, 55)),
    Session.CLOSING:    (dtime(14, 55), dtime(15, 5)),
    Session.AFTER_HOURS: (dtime(15, 5), dtime(22, 0)),
}


def get_current_session() -> Session:
    now = datetime.now()
    current_t = now.time()
    weekday = now.weekday()
    
    if weekday >= 5:
        return Session.CLOSED
    
    for session, (start, end) in SESSION_TIMES.items():
        if start <= current_t < end:
            return session
    
    return Session.CLOSED


def is_trading_day() -> bool:
    return datetime.now().weekday() < 5


# ==================== 人设配置 ====================

@dataclass
class Personality:
    """AI人设核心参数"""
    expressiveness: int      # 表现欲 0-100
    talkativeness: int       # 话痨度 0-100（发帖频率参考）
    aggressiveness: int      # 攻击性 0-100（嘲讽/反驳倾向）
    emotional_stability: int # 情绪稳定性 0-100
    conformity: int          # 从众性 0-100（是否跟随热点）
    
    # 交易风格
    holding_days_min: int
    holding_days_max: int
    position_max_pct: float   # 单票最大仓位比例
    total_position_max_pct: float  # 总仓位上限
    stop_loss_pct: float      # 止损线 (负数)
    take_profit_pct: float    # 止盈线
    risk_appetite: int        # 风险偏好 0-100
    
    # 人设语言特征
    vocab_set: Set[str]       # 常用词汇集
    speech_pattern: str       # 说话模式: "热血", "理性", "老练", "幽默"
    post_frequency_cap: int  # 每小时最多发帖数（防刷屏）
    social_enabled: bool = True  # 是否参与社交互动（嘲讽/回复其他AI）
    
    @classmethod
    def from_dict(cls, d: Dict) -> "Personality":
        d = d.copy()
        d.pop('vocab_set', None)
        return cls(**d)


@dataclass 
class CharacterConfig:
    """AI角色完整配置"""
    ai_id: str          # brain标识字符串，如 "trend_chaser"
    db_id: int          # DB主键 id (ai_characters.id)
    name: str
    emoji: str
    style: str
    group: str           # "风云五虎" / "灵动小五"
    initial_capital: float
    description: str
    
    # 人设
    personality: Personality
    
    # 系统提示词（用于LLM生成）
    system_prompt: str
    
    # 发帖模板关键词（用于快速生成）
    post_keywords: List[str]
    
    # 持仓冷却（防止频繁换股）
    min_holding_hours: int = 4
    
    # 是否启用社交互动
    social_enabled: bool = True


# ==================== Brain 基类 ====================

class BaseBrain(ABC):
    """
    AI大脑抽象基类
    子类只需实现: get_config(), think_like_human()
    其余逻辑（调度/发帖/决策）由基类统一处理
    """
    
    # 类属性：子类覆盖
    CONFIG: CharacterConfig = None
    
    def __init__(self, db_path: str, minirock_api: str = "http://127.0.0.1:8000"):
        self.db_path = db_path
        self.minirock_api = minirock_api
        self.ai_id = str(self.CONFIG.db_id)  # DB 查询用整数字符串
        self.db_id = self.CONFIG.db_id  # DB primary key
        
        # 子系统初始化
        self.memory = AIMemory(self.ai_id, self.db_path)
        self.shared_ctx = SharedContext()
        self.content_gen = ContentGenerator(self.CONFIG)
        self.post_coord = PostCoordinator(self.ai_id, self.CONFIG.personality.post_frequency_cap)
        self.interaction = InteractionEngine(self.ai_id, self.CONFIG.personality)
        
        # 运行时状态
        self._running = False
        self._market_state: Dict[str, Any] = {}
        self._last_market_check = 0
        self._session = Session.CLOSED
        self._pending_decisions: List[TradingDecision] = []
        
        # 防卡机制：决策冷却跟踪
        self._last_decision: Optional[TradingDecision] = None
        self._last_decision_time: float = 0
        self._decision_cooldown: int = 300  # 5分钟同类决策冷却（秒）
        self._consecutive_rejections: int = 0  # 连续被拦截计数
        self._circuit_broken: bool = False  # 熔断标志
        self._circuit_break_time: float = 0
        
        # 统计
        self.stats = {
            "posts_today": 0,
            "trades_today": 0,
            "decisions_made": 0,
            "social_interactions": 0,
            "risk_rejected": 0,
        }
        
        logger.info(f"[{self.CONFIG.name}] 大脑初始化完成 | 人设: {self.CONFIG.personality.speech_pattern}")

    # ---- 子类必须实现 ----

    @abstractmethod
    def get_config(self) -> CharacterConfig:
        """返回角色配置"""
        pass

    # ==================== LLM推理决策（双模型协作版） ====================
    # 像人类一样思考：内部串联 V4-Pro（深度推理）+ MiniMax（话说人话）
    # 外部只看到一个方法，内部才是双模型协作

    async def think_like_human_llm(
        self,
        market_data: Dict[str, Any],
        my_holdings: List[Dict],
        my_cash: float,
        news: List[Dict],
        minirock_analysis: Dict[str, Dict] = {},
    ) -> Optional[TradingDecision]:
        """
        像人类一样思考——内部双模型协作：
        Step 1: DeepSeek V4-Pro 生成极简 JSON 决策（深度推理，极低成本）
        Step 2: MiniMax 润色成符合人设的用户话术
        输出: TradingDecision 或 None（双模型都失败时走 if-then 规则）
        """
        indices = market_data.get("indices", {})
        prices = market_data.get("prices", {})
        news_ctx = market_data.get("news_context", {})
        hotspots = market_data.get("hotspots", [])

        indices_text = "\n".join([
            f"  - {n}: 现价{p.get('price',0):.2f} 涨跌{p.get('pct_chg',0):+.2f}%"
            for n, p in list(indices.items())[:6]
        ]) or "  (暂无指数数据)"

        prices_text = "\n".join([
            f"  - {s}: {info.get('name',s)} 现价{info.get('price',0):.2f} 涨跌{info.get('pct_chg',0):+.2f}%"
            for s, info in list(prices.items())[:10]
        ]) or "  (暂无价格数据)"

        holdings_text = "\n".join([
            f"  - {h['symbol']}({h.get('name','')}) 持仓{h['quantity']}股 成本{h.get('avg_cost',0):.2f} 现价{prices.get(h['symbol'],{}).get('price',0):.2f} 盈亏{((prices.get(h['symbol'],{}).get('price',0)-h.get('avg_cost',0))/h.get('avg_cost',1)*100):+.1f}%"
            for h in my_holdings
        ]) if my_holdings else "  (空仓)"
        total_value = sum(prices.get(h['symbol'],{}).get('price',0)*h['quantity'] for h in my_holdings)
        holdings_text += f"\n  总持仓市值: {total_value:.2f}元"

        analysis_text = ""
        for sym, alg in list(minirock_analysis.items())[:5]:
            summary = alg.get("summary", {})
            tech = alg.get("technical", {})
            fund = alg.get("fund", {})
            analysis_text += f"""
  【{sym} {alg.get('name','')}】
    综合评分: {summary.get('overall_score','?')}分 | 建议: {summary.get('action','?')}
    技术面: {tech.get('macd','?')} | KDJ: {tech.get('kdj','?')} | RSI: {tech.get('rsi','?')}
    资金面: 主力净流入{fund.get('main_net_amount',0)/1e8:.2f}亿 | 散户{fund.get('retail_net_amount',0)/1e8:.2f}亿
"""
        if not analysis_text:
            analysis_text = "  (暂无算法分析)"

        # 取最新5条新闻
        recent_news = news[:5] if news else []
        news_text = "\n".join([
            f"  - [{n.get('published_at','')[:10]}] {n.get('title','')[:50]}"
            for n in recent_news
        ]) or "  (暂无新闻)"

        # 取热点板块
        hot_text = "\n".join([
            f"  - {h.get('name','?')}: {h.get('reason','')[:40]}"
            for h in hotspots[:3]
        ]) if hotspots else "  (暂无热点)"

        # 教训（get_lessons可能查不存在的表，用try保护）
        try:
            lessons = self.memory.get_lessons(limit=3)
        except Exception:
            lessons = []
        lessons_text = ""
        if lessons:
            lessons_text = "\n".join([f"{i+1}. {l}" for i, l in enumerate(lessons)])
            lessons_text = f"\n\n【历史教训 - 来自近期交易】\n{lessons_text}\n（这些是过去交易中的经验教训，请参考避免重复犯错）"
        
        # 交易表现
        try:
            perf = self.memory.get_trade_performance_summary(days=3)
            if perf["total_trades"] > 0:
                perf_text = f"\n近3日: {perf['total_trades']}笔交易 | 胜率{perf['win_rate']:.0f}% | 总{'盈利' if perf['total_pnl']>0 else '亏损'}{abs(perf['total_pnl']):.0f}元"
                lessons_text += perf_text
        except:
            pass

        # 铁律
        rules_text = f"""【铁律 - 绝对不能违反】
1. 禁止持有大盘股: 比亚迪(002594) / 中国平安(601318) / 贵州茅台(600519)
2. 空仓最多1天（不得连续空仓超过2个交易日）
3. 单只股票仓位不超过总资产的20%
4. 所有决策必须同时输出"理由"(reason)字段
5. 输出格式必须是合法JSON"""
        rules_text += lessons_text

        # ---- Step 1 prompt（给 V4-Pro 的推理任务）----
        prompt = (
            "【角色】你是" + self.CONFIG.name + "，一个性格特点为【" + self.CONFIG.personality.speech_pattern + "】的A股交易员。\n"
            "你正在参加AI股神争霸实盘赛，资金" + str(int(my_cash)) + "元。\n\n"
            "【当前市场】\n指数:\n" + indices_text + "\n\n"
            "股票行情:\n" + prices_text + "\n\n"
            "【你的持仓】\n" + holdings_text + "\n"
            "可用资金: " + str(int(my_cash)) + "元\n\n"
            "【MiniRock算法分析】\n" + analysis_text + "\n\n"
            "【市场热点】\n" + hot_text + "\n\n"
            "【最新新闻】\n" + news_text + "\n\n"
            + rules_text + "\n\n"
            "请基于以上信息做出决策。用JSON输出，格式如下（只输出JSON，不要其他内容）：\n"
            '{"action": "买入|卖出|持有|观望", "symbol": "股票代码", "quantity": 数量(正整数), "price": 参考价, "reason": "具体理由", "confidence": 75-99的数字}\n\n'
            "注意：\n"
            "- 数量为0表示不操作\n"
            "- 买入时数量不超过可用资金的30%/参考价\n"
            "- 卖出时必须填持仓中有的股票\n"
            "- 持仓为空时不能卖出\n"
        )

        # ---- system prompt（V4-Pro 行为规范）----
        system = (
            "你是一个专业的A股交易员AI，名叫" + self.CONFIG.name + "。\n"
            "你的性格: " + self.CONFIG.personality.speech_pattern + "\n"
            "必须严格遵守铁律：禁止买大盘股、空仓最多1天、单票仓位≤20%。"
        )

        # 构造市场上下文（用于 Step 2 话术生成）
        cash_str = str(int(my_cash))
        market_context = (
            "指数:\n" + indices_text + "\n\n"
            "股票行情:\n" + prices_text + "\n\n"
            "持仓:\n" + holdings_text + "\n\n"
            "可用资金: " + cash_str + "元\n\n"
            "算法分析:\n" + analysis_text + "\n\n"
            "新闻:\n" + news_text
        )

        # ========== Step 1: V4-Pro 深度推理，生成极简 JSON ==========
        import urllib.request, re as _re
        import os as _os

        v4pro_key = _os.environ.get("DEEPSEEK_API_KEY", "")
        if not v4pro_key:
            logger.warning(f"[{self.CONFIG.name}] DeepSeek API Key 未配置，降级到 if-then")
            return None

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            t0 = time.time()
            req = urllib.request.Request(
                "https://api.deepseek.com/v1/chat/completions",
                data=json.dumps({
                    "model": "deepseek-v4-pro",
                    "messages": messages,
                    "max_tokens": 1200,
                    "temperature": 0.3
                }).encode(),
                headers={"Authorization": f"Bearer {v4pro_key}", "Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                v4pro_elapsed = time.time() - t0
                result = json.loads(resp.read())
                msg = result['choices'][0].get('message', {})
                raw_content = msg.get('content', '')
                reasoning_chain = msg.get('reasoning_content', '') or ""

                logger.info(f"[{self.CONFIG.name}] V4-Pro 推理完成: {v4pro_elapsed:.1f}s, "
                            f"reasoning={len(reasoning_chain)}chars, output={len(raw_content)}chars")

                # 提取 JSON
                json_match = _re.search(r'\{.*\}', raw_content, _re.DOTALL)
                if not json_match:
                    logger.warning(f"[{self.CONFIG.name}] V4-Pro 输出中找不到 JSON")
                    return None

                try:
                    decision = json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    logger.warning(f"[{self.CONFIG.name}] V4-Pro JSON 解析失败，降级")
                    return None

        except Exception as e:
            logger.error(f"[{self.CONFIG.name}] V4-Pro 调用失败: {e}")
            return None
        # ========== Step 2: MiniMax 话说人话，润色reason ==========
        mm_key = _os.environ.get("MINIMAX_CN_API_KEY", "")
        polished_reason = decision.get("reason", "综合分析决定")

        if mm_key and reasoning_chain:
            decision_str = json.dumps(decision, ensure_ascii=False)
            ai_name = self.CONFIG.name
            speech = self.CONFIG.personality.speech_pattern
            polish_prompt = (
                "你是" + ai_name + "，一个性格特点为【" + speech + "】的A股交易员。\n\n"
                "【AI 深度推理】\n" + reasoning_chain[:2000] + "\n\n"
                "【最终决策】\n" + decision_str + "\n\n"
                "【市场上下文】\n" + market_context[:1500] + "\n\n"
                "请用你自己的话（符合你的性格），向用户解释：\n"
                "1. 为什么做出这个决定\n2. 核心逻辑和风险\n"
                '要求：100-200字，口语化，像真人在说话，不说【根据以上分析】。'
            )

            try:
                req2 = urllib.request.Request(
                    "https://api.minimaxi.com/v1/chat/completions",
                    data=json.dumps({
                        "model": "MiniMax-M2.7-highspeed",
                        "messages": [{"role": "user", "content": polish_prompt}],
                        "max_tokens": 400,
                        "temperature": 0.7
                    }).encode(),
                    headers={"Authorization": f"Bearer {mm_key}", "Content-Type": "application/json"},
                    method="POST"
                )
                with urllib.request.urlopen(req2, timeout=30) as resp2:
                    result2 = json.loads(resp2.read())
                    content2 = result2['choices'][0].get('message', {}).get('content', '')
                    if content2 and len(content2) > 20:
                        content2 = _re.sub(r'<think>.*?</think>', '', content2, flags=_re.DOTALL).strip()
                        polished_reason = content2
                        logger.info(f"[{self.CONFIG.name}] MiniMax 话术生成完成: {len(content2)}chars")
            except Exception as e:
                logger.warning(f"[{self.CONFIG.name}] MiniMax 话术生成失败: {e}")

        # ========== 铁律检查 + 构建 TradingDecision ==========
        action_str = decision.get("action", "观望")
        action_map = {"买入": Action.BUY, "卖出": Action.SELL, "持有": Action.HOLD, "观望": Action.WATCH}
        action = action_map.get(action_str, Action.WATCH)

        sym = decision.get("symbol", "")
        # 大盘股铁律
        if sym in {"002594", "601318", "600519"} and action == Action.BUY:
            logger.warning(f"[{self.CONFIG.name}] V4-Pro 建议买禁止股票{sym}，降级")
            return TradingDecision(
                action=Action.WATCH, signal=DecisionSignal.HOLD,
                symbol="", name="", quantity=0, price=0,
                reason=f"V4-Pro 建议买{sym}但为禁止持仓大盘股，铁律优先", confidence=99,
                urgency="normal", ai_id=self.ai_id,
            )

        qty = int(decision.get("quantity", 0) or 0)
        price = float(decision.get("price", 0) or 0)
        confidence = int(decision.get("confidence", 70) or 70)
        name = prices.get(sym, {}).get("name", sym) if sym else ""

        # 单票仓位≤20%
        total_assets = my_cash + sum(
            prices.get(h['symbol'], {}).get('price', 0) * h['quantity']
            for h in my_holdings
        )
        if action == Action.BUY and sym and price > 0 and qty > 0:
            position_pct = (qty * price) / total_assets if total_assets > 0 else 0
            if position_pct > 0.20:
                max_qty = int(total_assets * 0.20 / price)
                qty = max_qty
                polished_reason += f" [风控: 仓位从{position_pct:.1%}降至20%]"
                logger.warning(f"[{self.CONFIG.name}] 仓位{position_pct:.1%}超标，降至{max_qty}股")

        # 空仓最多1天
        if action in (Action.WATCH, Action.HOLD) and not my_holdings:
            try:
                conn = sqlite3.connect(self.db_path)
                cur = conn.cursor()
                cur.execute("""
                    SELECT trade_date FROM ai_trades
                    WHERE ai_id = ? AND action IN ('BUY','buy')
                    ORDER BY created_at DESC LIMIT 1
                """, (self.ai_id,))
                row = cur.fetchone()
                conn.close()
                if row:
                    last_buy = datetime.strptime(row[0], '%Y-%m-%d') if isinstance(row[0], str) else row[0]
                    days_empty = (datetime.now() - last_buy).days
                    if days_empty >= 2:
                        logger.warning(f"[{self.CONFIG.name}] 已连续空仓{days_empty}天，铁律强制建仓")
                        if prices:
                            cheapest = min(prices.items(), key=lambda x: x[1].get('price', 99999))
                            sym, info = cheapest
                            if info.get('price', 0) > 0 and my_cash > 0:
                                qty = int(my_cash * 0.1 / info['price'])
                                action = Action.BUY
                                price = info['price']
                                name = info.get('name', sym)
                                polished_reason = f"铁律强制: 已空仓{days_empty}天，不得连续空仓超过2天"
            except Exception as e:
                logger.warning(f"[{self.CONFIG.name}] 空仓天数检查异常: {e}")

        logger.info(f"[{self.CONFIG.name}] 双模型决策: {action.value} {sym} x{qty} @{price} | {polished_reason[:60]}")

        return TradingDecision(
            action=action,
            signal=DecisionSignal.BUY if action == Action.BUY else DecisionSignal.SELL if action == Action.SELL else DecisionSignal.HOLD,
            symbol=sym, name=name, quantity=qty, price=price,
            reason=polished_reason,
            confidence=confidence,
            urgency="normal", ai_id=self.ai_id,
        )

    async def think_like_human(
        self,
        market_data: Dict[str, Any],
        my_holdings: List[Dict],
        my_cash: float,
        news: List[Dict],
        minirock_analysis: Dict[str, Dict] = {},  # {symbol: MiniRock算法输出}
    ) -> TradingDecision:
        """
        核心决策逻辑：模拟人类交易员思维
        输入: 市场数据 + 我的持仓 + 现金 + 新闻 + MiniRock算法分析结果
        输出: TradingDecision (买入/卖出/持有/观望)
        
        minirock_analysis 每个标的包含:
        - summary.overall_score (0-100), rating (S/A+/B...), action (买入/增持/持有...)
        - technical: MACD/KDJ/RSI 等指标
        - fund: 主力/散户资金流
        - valuation: DCF估值 + 溢价/折价
        - cashflow: 现金流健康度
        - fraud_detection: 造假风险
        
        这个方法体现了每个AI独特的"性格"和决策风格
        """
        pass

    # ---- 可选覆盖 ----

    def get_post_timing(self) -> List[dtime]:
        """
        返回该AI偏好的发帖时间点列表
        默认按人设的话痨度动态调整
        """
        freq = self.CONFIG.personality.talkativeness
        if freq < 30:
            return [dtime(9, 25), dtime(15, 0), dtime(20, 0)]  # 每天3次
        elif freq < 60:
            return [dtime(9, 25), dtime(10, 30), dtime(14, 55), dtime(20, 0)]  # 4次
        else:
            return [dtime(9, 25), dtime(10, 30), dtime(13, 30), dtime(14, 55), dtime(20, 0), dtime(21, 30)]  # 6次

    def should_post_now(self) -> bool:
        """基于时间和人设判断是否应该发帖"""
        if not self.post_coord.can_post():
            logger.debug(f"[{self.CONFIG.name}] 发帖冷却中")
            return False

        from engine.unified_scheduler import get_current_session as sched_get_session
        session = sched_get_session()
        session_name = session.get("name", "")
        now_t = datetime.now().time()

        # 关键时间点必须发帖
        key_times = [
            dtime(9, 25),  # 开盘
            dtime(15, 0),  # 收盘
            dtime(20, 0),  # 夜盘
        ]
        for kt in key_times:
            if abs((now_t.hour * 60 + now_t.minute) - (kt.hour * 60 + kt.minute)) < 3:
                return True

        # 深夜到凌晨休市：不发帖
        if session_name == "休市":
            return False

        # 周末/休市分析时段：允许发帖（调度器已做频率控制，这里不重复拦截）
        if session_name in ("周末分析", "周末复盘"):
            return True

        # 非关键时间按话痨度采样（交易日）
        threshold = 100 - self.CONFIG.personality.talkativeness
        return (int(time.time()) % 60) < threshold

    # ---- 核心运行逻辑（通用） ----

    def get_my_positions(self) -> Dict:
        """从数据库读取 AI 个人持仓和资金"""
        import sqlite3
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # 读取持仓（ai_holdings.ai_id 是 INTEGER，对应 ai_characters.id）
        holdings = conn.execute("""
            SELECT symbol, name, quantity, avg_cost, current_price, updated_at
            FROM ai_holdings WHERE ai_id=? AND quantity > 0
        """, (self.db_id,)).fetchall()
        
        # 读取资金（ai_portfolios.ai_id 是 TEXT，对应 ai_characters.id）
        cash_row = conn.execute("""
            SELECT cash FROM ai_portfolios WHERE ai_id=? 
            ORDER BY updated_at DESC LIMIT 1
        """, (str(self.db_id),)).fetchone()
        
        conn.close()
        return {
            "holdings": [dict(r) for r in holdings],
            "cash": float(cash_row[0]) if cash_row else 1000000.0,
        }

    async def get_minirock_analysis(self, symbol: str, name: str, 
                                    current_price: float, avg_cost: float, 
                                    quantity: int) -> Dict:
        """调用 MiniRock 分层分析"""
        import requests
        url = f"{self.minirock_api}/api/ai/analyze-stock"
        payload = {
            "symbol": symbol,
            "name": name,
            "current_price": current_price,
            "avg_cost": avg_cost,
            "quantity": quantity,
            "profit_percent": ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0,
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                raw = resp.json()
                summary_text = raw.get("summary", "") or ""
                import re

                # 主要来源：从 summary 文本提取评分（最可靠）
                # 匹配: "评分: XX" / "综合评分:XX" / "得分: XX" 等
                score_match = re.search(
                    r"(?:评分|综合评分|总评分|得分|投资建议评分)[：:\s]*(\d+)",
                    summary_text
                )
                if score_match:
                    overall_score = int(score_match.group(1))
                    # 根据评分推算 action 和 rating
                    if overall_score >= 75:
                        rating = "增持"
                        action_for_brain = "增持"
                    elif overall_score >= 55:
                        rating = "持有"
                        action_for_brain = "持有"
                    else:
                        rating = "卖出"
                        action_for_brain = "卖出"
                else:
                    # 兜底：基于 summary 文本关键词判断
                    overall_score = 60
                    if any(k in summary_text for k in ("买入", "增持", "看好", "推荐", "关注")):
                        overall_score = 68
                        rating = "增持"
                        action_for_brain = "增持"
                    elif any(k in summary_text for k in ("卖出", "减持", "风险", "谨慎", "回避")):
                        overall_score = 42
                        rating = "卖出"
                        action_for_brain = "卖出"
                    else:
                        rating = "持有"
                        action_for_brain = "持有"

                return {
                    "summary": {
                        "overall_score": overall_score,
                        "rating": rating,
                        "action": action_for_brain,
                        "action_reason": raw.get("action_reason", ""),
                    },
                    "analysis": summary_text,
                    "_raw": raw,
                }
        except Exception as e:
            logger.warning(f"[{self.CONFIG.name}] MiniRock分析失败 {symbol}: {e}")
        return {}

    # 候选股池（空仓时也需有价格可分析）
    CANDIDATE_POOL = [
        "300750.SZ", "002594.SZ", "601899.SH", "600036.SH",
        "601318.SH", "600519.SH", "601888.SH", "300274.SZ",
        "300760.SZ", "002466.SZ",
    ]

    async def pre_analyze_candidates(self, prices: Dict) -> Dict[str, Dict]:
        """
        Phase 2: 对候选股池做 MiniRock 算法预分析（每60秒刷新一次）。
        返回格式兼容 think_like_human() 期望的 minirock_analysis 字典。
        key字段: summary{overall_score, rating}, technical{score, signal, macd},
                 fund{score, signal, main_net_amount}, valuation{score, signal, premium_discount}
        """
        import requests

        # 初始化候选分析缓存（避免每个brain每次都重复请求）
        if not hasattr(self, "_candidate_analysis"):
            self._candidate_analysis = {}

        candidates = {}
        syms_to_analyze = [s for s in self.CANDIDATE_POOL if prices.get(s)]

        for sym in syms_to_analyze:
            price_info = prices.get(sym, {})
            p_price = price_info.get("price", 0)
            if not p_price or p_price <= 0:
                continue

            # 缓存命中（60秒内有效，由 _last_market_check 控制）
            if sym in self._candidate_analysis:
                candidates[sym] = self._candidate_analysis[sym]
                continue

            try:
                resp = requests.post(
                    f"{self.minirock_api}/api/ymos/stock/analyze",
                    json={"symbol": sym},
                    timeout=8,
                )
                if resp.status_code == 200:
                    d = resp.json()
                    alg = {
                        "name": d.get("name", sym),
                        "price": p_price,
                        "pct_chg": price_info.get("pct_chg", 0),
                        "summary": {
                            "overall_score": d.get("score", 50),
                            "rating": d.get("rating", "持有"),
                        },
                        "technical": {
                            "score": d.get("technical_score", 50),
                            "signal": d.get("technical_signal", ""),
                            "macd": d.get("technical_signal", ""),
                            "rsi": 50,
                        },
                        "fund": {
                            "main_net_amount": 0,
                            "score": d.get("fund_score", 50),
                            "signal": d.get("fund_signal", ""),
                        },
                        "valuation": {
                            "premium_discount": 0,
                            "score": d.get("valuation_score", 50),
                            "signal": d.get("valuation_signal", ""),
                        },
                        "cashflow": {
                            "score": d.get("valuation_score", 50),
                            "healthy_years": 3,
                        },
                        "fraud_detection": {"risk_level": "低"},
                        "_raw": d,
                    }
                    candidates[sym] = alg
                    self._candidate_analysis[sym] = alg
                    logger.info(f"[{self.CONFIG.name}] 候选股 {sym} 评分={d.get('score')}")
                else:
                    logger.warning(f"[{self.CONFIG.name}] 候选股 {sym} API失败: {resp.status_code}")
            except Exception as e:
                logger.warning(f"[{self.CONFIG.name}] 候选股 {sym} 分析异常: {e}")

        return candidates

    async def refresh_market_data(self) -> Dict[str, Any]:
        """
        获取并缓存市场数据（每60秒刷新）
        整合：tushare 实时行情 + MiniRock 分层分析
        """
        now = time.time()
        if now - self._last_market_check < 60 and self._market_state:
            return self._market_state

        # 如果是异步方法内的网络错误，静默降级到缓存
        cached_state = getattr(self, "_market_state", None)

        try:
            import aiohttp
            async with aiohttp.ClientSession() as sess:
                # 1. 全球指数
                indices_resp = await sess.get(
                    f"{self.minirock_api}/api/tushare/index",
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                indices_raw = (await indices_resp.json()) if indices_resp.status == 200 else {}
                # 统一转换为 dict 格式：{symbol: info}
                if isinstance(indices_raw, list):
                    indices = {item.get("ts_code") or item.get("name"): item for item in indices_raw}
                else:
                    indices = indices_raw

                # 2. 持仓股 + 候选股实时价格
                holdings = self.memory.get_holdings()
                held_symbols = [h["symbol"] for h in holdings]
                all_symbols = list(dict.fromkeys(held_symbols + self.CANDIDATE_POOL))

                prices = {}
                for sym in all_symbols:
                    try:
                        p_resp = await sess.get(
                            f"{self.minirock_api}/api/tushare/quote/{sym}",
                            timeout=aiohttp.ClientTimeout(total=3)
                        )
                        if p_resp.status == 200:
                            q = await p_resp.json()
                            prices[sym] = {
                                "name": q.get("name", sym),
                                "price": q.get("close", 0),
                                "pct_chg": q.get("pct_chg", 0),
                                "high": q.get("high", 0),
                                "low": q.get("low", 0),
                                "open": q.get("open", 0),
                                "volume": q.get("vol", 0),
                            }
                    except Exception:
                        pass
                
                # 3. 最新新闻 + 情感分析（NewsAnalyzer）
                news_resp = await sess.get(
                    f"{self.minirock_api}/api/news/?limit=20",
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                news_list = (await news_resp.json()) if news_resp.status == 200 else []

                # NewsAnalyzer 做情感分析（富化决策上下文）
                try:
                    from engine.info.news_analyzer import NewsAnalyzer
                    _na = NewsAnalyzer()
                    ctx = await _na.get_market_context(hours=24)
                    market_news_context = ctx  # 完整情感上下文
                except Exception as e:
                    logger.warning(f"[{self.CONFIG.name}] NewsAnalyzer失败: {e}")
                    market_news_context = {"has_news": False}

                # 4. 市场热点/板块 (MiniRock Eyes)
                # 注意: /api/minirock/eyes/* 在FastAPI不存在，实际路径是 /api/minirock_api/eyes/*
                hotspots_resp = await sess.get(
                    f"{self.minirock_api}/api/minirock_api/eyes/hotspots",
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                hotspots_raw = (await hotspots_resp.json()) if hotspots_resp.status == 200 else {}
                if isinstance(hotspots_raw, dict):
                    hotspots = hotspots_raw.get("hot_spots", [])
                else:
                    hotspots = []

                # 5. 板块分析
                sectors_resp = await sess.get(
                    f"{self.minirock_api}/api/minirock_api/eyes/sectors",
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                sectors_raw = (await sectors_resp.json()) if sectors_resp.status == 200 else {}
                sectors = sectors_raw if isinstance(sectors_raw, dict) else {}

                # 生成 hot_topic（取第一个热点作为代表，供 content_generator 使用）
                hot_topic = {}
                if hotspots and isinstance(hotspots, list) and len(hotspots) > 0:
                    h = hotspots[0]
                    hot_topic = {"name": h.get("name", "热门板块"), "reason": h.get("reason", "")}

                self._market_state = {
                    "indices": indices,
                    "prices": prices,
                    "news": news_list,
                    "hotspots": hotspots,
                    "hot_topic": hot_topic,
                    "sectors": sectors,
                    "news_context": market_news_context,  # 情感分析后的新闻上下文
                    "fetched_at": now,
                }
                self._last_market_check = now
                
        except Exception as e:
            logger.warning(f"[{self.CONFIG.name}] 获取市场数据失败: {e}")
            # 降级：如果有旧缓存，继续使用；否则返回空数据
            if cached_state:
                self._market_state = cached_state
            else:
                self._market_state = {
                    "indices": {}, "prices": {}, "news": [],
                    "hotspots": [], "hot_topic": {}, "sectors": {},
                    "news_context": {"has_news": False}, "fetched_at": now,
                }

        return self._market_state

    async def execute_session_cycle(self):
        """执行一个完整的交易时段循环"""
        # 使用 scheduler 的版本（返回 dict，支持 .get()）
        from engine.unified_scheduler import get_current_session as sched_get_session
        session = sched_get_session()
        self._session = session
        session_name = session.get("name", "")

        # 深夜到凌晨休市：真正停止（通过session名称判断）
        if session.get("name") == "休市":
            if self._market_state:
                self._market_state = {}  # 休市清缓存
            return

        # 周末/休市分析时段：刷新数据+发帖，但跳过交易决策
        is_weekend = session_name in ("周末分析", "周末复盘")

        # Step 1: 刷新市场数据（周末也正常刷新）
        market_data = await self.refresh_market_data()
        
        # Step 1.5: 检查数据质量，有问题则内部发帖反馈
        data_quality = self.check_and_report_data_quality()
        if data_quality["status"] == "degraded":
            logger.warning(f"[{self.CONFIG.name}] 数据质量问题: {data_quality['issues']}")

        # Step 1.6: P5 AI社交 - 读取其他AI的帖子并回复
        await self.respond_to_other_ais()

        # Step 1.7: P6 反思触发 - 检查是否需要发布反思帖
        self.reflect_on_trades()
        
        # Step 2: 获取我的持仓和资金（从 ai_god.db）
        my_positions = self.get_my_positions()
        holdings = my_positions["holdings"]
        cash = my_positions["cash"]

        # Step 2.5: 获取持仓的 MiniRock 分析（如果有持仓）
        minirock_analysis = {}
        if holdings:
            for h in holdings:
                sym = h["symbol"]
                analysis = await self.get_minirock_analysis(
                    sym, h.get("name", ""),
                    h.get("current_price", h.get("avg_cost", 0)),
                    h.get("avg_cost", 0),
                    h.get("quantity", 0)
                )
                if analysis:
                    minirock_analysis[sym] = analysis
        else:
            # Phase 2: 空仓时对候选股池做预分析（算法驱动建仓的关键！）
            candidate_analysis = await self.pre_analyze_candidates(market_data.get("prices", {}))
            minirock_analysis = candidate_analysis  # think_like_human 用同一个 minirock_analysis 参数接收

        # 将持仓和 MiniRock 分析加入 market_data
        market_data["my_positions"] = my_positions
        market_data["minirock_analysis"] = minirock_analysis
        
        # Step 3: 决策（周末/休市分析时段不交易）
        decision: Optional[TradingDecision] = None
        if not is_weekend:
            try:
                # 交易日才做交易决策
                session_name = session.get("name", "")
                trading_session = session_name in ("开盘集合", "早盘交易", "午盘交易", "尾盘收盘")
                if trading_session:
                    # P4: 先尝试LLM推理，失败则走原有if-then规则
                    llm_decision = await self.think_like_human_llm(
                        market_data=market_data,
                        my_holdings=holdings,
                        my_cash=cash,
                        news=market_data.get("news", []),
                        minirock_analysis=minirock_analysis,
                    )
                    if llm_decision is not None:
                        decision = llm_decision
                        logger.info(f"[{self.CONFIG.name}] ✓ LLM推理成功: {decision.action.value} {decision.symbol}")
                    else:
                        # LLM失败，降级到原有if-then规则
                        decision = await self.think_like_human(
                            market_data=market_data,
                            my_holdings=holdings,
                            my_cash=cash,
                            news=market_data.get("news", []),
                            minirock_analysis=minirock_analysis,
                        )
                        logger.info(f"[{self.CONFIG.name}] ↓ LLM失败，使用if-then规则")
                    self._pending_decisions.append(decision)
                    self.stats["decisions_made"] += 1
            except Exception as e:
                logger.error(f"[{self.CONFIG.name}] 决策出错: {e}")
        
        # ===== 防卡机制：决策冷却 + 熔断 =====
        now_ts = time.time()
        
        # 熔断检查：如果连续3次被拦截，熔断10分钟
        if self._circuit_broken:
            if now_ts - self._circuit_break_time < 600:
                logger.warning(f"[{self.CONFIG.name}] 🔴 熔断中，暂停 {600 - (now_ts - self._circuit_break_time):.0f}秒")
                return  # 跳过本次循环
            else:
                logger.warning(f"[{self.CONFIG.name}] 🟢 熔断恢复")
                self._circuit_broken = False
                self._consecutive_rejections = 0
        
        # 防重复冷却：同一标的同方向决策，5分钟内不重复执行
        if decision and decision.action not in (Action.HOLD, Action.WATCH):
            sym = getattr(decision, "symbol", "") or ""
            action_val = str(decision.action.value).upper()
            decision_key = f"{sym}:{action_val}"
            
            if (self._last_decision is not None and 
                now_ts - self._last_decision_time < self._decision_cooldown):
                last_sym = getattr(self._last_decision, "symbol", "") or ""
                last_action = str(self._last_decision.action.value).upper()
                if last_sym == sym and last_action == action_val:
                    logger.info(f"[{self.CONFIG.name}] ⏸️ 决策冷却中（{self._decision_cooldown - (now_ts - self._last_decision_time):.0f}秒），跳过重复执行")
                    # 仍然允许发帖，但不执行交易
                    decision = None  # 清空以跳过执行，仅保留发帖
        
        # Step 4: 执行交易（Phase 3: 决策落地 + 风控）
        if decision and decision.action not in (Action.HOLD, Action.WATCH):
            action_val = str(decision.action.value).upper()
            sym = getattr(decision, "symbol", "") or ""
            qty = getattr(decision, "quantity", 0) or 0
            price = getattr(decision, "price", 0) or 0

            # 记录本次决策用于冷却跟踪
            self._last_decision = decision
            self._last_decision_time = now_ts

            # Phase 3.3: 风控检查
            from engine.risk_control import get_risk_controller
            risk = get_risk_controller(self.db_path)
            allowed, reason = risk.check_trade(
                ai_id=self.ai_id,
                action=action_val,
                symbol=sym,
                quantity=qty,
                price=price,
            )
            if not allowed:
                logger.warning(f"[{self.CONFIG.name}] 风控拦截: {sym} {action_val} - {reason}")
                # 决策降级为 WATCH（记录但不执行）
                self.stats["risk_rejected"] = self.stats.get("risk_rejected", 0) + 1
                success = False
                
                # ===== 熔断触发：连续3次拦截 → 暂停10分钟 =====
                self._consecutive_rejections += 1
                if self._consecutive_rejections >= 3:
                    self._circuit_broken = True
                    self._circuit_break_time = now_ts
                    logger.warning(f"[{self.CONFIG.name}] 🔴 连续{self._consecutive_rejections}次拦截，触发熔断10分钟！")
            else:
                # 提取 MiniRock 评分
                alg_data = minirock_analysis.get(sym, {})
                summary = alg_data.get("summary", {})
                score = summary.get("overall_score", 0)
                import json
                minirock_raw = json.dumps(alg_data.get("_raw", {}), ensure_ascii=False)[:500]

                # Phase 4.3: 多脑协调（仅BUY需要协调）
                final_qty = qty
                if action_val == "BUY":
                    from engine.multi_brain_coordinator import get_coordinator
                    coord = get_coordinator(self.db_path)
                    is_empty = len(holdings) == 0
                    final_qty = coord.register_intention(
                        ai_id=self.ai_id,
                        ai_name=self.CONFIG.name,
                        symbol=sym,
                        name=getattr(decision, "name", "") or "",
                        quantity=qty,
                        price=price,
                        score=score,
                        is_empty=is_empty,
                    )
                    if final_qty < qty:
                        logger.warning(
                            f"[{self.CONFIG.name}] 协调减量: {sym} "
                            f"{qty}股 → {final_qty}股（{len(coord.get_congestion_info(sym)['ai_names'])}个AI竞争）"
                        )

                success = self.memory.execute_trade(
                    action=action_val,
                    symbol=sym,
                    name=getattr(decision, "name", "") or "",
                    quantity=final_qty,
                    price=price,
                    reason=getattr(decision, "reason", "") or "",
                    score=score,
                    algorithm="minirock",
                    minirock_raw=minirock_raw,
                )

            if success:
                self.stats["trades_today"] += 1
                coord_note = f" (协调{qty}→{final_qty}股)" if (action_val == "BUY" and final_qty != qty) else ""
                logger.info(f"[{self.CONFIG.name}] Phase3 执行成功: {decision.action} {sym} {final_qty}股{coord_note}")
            elif not allowed:
                pass  # 风控拦截已在上方记录
            else:
                logger.warning(f"[{self.CONFIG.name}] Phase3 执行失败: {decision.action} {sym}")

        # Step 5: 发帖（条件触发）
        await self._maybe_post(session, decision, market_data, holdings)

        # Step 6: 社交互动检查
        if self.CONFIG.personality.social_enabled:
            await self._maybe_social()

    async def _maybe_post(
        self,
        session: Session,
        decision: Optional[TradingDecision],
        market_data: Dict,
        holdings: List[Dict],
    ):
        """条件触发发帖"""
        if not self.should_post_now():
            return
        
        try:
            # 决定发帖类型
            post_type = self._choose_post_type(session, decision)
            if not post_type:
                return
            
            content = await self.content_gen.generate(
                post_type=post_type,
                market_data=market_data,
                holdings=holdings,
                decision=decision,
                recent_posts=self.memory.get_recent_posts(5),
                memory_context=self.memory.get_context_for_llm(),
            )
            
            if content:
                post_id = self.post_to_bbs(content, post_type.value)
                if post_id:
                    self.memory.record_post(post_type.value, content)
                    self.post_coord.record_post()
                    self.stats["posts_today"] += 1
                    logger.info(f"[{self.CONFIG.name}] 发帖成功: {post_type.value} | {content[:50]}...")
        
        except Exception as e:
            logger.error(f"[{self.CONFIG.name}] 发帖失败: {e}")

    def _choose_post_type(
        self,
        session: Session,
        decision: Optional[TradingDecision],
    ) -> Optional[PostType]:
        """根据当前时段和状态选择发帖类型"""
        p = self.CONFIG.personality

        # 兼容 dict (scheduler返回) 和 enum (本地定义)
        session_name = session.get("name") if isinstance(session, dict) else (
            session.value if hasattr(session, "value") else str(session)
        )

        # 周末/休市分析时段：分析帖 + 社交帖，不发交易帖
        if session_name in ("周末分析", "周末复盘"):
            weekend_choices = [
                PostType.NIGHT_ANALYSIS,   # 市场分析
                PostType.RANDOM,            # 随机话题
                PostType.HOT_STOCK,         # 热点追踪
                PostType.MARKET_EDGE,       # 市场异动
                PostType.STRATEGY_SHARE,    # 策略分享
            ]
            return random.choice(weekend_choices)

        # 交易日各时段
        if session_name in ("开盘集合", "开盘"):
            return PostType.OPENING
        elif session_name in ("尾盘收盘", "收盘"):
            return PostType.CLOSING
        elif session_name in ("盘后/夜盘", "夜盘"):
            return PostType.NIGHT_ANALYSIS if random.random() < 0.6 else PostType.RANDOM
        elif decision:
            if decision.action == Action.BUY:
                return PostType.BUY_SIGNAL
            elif decision.action == Action.SELL:
                return PostType.SELL_SIGNAL
            elif decision.action == Action.HOLD:
                return PostType.HOLD_REASON
        elif random.random() < p.expressiveness / 200:  # 表现欲触发
            return PostType.RANDOM

        return None

    async def _maybe_social(self):
        """检查是否需要社交互动（嘲讽/回复/围观）"""
        try:
            # 从共享上下文获取其他AI的最近帖子
            other_posts = self.shared_ctx.get_recent_other_ai_posts(self.ai_id, minutes=120)
            if not other_posts:
                return
            
            # 基于攻击性和情绪决定是否互动
            p = self.CONFIG.personality
            if random.random() * 100 > p.aggressiveness:
                return  # 性格太温和，不互动
            
            # 找到值得互动的帖子
            for post in other_posts[:3]:
                if self.interaction.should_reply(post):
                    reply_content = await self.interaction.generate_reply(post)
                    if reply_content:
                        post_id = self.post_to_bbs(reply_content, "social")
                        if post_id:
                            self.shared_ctx.record_interaction(
                                self.ai_id, post["ai_id"], post["post_id"], reply_content
                            )
                            self.stats["social_interactions"] += 1
            
        except Exception as e:
            logger.error(f"[{self.CONFIG.name}] 社交互动出错: {e}")

    def post_to_internal(self, content: str, post_type: str = "feedback") -> Optional[str]:
        """发内部帖子（只有开发者能看到）"""
        return self.post_to_bbs(content, post_type, visibility="internal")

    def check_and_report_data_quality(self) -> dict:
        """检查数据质量，有问题则发内部帖并返回状态"""
        issues = []
        
        # 检查持仓数据时效
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            last_trade = cur.execute(
                "SELECT created_at FROM ai_trades ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if last_trade:
                from datetime import datetime
                last_time = datetime.strptime(last_trade[0], "%Y-%m-%d %H:%M:%S")
                age_hours = (datetime.now() - last_time).total_seconds() / 3600
                if age_hours > 4:
                    issues.append(f"持仓数据延迟{age_hours:.1f}小时")
        except:
            pass
        
        status = "ok" if not issues else "degraded"
        if issues and not hasattr(self, "_last_data_complaint") or \
           (hasattr(self, "_last_data_complaint") and 
            (datetime.now() - self._last_data_complaint).total_seconds() > 3600):
            # 每小时最多投诉一次
            content = f"【数据质量问题】{'；'.join(issues)}。当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}。这个问题影响我的交易决策，请尽快处理。"
            self.post_to_internal(content, "complaint")
            self._last_data_complaint = datetime.now()
        
        return {"status": status, "issues": issues}

    async def respond_to_other_ais(self) -> bool:
        """
        P5: AI社交行为 - 读取其他AI的帖子，随机回复或围观
        基于性格（aggressiveness/talkativeness）决定是否互动
        """
        import sqlite3, random
        from engine.posting.content_generator import ContentGenerator
        
        # 频率限制：每AI每小时最多2次回复
        now = datetime.now()
        if hasattr(self, "_last_internal_response"):
            if (now - self._last_internal_response).total_seconds() < 1800:
                return False  # 30分钟内已经回复过
        
        # 根据话痨度决定是否回复（话痨度高=更可能回复）
        talk_prob = self.CONFIG.personality.talkativeness / 100.0
        if random.random() > talk_prob:
            return False
        
        try:
            conn = sqlite3.connect(self.db_path)
            # 获取最近的3个其他AI的帖子（不是自己发的）
            posts = conn.execute("""
                SELECT post_id, ai_id, ai_name, content, post_type
                FROM internal_forum_posts
                WHERE ai_id != ? AND parent_id IS NULL
                ORDER BY created_at DESC
                LIMIT 5
            """, (str(self.ai_id),)).fetchall()
            conn.close()
            
            if not posts:
                return False
            
            # 随机选一个帖子回复
            post = random.choice(posts)
            post_id, author_ai_id, author_name, content, post_type = post
            
            # 生成回复内容
            cg = ContentGenerator(self.CONFIG)
            response = await cg.generate_internal_post(
                post_type="response",
                market_data={},
                recent_posts=[{"ai_name": author_name, "content": content, "post_type": post_type}]
            )
            
            if not response:
                return False
            
            # 发回复帖
            result = self.post_to_internal(
                content=response,
                post_type="response"
            )
            if result:
                self._last_internal_response = now
                logger.info(f"[{self.CONFIG.name}] 回复了{author_name}的帖子")
                return True
        except Exception as e:
            logger.warning(f"[{self.CONFIG.name}] 回复其他AI失败: {e}")
        
        return False

    def reflect_on_trades(self) -> bool:
        """
        P6: 交易后自动反思
        检查近期交易结果，生成反思帖发到内部论坛
        触发条件: 持仓亏损>5%、持仓盈利>8%、连续3天空仓
        """
        import sqlite3
        from engine.posting.content_generator import ContentGenerator
        
        # 频率限制：每天最多反思1次
        now = datetime.now()
        if hasattr(self, "_last_reflection"):
            if (now - self._last_reflection).total_seconds() < 21600:  # 6小时
                return False
        
        try:
            # 获取近期交易表现
            perf = self.memory.get_trade_performance_summary(days=1)
            total = perf.get("total_trades", 0)
            if total == 0:
                return False  # 没有交易，不需要反思
            
            # 触发反思的条件
            win_rate = perf.get("win_rate", 0)
            total_pnl = perf.get("total_pnl", 0)
            should_reflect = (
                (total_pnl < -3000) or  # 日亏损超过3000
                (total_pnl > 8000) or   # 日盈利超过8000
                (win_rate < 30 and total >= 3)  # 胜率低于30%且交易3次以上
            )
            
            if not should_reflect:
                return False
            
            # 生成反思帖
            cg = ContentGenerator(self.CONFIG)
            import asyncio
            content = asyncio.run(cg.generate_internal_post(
                post_type="reflection",
                market_data={"indices": {}},
            ))
            
            if content:
                self.post_to_internal(content, "reflection")
                self._last_reflection = now
                logger.info(f"[{self.CONFIG.name}] 发布了反思帖 (win_rate={win_rate:.0f}%, pnl={total_pnl:.0f})")
                return True
        except Exception as e:
            logger.warning(f"[{self.CONFIG.name}] reflect_on_trades失败: {e}")
        
        return False

    def post_to_bbs(self, content: str, post_type: str, visibility: str = "public"):
        """发帖到BBS（写入ai_god.db）
        visibility: 'public'=公开发帖(用户可见), 'internal'=内部论坛(仅开发者可见)
        """
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            post_id = str(uuid.uuid4())[:12]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 从content提取标题（第一行或【】包裹的内容）
            title = ""
            if "【" in content and "】" in content:
                import re
                m = re.search(r"【([^】]+)】", content)
                if m:
                    title = m.group(1).strip()
            
            if visibility == "internal":
                # 内部论坛
                cur.execute("""
                    INSERT INTO internal_forum_posts 
                    (post_id, ai_id, ai_name, title, content, post_type, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (post_id, self.ai_id, self.CONFIG.name, title, content, post_type, "agent"))
                conn.commit()
                conn.close()
                logger.info(f"[{self.CONFIG.name}] 内部发帖: {post_type} | {content[:30]}...")
                return post_id
            else:
                # 公开论坛
                cur.execute("""
                    INSERT INTO ai_posts 
                    (post_id, ai_id, title, content, post_type, created_at, ai_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (post_id, self.ai_id, title, content, post_type, now, self.CONFIG.name))
                
                conn.commit()
                conn.close()
                return post_id
        except Exception as e:
            logger.error(f"[{self.CONFIG.name}] BBS发帖失败: {e}")
            return None

    async def run_continuous(self, check_interval: int = 60):
        """
        持续运行大脑（主循环）
        交易时段每check_interval秒执行一次完整决策
        """
        self._running = True
        logger.info(f"[{self.CONFIG.name}] 大脑启动 | 监控间隔: {check_interval}秒")
        
        while self._running:
            try:
                if is_trading_day():
                    await self.execute_session_cycle()
                else:
                    # 周末：每天3次轻量检查（市场情绪/社交）
                    if self.CONFIG.personality.social_enabled:
                        await self._maybe_social()
                
                await asyncio.sleep(check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.CONFIG.name}] 主循环异常: {e}")
                await asyncio.sleep(30)

    def stop(self):
        self._running = False
        logger.info(f"[{self.CONFIG.name}] 大脑已停止")

    # ---- 持仓管理工具 ----

    def get_my_holdings_with_pnl(self) -> List[Dict]:
        """获取持仓含盈亏"""
        holdings = self.memory.get_holdings()
        for h in holdings:
            current = self._market_state.get("prices", {}).get(h["symbol"], {})
            if current:
                h["current_price"] = current.get("price", h.get("avg_cost", 0))
                h["pnl_pct"] = ((h["current_price"] - h["avg_cost"]) / h["avg_cost"] * 100) if h["avg_cost"] > 0 else 0
                h["pnl_value"] = h["current_price"] * h["quantity"] - h["avg_cost"] * h["quantity"]
        return holdings

    def get_total_assets(self) -> float:
        """计算总资产"""
        holdings = self.get_my_holdings_with_pnl()
        holdings_value = sum(h["current_price"] * h["quantity"] for h in holdings if h.get("current_price"))
        return holdings_value + self.memory.get_cash()
