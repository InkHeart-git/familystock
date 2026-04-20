"""
David Chen（陈大卫）- 宏观策略大脑
风格：全球视野，跨市场配置，关注利率/政策/汇率
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from typing import Dict, List, Any
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


MACRO_MASTER_CONFIG = CharacterConfig(
    ai_id="macro_master",
    db_id=5,  # DB primary key id=5 (David Chen（陈大卫）)
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

    async def think_like_human(
        self,
        market_data: Dict[str, Any],
        my_holdings: List[Dict],
        my_cash: float,
        news: List[Dict],
        minirock_analysis: Dict[str, Dict] = {},
    ) -> TradingDecision:
        """
        宏观策略逻辑（MiniRock 算法驱动）：
        1. 全球指数指引（已有）作为宏观背景
        2. 算法综合评分：≥70 分 A股才有配置价值
        3. 持仓用算法评分管理，宏观背景决定仓位上限
        4. 资金流 + 估值判断方向
        """
        prices = market_data.get("prices", {})
        indices = market_data.get("indices", {})

        us_pct = indices.get("NDX", {}).get("pct_chg", 0)
        hk_pct = indices.get("HSI", {}).get("pct_chg", 0)

        for h in my_holdings:
            sym = h["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})

            current = prices.get(sym, {}).get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            pnl_pct = (current - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
            score = summary.get("overall_score", 50)

            if pnl_pct <= -6.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"宏观逻辑变化，触发止损{pnl_pct:.1f}%",
                    confidence=90, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 评分 ≤55 → 宏观配置价值消失
            if score <= 55:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"MiniRock评分{score}分，宏观配置价值减弱，减持",
                    confidence=80, urgency="normal",
                    ai_id=self.ai_id, risk_level="medium",
                )

        # ── 空仓配置 ──────────────────────────────────────
        if not my_holdings and my_cash > 10000:
            # 宏观背景：美股/港股指引
            macro_bullish = us_pct > 1.5 or hk_pct > 1.0

            if macro_bullish:
                candidates = []
                for sym, info in prices.items():
                    alg = minirock_analysis.get(sym, {})
                    summary = alg.get("summary", {})
                    score = summary.get("overall_score", 0)
                    pct_chg = info.get("pct_chg", 0)

                    if score >= 70 and pct_chg >= 1.0:
                        candidates.append({
                            "symbol": sym, "name": info.get("name", sym),
                            "price": info.get("price", 0), "pct_chg": pct_chg,
                            "score": score,
                            "confidence": min(score, 90),
                        })

                if candidates:
                    best = max(candidates, key=lambda x: x["score"])
                    price = best["price"]
                    qty = int((my_cash * 0.30) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=best["symbol"], name=best["name"],
                        quantity=qty, price=price,
                        reason=f"宏观联动：纳指{us_pct:+.1f}%/恒指{hk_pct:+.1f}%，MiniRock评分{best['score']}分，顺宏观做多A股",
                        confidence=best["confidence"], urgency="normal",
                        ai_id=self.ai_id,
                    )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason=f"宏观逻辑未变，持仓（纳指{us_pct:+.1f}%）" if my_holdings else f"等待宏观信号（纳指{us_pct:+.1f}%）",
            confidence=60, ai_id=self.ai_id,
        )
