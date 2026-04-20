"""
James Wong（黄詹姆斯）- 高股息大脑
风格：稳健收息，压舱石，低波动，蓝筹高股息
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from typing import Dict, List, Any
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


DIVIDEND_HUNTER_CONFIG = CharacterConfig(
    ai_id="dividend_hunter",
    db_id=7,  # DB primary key id=7 (James Wong（黄詹姆斯）)
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

    async def think_like_human(
        self,
        market_data: Dict[str, Any],
        my_holdings: List[Dict],
        my_cash: float,
        news: List[Dict],
        minirock_analysis: Dict[str, Dict] = {},
    ) -> TradingDecision:
        """
        高股息策略（MiniRock 算法驱动）：
        1. 持仓：现金流必须健康（≥3年），造假 → 止损
        2. 评分 ≤50 → 减仓（高股息逻辑不再成立）
        3. 空仓：DCF折价 + 现金流健康 + 跌幅不大
        4. 止损宽：亏 10% 才走（压舱石定位）
        """
        prices = market_data.get("prices", {})

        for h in my_holdings:
            sym = h["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})
            cashflow = alg.get("cashflow", {})
            fraud = alg.get("fraud_detection", {})

            current = prices.get(sym, {}).get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            pnl_pct = (current - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
            score = summary.get("overall_score", 50)

            # 造假 → 高股息基础崩塌，止损
            fraud_risk = str(fraud.get("risk_level", "")).lower()
            if "高" in fraud_risk:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"财务造假风险，高股息根基崩塌，止损清仓",
                    confidence=92, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            if pnl_pct <= -10.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"跌破压舱石底线，亏损{pnl_pct:.1f}%，止损",
                    confidence=90, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 评分低 → 高股息逻辑不再成立
            if score <= 50:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=int(h["quantity"] * 0.5), price=current,
                    reason=f"MiniRock评分{score}分，高股息逻辑弱化，减仓保护",
                    confidence=78, urgency="normal",
                    ai_id=self.ai_id, risk_level="medium",
                )

        # ── 空仓布局 ──────────────────────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                valuation = alg.get("valuation", {})
                cashflow = alg.get("cashflow", {})

                score = summary.get("overall_score", 0)
                pct_chg = info.get("pct_chg", 0)
                cf_score = cashflow.get("score", 0)
                healthy_yrs = cashflow.get("healthy_years", 0)

                # 高股息：评分 ≥60 + 现金流健康(≥3年) + 今日小跌或横盘
                if score >= 60 and healthy_yrs >= 3 and -2 <= pct_chg <= 1.5:
                    candidates.append({
                        "symbol": sym, "name": info.get("name", sym),
                        "price": info.get("price", 0), "pct_chg": pct_chg,
                        "score": score, "cf_score": cf_score,
                        "confidence": min(score, 88),
                    })

            if candidates:
                best = max(candidates, key=lambda x: (x["score"], x["cf_score"]))
                price = best["price"]
                if price <= 0:
                    return TradingDecision(
                        action=Action.WATCH, signal=DecisionSignal.WATCH,
                        reason="候选标的价格数据无效，等待开盘后重新分析",
                        confidence=50, ai_id=self.ai_id,
                    )
                qty = min(int((my_cash * 0.35) / price / 100) * 100, int(my_cash / price / 100) * 100)
                return TradingDecision(
                    action=Action.BUY, signal=DecisionSignal.BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分，现金流{healthy_yrs}年健康，高股息稳健布局",
                    confidence=best["confidence"], urgency="normal",
                    ai_id=self.ai_id,
                )

        return TradingDecision(
            action=Action.WATCH if not my_holdings else Action.HOLD,
            signal=DecisionSignal.HOLD,
            reason="收息逻辑不变" if my_holdings else "等待高股息机会",
            confidence=65, ai_id=self.ai_id,
        )
