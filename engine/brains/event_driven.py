"""
沈闻 - 事件驱动大脑
风格：专注催化剂和事件驱动机会（业绩/政策/并购）
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


EVENT_DRIVEN_CONFIG = CharacterConfig(
    ai_id="event_driven",
    name="沈闻",
    emoji="🎯",
    style="事件驱动",
    group="灵动小五",
    initial_capital=100000.0,
    description="事件驱动型投资者，专注催化剂和事件机会",
    personality=Personality(
        expressiveness=65, talkativeness=65, aggressiveness=40,
        emotional_stability=70, conformity=50,
        holding_days_min=2, holding_days_max=7,
        position_max_pct=0.40, total_position_max_pct=0.80,
        stop_loss_pct=-6.0, take_profit_pct=10.0, risk_appetite=65,
        vocab_set={"事件", "催化", "业绩", "政策", "公告", "节点"},
        speech_pattern="理性", post_frequency_cap=4,
    ),
    system_prompt="你是沈闻，事件驱动型投资者。专注业绩公告、政策利好、并购重组等催化剂。",
    post_keywords=["事件", "催化", "业绩", "政策", "公告"],
    min_holding_hours=4, social_enabled=True,
)


class EventDrivenBrain(BaseBrain):
    """沈闻 - 事件驱动大脑"""
    CONFIG = EVENT_DRIVEN_CONFIG

    def get_config(self) -> CharacterConfig:
        return self.CONFIG

    async def think_like_human(self, market_data, my_holdings, my_cash, news):
        prices = market_data.get("prices", {})
        news_list = market_data.get("news", [])

        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            current = price_info.get("price", h.get("avg_cost", 0))
            if current > 0:
                pnl_pct = (current - h["avg_cost"]) / h["avg_cost"] * 100
                if pnl_pct <= -6.0:
                    return TradingDecision(
                        action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                        symbol=sym, name=h.get("name", sym),
                        quantity=h["quantity"], price=current,
                        reason=f"事件驱动失效，触发止损",
                        confidence=90, urgency="critical", ai_id=self.ai_id,
                    )

        # 事件驱动策略：从新闻找催化剂
        if not my_holdings and my_cash > 10000:
            # 找相关新闻的股票
            event_keywords = ["业绩预增", "政策支持", "中标", "合作", "回购"]
            relevant_news = [
                n for n in news_list
                if any(kw in n.get("title", "") for kw in event_keywords)
            ]

            if relevant_news:
                target = relevant_news[0]
                # 从新闻关联到持仓股票
                # 这里简化处理：找相关新闻关联的股票
                candidates = [(s, i) for s, i in prices.items() if i.get("pct_chg", 0) >= 2.0]
                if candidates:
                    sym, info = candidates[0]
                    price = info.get("price", 0)
                    if price > 0:
                        qty = int((my_cash * 0.40) / price / 100) * 100
                        return TradingDecision(
                            action=Action.BUY, signal=DecisionSignal.BUY,
                            symbol=sym, name=info.get("name", sym),
                            quantity=qty, price=price,
                            reason=f"事件催化：{target.get('title', '利好公告')}，事件驱动入场",
                            confidence=75, urgency="high", ai_id=self.ai_id,
                        )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="事件逻辑未变" if my_holdings else "等待事件催化",
            confidence=60, ai_id=self.ai_id,
        )
