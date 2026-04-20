"""
Ryan（瑞恩）/ Mike（迈克）- 动量投资大脑
风格：追涨不抄底，顺势而为，止损快，持仓短
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from typing import Dict, List, Any
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


MOMENTUM_KID_CONFIG = CharacterConfig(
    ai_id="momentum_kid",
    db_id=4,  # DB primary key id=4 (Ryan（瑞恩）)
    name="Ryan（瑞恩）",
    emoji="⚡",
    style="动量投资",
    group="灵动小五",
    initial_capital=100000.0,
    description="动量投资者，追涨不抄底，顺势而为",
    personality=Personality(
        expressiveness=80, talkativeness=60, aggressiveness=70,
        emotional_stability=45, conformity=75,
        holding_days_min=1, holding_days_max=3,
        position_max_pct=0.45, total_position_max_pct=0.85,
        stop_loss_pct=-4.0, take_profit_pct=8.0, risk_appetite=80,
        vocab_set={"动量", "顺势", "爆发", "追", "快进快出"},
        speech_pattern="热血", post_frequency_cap=5,
    ),
    system_prompt="你是Ryan（瑞恩），动量投资风格的短线交易员。",
    post_keywords=["动量", "突破", "加速", "顺势"],
    min_holding_hours=2, social_enabled=True,
)


class MomentumKidBrain(BaseBrain):
    """Ryan - 动量投资大脑"""
    CONFIG = MOMENTUM_KID_CONFIG

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

        # 止损：亏4%就走
        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            current = price_info.get("price", h.get("avg_cost", 0))
            if current > 0:
                pnl_pct = (current - h["avg_cost"]) / h["avg_cost"] * 100
                if pnl_pct <= -4.0:
                    return TradingDecision(
                        action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                        symbol=sym, name=h.get("name", sym),
                        quantity=h["quantity"], price=current,
                        reason=f"动量减弱，止损出局",
                        confidence=90, urgency="critical", ai_id=self.ai_id,
                    )

        # 空仓追涨：今日涨幅 > 3% 的强势股
        if not my_holdings and my_cash > 10000:
            candidates = [(s, i) for s, i in prices.items() if i.get("pct_chg", 0) >= 3.0]
            if candidates:
                sym, info = candidates[0]
                price = info.get("price", 0)
                if price > 0:
                    qty = int((my_cash * 0.45) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=sym, name=info.get("name", sym),
                        quantity=qty, price=price,
                        reason=f"动量信号：{info.get('pct_chg',0):.1f}%涨幅启动，顺势追击",
                        confidence=70, urgency="high", ai_id=self.ai_id,
                    )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="等待动量信号" if my_holdings else "无动量机会，空仓观望",
            confidence=50, ai_id=self.ai_id,
        )
