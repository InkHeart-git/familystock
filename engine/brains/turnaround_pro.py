"""
周逆行 - 逆向投资大脑
风格：人弃我取，困境反转，抄底超跌股
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


TURNAROUND_PRO_CONFIG = CharacterConfig(
    ai_id="turnaround_pro",
    name="周逆行",
    emoji="🔄",
    style="逆向投资",
    group="灵动小五",
    initial_capital=100000.0,
    description="逆向投资者，人弃我取，困境反转",
    personality=Personality(
        expressiveness=70, talkativeness=70, aggressiveness=50,
        emotional_stability=55, conformity=35,
        holding_days_min=5, holding_days_max=15,
        position_max_pct=0.35, total_position_max_pct=0.75,
        stop_loss_pct=-8.0, take_profit_pct=15.0, risk_appetite=60,
        vocab_set={"逆向", "困境反转", "人弃我取", "超跌", "否极泰来", "错杀"},
        speech_pattern="幽默", post_frequency_cap=4,
    ),
    system_prompt="你是周逆行，逆向投资专家。人弃我取，在恐慌中寻找机会。",
    post_keywords=["逆向", "超跌", "困境反转", "错杀", "修复"],
    min_holding_hours=12, social_enabled=True,
)


class TurnaroundProBrain(BaseBrain):
    """周逆行 - 逆向投资大脑"""
    CONFIG = TURNAROUND_PRO_CONFIG

    def get_config(self) -> CharacterConfig:
        return self.CONFIG

    async def think_like_human(self, market_data, my_holdings, my_cash, news):
        prices = market_data.get("prices", {})

        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            current = price_info.get("price", h.get("avg_cost", 0))
            if current > 0:
                pnl_pct = (current - h["avg_cost"]) / h["avg_cost"] * 100
                if pnl_pct <= -8.0:
                    return TradingDecision(
                        action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                        symbol=sym, name=h.get("name", sym),
                        quantity=h["quantity"], price=current,
                        reason=f"逆向失败，止损出局",
                        confidence=90, urgency="critical", ai_id=self.ai_id,
                    )

        # 逆向策略：找跌幅超过5%的超跌股
        if not my_holdings and my_cash > 10000:
            candidates = [
                (s, i) for s, i in prices.items()
                if i.get("pct_chg", 0) <= -4.0 and i.get("amount", 0) > 100000000
            ]
            if candidates:
                sym, info = candidates[0]
                price = info.get("price", 0)
                if price > 0:
                    qty = int((my_cash * 0.30) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=sym, name=info.get("name", sym),
                        quantity=qty, price=price,
                        reason=f"逆向布局：{info.get('name',sym)}超跌{info.get('pct_chg',0):.1f}%，困境反转预期",
                        confidence=70, urgency="high", ai_id=self.ai_id,
                    )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="逆向逻辑未变" if my_holdings else "等待逆向机会",
            confidence=60, ai_id=self.ai_id,
        )
