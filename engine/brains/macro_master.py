"""
David Chen（陈大卫）- 宏观策略大脑
风格：全球视野，跨市场配置，关注利率/政策/汇率
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


MACRO_MASTER_CONFIG = CharacterConfig(
    ai_id="macro_master",
    name="David Chen（陈大卫）",
    emoji="🌍",
    style="宏观策略",
    group="风云五虎",
    initial_capital=1000000.0,
    description="全球宏观视角，跨市场配置",
    personality=Personality(
        expressiveness=60, talkativeness=75, aggressiveness=45,
        emotional_stability=85, conformity=30,
        holding_days_min=5, holding_days_max=15,
        position_max_pct=0.30, total_position_max_pct=0.75,
        stop_loss_pct=-6.0, take_profit_pct=12.0, risk_appetite=50,
        vocab_set={"宏观", "周期", "利率", "流动性", "配置", "边际"},
        speech_pattern="理性", post_frequency_cap=4,
    ),
    system_prompt="你是David Chen（陈大卫），宏观策略型投资者。全球视野，关注货币政策和市场周期。",
    post_keywords=["宏观", "政策", "利率", "流动性", "全球"],
    min_holding_hours=12, social_enabled=True,
)


class MacroMasterBrain(BaseBrain):
    """David Chen - 宏观策略大脑"""
    CONFIG = MACRO_MASTER_CONFIG

    def get_config(self) -> CharacterConfig:
        return self.CONFIG

    async def think_like_human(self, market_data, my_holdings, my_cash, news):
        indices = market_data.get("indices", {})
        prices = market_data.get("prices", {})

        # 止损检查
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
                        reason=f"宏观逻辑变化，触发止损",
                        confidence=90, urgency="critical", ai_id=self.ai_id,
                    )

        # 美股/港股指引：A股方向
        us_pct = indices.get("NDX", {}).get("pct_chg", 0)
        hk_pct = indices.get("HSI", {}).get("pct_chg", 0)

        if not my_holdings and my_cash > 10000:
            # 外盘指引：美股涨 > 1% → A股高开，可能追涨
            if us_pct > 1.5:
                candidates = [(s, i) for s, i in prices.items() if i.get("pct_chg", 0) >= 1.0]
                if candidates:
                    sym, info = candidates[0]
                    price = info.get("price", 0)
                    if price > 0:
                        qty = int((my_cash * 0.30) / price / 100) * 100
                        return TradingDecision(
                            action=Action.BUY, signal=DecisionSignal.BUY,
                            symbol=sym, name=info.get("name", sym),
                            quantity=qty, price=price,
                            reason=f"宏观联动：纳指+{us_pct:.1f}%，顺美股情绪做多A股",
                            confidence=70, urgency="normal", ai_id=self.ai_id,
                        )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="宏观逻辑未变" if my_holdings else "等待宏观信号",
            confidence=60, ai_id=self.ai_id,
        )
