"""
James Wong（黄詹姆斯）- 高股息大脑
风格：稳健收息，压舱石，低波动，蓝筹高股息
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


DIVIDEND_HUNTER_CONFIG = CharacterConfig(
    ai_id="dividend_hunter",
    name="James Wong（黄詹姆斯）",
    emoji="💰",
    style="高股息策略",
    group="灵动小五",
    initial_capital=100000.0,
    description="专注高股息蓝筹，稳定收息",
    personality=Personality(
        expressiveness=40, talkativeness=55, aggressiveness=25,
        emotional_stability=90, conformity=15,
        holding_days_min=15, holding_days_max=30,
        position_max_pct=0.35, total_position_max_pct=0.70,
        stop_loss_pct=-10.0, take_profit_pct=20.0, risk_appetite=25,
        vocab_set={"股息", "分红", "现金流", "收息", "稳健", "压舱石"},
        speech_pattern="老练", post_frequency_cap=3,
    ),
    system_prompt="你是James Wong（黄詹姆斯），高股息价值投资者。稳健为王，收息为主。",
    post_keywords=["股息", "分红", "现金流", "蓝筹", "稳健"],
    min_holding_hours=72, social_enabled=True,
)


class DividendHunterBrain(BaseBrain):
    """James Wong - 高股息大脑"""
    CONFIG = DIVIDEND_HUNTER_CONFIG

    def get_config(self) -> CharacterConfig:
        return self.CONFIG

    async def think_like_human(self, market_data, my_holdings, my_cash, news):
        prices = market_data.get("prices", {})

        # 高股息止损线宽：亏10%才出
        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            current = price_info.get("price", h.get("avg_cost", 0))
            if current > 0:
                pnl_pct = (current - h["avg_cost"]) / h["avg_cost"] * 100
                if pnl_pct <= -10.0:
                    return TradingDecision(
                        action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                        symbol=sym, name=h.get("name", sym),
                        quantity=h["quantity"], price=current,
                        reason=f"高股息股大跌，触发止损",
                        confidence=90, urgency="critical", ai_id=self.ai_id,
                    )

        # 高股息策略：空仓时不追高，等回调或横盘买入
        if not my_holdings and my_cash > 10000:
            candidates = [
                (s, i) for s, i in prices.items()
                if -2 <= i.get("pct_chg", 0) <= 1.5 and i.get("amount", 0) > 200000000
            ]
            if candidates:
                sym, info = candidates[0]
                price = info.get("price", 0)
                if price > 0:
                    qty = int((my_cash * 0.35) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=sym, name=info.get("name", sym),
                        quantity=qty, price=price,
                        reason=f"高股息布局：{info.get('name',sym)}回调提供安全边际，稳健入场",
                        confidence=75, urgency="normal", ai_id=self.ai_id,
                    )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="收息逻辑不变" if my_holdings else "等待高股息机会",
            confidence=65, ai_id=self.ai_id,
        )
