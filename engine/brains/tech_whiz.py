"""
韩科捷 - 科技投资大脑
风格：专注科技成长股，关注研发/渗透率/国产替代
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


TECH_WHIZ_CONFIG = CharacterConfig(
    ai_id="tech_whiz",
    db_id=6,  # DB primary key id=6 (韩科捷)
    name="韩科捷",
    emoji="🚀",
    style="科技投资",
    group="灵动小五",
    initial_capital=100000.0,
    description="专注科技成长股，国产替代赛道",
    personality=Personality(
        expressiveness=75, talkativeness=65, aggressiveness=55,
        emotional_stability=60, conformity=40,
        holding_days_min=3, holding_days_max=8,
        position_max_pct=0.40, total_position_max_pct=0.80,
        stop_loss_pct=-6.0, take_profit_pct=12.0, risk_appetite=70,
        vocab_set={"科技", "创新", "研发", "渗透率", "国产替代", "高增长"},
        speech_pattern="热血", post_frequency_cap=5,
    ),
    system_prompt="你是韩科捷，科技投资专家。专注半导体/AI/软件等科技成长赛道。",
    post_keywords=["科技", "半导体", "AI", "国产替代", "渗透率"],
    min_holding_hours=6, social_enabled=True,
)


class TechWhizBrain(BaseBrain):
    """韩科捷 - 科技投资大脑"""
    CONFIG = TECH_WHIZ_CONFIG

    def get_config(self) -> CharacterConfig:
        return self.CONFIG

    async def think_like_human(
        self,
        market_data: Dict[str, Any],
        my_holdings: List[Dict],
        my_cash: float,
        news: List[Dict],
        minirock_analysis: Dict[str, Dict] = {},
    ) -> TradingDecision:
        prices = market_data.get("prices", {})

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
                        reason=f"科技股波动加大，触发止损",
                        confidence=90, urgency="critical", ai_id=self.ai_id,
                    )

        if not my_holdings and my_cash > 10000:
            # 科技股筛选：成交额大 + 今日涨幅 > 2%
            candidates = [
                (s, i) for s, i in prices.items()
                if i.get("pct_chg", 0) >= 2.0 and i.get("amount", 0) > 500000000
            ]
            if candidates:
                sym, info = candidates[0]
                price = info.get("price", 0)
                if price > 0:
                    qty = int((my_cash * 0.40) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=sym, name=info.get("name", sym),
                        quantity=qty, price=price,
                        reason=f"科技赛道：{info.get('name',sym)}涨幅+{info.get('pct_chg',0):.1f}%，成长动量强",
                        confidence=70, urgency="normal", ai_id=self.ai_id,
                    )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="科技逻辑未变" if my_holdings else "等待科技机会",
            confidence=60, ai_id=self.ai_id,
        )
