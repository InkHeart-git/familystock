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
        """
        动量投资逻辑（MiniRock 算法驱动）：
        1. 硬止损：亏 4% 必走（动量策略止损线紧）
        2. 评分 ≤55 → 离场（动量消失）
        3. 资金流确认：主力净流入 + 评分 ≥70 → 追涨
        4. 涨幅 ≥3% + 动量强才入场
        """
        prices = market_data.get("prices", {})

        for h in my_holdings:
            sym = h["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})
            tech = alg.get("technical", {})
            fund = alg.get("fund", {})

            current = prices.get(sym, {}).get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            pnl_pct = (current - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
            score = summary.get("overall_score", 50)

            if pnl_pct <= -4.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"动量减弱，触发4%止损线，亏损{pnl_pct:.1f}%",
                    confidence=92, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 评分骤降 → 动量消失
            if score <= 55:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"MiniRock评分{score}分，动量减弱，果断离场",
                    confidence=82, urgency="high",
                    ai_id=self.ai_id, risk_level="medium",
                )

        # ── 空仓追涨 ──────────────────────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                fund = alg.get("fund", {})

                score = summary.get("overall_score", 0)
                pct_chg = info.get("pct_chg", 0)
                main_net = fund.get("main_net_amount", 0)

                # 动量策略：涨幅 ≥3% + 评分 ≥70 + 主力资金确认
                if pct_chg >= 3.0 and score >= 70 and main_net > 0:
                    candidates.append({
                        "symbol": sym, "name": info.get("name", sym),
                        "price": info.get("price", 0), "pct_chg": pct_chg,
                        "score": score, "main_net": main_net,
                        "confidence": min(score, 95),
                    })

            if candidates:
                best = max(candidates, key=lambda x: (x["score"], x["pct_chg"]))
                price = best["price"]
                qty = int((my_cash * 0.45) / price / 100) * 100
                return TradingDecision(
                    action=Action.BUY,
                    signal=DecisionSignal.STRONG_BUY if best["score"] >= 85 else DecisionSignal.BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分，主力净流入，{best['pct_chg']:.1f}%涨幅启动，顺势追击！⚡",
                    confidence=best["confidence"], urgency="high",
                    ai_id=self.ai_id,
                )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="动量未破，持仓" if my_holdings else "无动量机会，空仓观望",
            confidence=60, ai_id=self.ai_id,
        )
