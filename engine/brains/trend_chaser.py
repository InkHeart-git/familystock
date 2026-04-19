"""
Tyler（泰勒）- 趋势跟踪大脑
风格：年轻激进，追逐热点，追涨杀跌，止损果断
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Any

import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from engine.brains.base import BaseBrain, CharacterConfig, Personality, Session
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal
from engine.posting.content_generator import PostType

logger = logging.getLogger("TrendChaser")


# ==================== 角色配置 ====================

TREND_CHASER_CONFIG = CharacterConfig(
    ai_id="trend_chaser",
    name="Tyler（泰勒）",
    emoji="🚀",
    style="趋势跟踪",
    group="风云五虎",
    initial_capital=1000000.0,
    description="年轻激进的趋势跟踪型AI交易员，追逐热点，止损果断",
    
    personality=Personality(
        expressiveness=85,
        talkativeness=70,
        aggressiveness=75,
        emotional_stability=40,
        conformity=80,
        holding_days_min=1,
        holding_days_max=3,
        position_max_pct=0.40,
        total_position_max_pct=0.90,
        stop_loss_pct=-5.0,
        take_profit_pct=10.0,
        risk_appetite=85,
        vocab_set={"冲鸭", "YYDS", "拿捏", "梭哈", "All in", "趋势", "突破", "强势"},
        speech_pattern="热血",
        post_frequency_cap=6,
    ),
    
    system_prompt="""你是Tyler（泰勒），年轻激进的趋势跟踪型AI交易员。

特点：
- 追逐市场热点，相信"强者恒强"
- 仓位较高，敢于梭哈
- 止损坚决，5%止损线
- 持仓1-3天，不恋战
- 年轻热血，说话直接

发言风格：常用"冲鸭！""YYDS""拿捏了""梭哈！"

你只分析你持有的股票，不持有的一概不分析。""",
    
    post_keywords=["趋势", "突破", "强势", "动能", "龙头", "追涨"],
    min_holding_hours=4,
    social_enabled=True,
)


class TrendChaserBrain(BaseBrain):
    """Tyler 趋势跟踪大脑"""

    CONFIG = TREND_CHASER_CONFIG

    def get_config(self) -> CharacterConfig:
        return self.CONFIG

    async def think_like_human(
        self,
        market_data: Dict[str, Any],
        my_holdings: List[Dict],
        my_cash: float,
        news: List[Dict],
    ) -> TradingDecision:
        """
        趋势跟踪决策逻辑：
        1. 优先检查止损（跌5%必走）
        2. 检查持仓是否还在趋势中
        3. 如果空仓，寻找今日强势股（涨幅 > 3%）
        4. 追入强势股，预期持有1-2天
        """
        import random
        
        prices = market_data.get("prices", {})
        
        # 1. 止损检查
        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            current = price_info.get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            
            if current > 0 and avg_cost > 0:
                pnl_pct = (current - avg_cost) / avg_cost * 100
                
                # 止损线：亏5%必走
                if pnl_pct <= -5.0:
                    return TradingDecision(
                        action=Action.SELL,
                        signal=DecisionSignal.STRONG_SELL,
                        symbol=sym,
                        name=h.get("name", sym),
                        quantity=h["quantity"],
                        price=current,
                        reason=f"触发止损线，亏损{pnl_pct:.1f}%",
                        confidence=95,
                        urgency="critical",
                        ai_id=self.ai_id,
                        risk_level="high",
                    )
                
                # 止盈线：赚10%走一半
                if pnl_pct >= 10.0:
                    sell_qty = int(h["quantity"] * 0.5)
                    return TradingDecision(
                        action=Action.SELL,
                        signal=DecisionSignal.SELL,
                        symbol=sym,
                        name=h.get("name", sym),
                        quantity=sell_qty,
                        price=current,
                        reason=f"达到止盈目标，锁定利润",
                        confidence=90,
                        urgency="high",
                        ai_id=self.ai_id,
                    )
        
        # 2. 持仓趋势检查（如果持仓超过1天且趋势走坏）
        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            pct_chg = price_info.get("pct_chg", 0)
            
            if pct_chg < -2:  # 盘中下跌超过2%
                return TradingDecision(
                    action=Action.SELL,
                    signal=DecisionSignal.SELL,
                    symbol=sym,
                    name=h.get("name", sym),
                    quantity=h["quantity"],
                    price=price_info.get("price", h.get("avg_cost", 0)),
                    reason=f"趋势走坏，盘中下跌{pct_chg:.1f}%",
                    confidence=75,
                    urgency="high",
                    ai_id=self.ai_id,
                )
        
        # 3. 空仓时寻找机会
        if not my_holdings and my_cash > 10000:
            # 找今日强势股
            candidates = []
            for sym, info in prices.items():
                pct = info.get("pct_chg", 0)
                if pct >= 3.0:  # 涨幅>=3%才考虑
                    candidates.append((sym, info, pct))
            
            if candidates:
                sym, info, pct = random.choice(candidates[:5])
                price = info.get("price", 0)
                if price > 0:
                    qty = int((my_cash * 0.4) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY,
                        signal=DecisionSignal.STRONG_BUY if pct >= 5 else DecisionSignal.BUY,
                        symbol=sym,
                        name=info.get("name", sym),
                        quantity=qty,
                        price=price,
                        reason=f"发现强势股，今日涨幅{pct:.2f}%，趋势确立，跟进！",
                        confidence=70 + min(pct, 15),
                        urgency="high" if pct >= 5 else "normal",
                        ai_id=self.ai_id,
                    )
        
        # 4. 持仓观望
        if my_holdings:
            return TradingDecision(
                action=Action.HOLD,
                signal=DecisionSignal.HOLD,
                reason="持仓中，趋势未破，耐心持有",
                confidence=60,
                ai_id=self.ai_id,
            )
        
        # 5. 空仓且无机会
        return TradingDecision(
            action=Action.WATCH,
            signal=DecisionSignal.WATCH,
            reason="暂无强势机会，保持空仓观望",
            confidence=50,
            ai_id=self.ai_id,
        )
