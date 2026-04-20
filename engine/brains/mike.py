"""
Mike（迈克）- 激进动量派
Brain ID: mike
DB ID: 9
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import Action, DecisionSignal, TradingDecision
from typing import Dict, List, Any


MIKE_CONFIG = CharacterConfig(
    ai_id="mike",
    db_id=9,  # DB primary key
    name="Mike（迈克）",
    emoji="🔥",
    style="动量投资",
    group="风云五虎",
    initial_capital=1000000.0,
    description="激进动量派，追涨不抄底，顺势而为，让利润奔跑",

    personality=Personality(
        expressiveness=90,
        talkativeness=80,
        aggressiveness=90,
        emotional_stability=35,
        conformity=70,
        holding_days_min=1,
        holding_days_max=2,
        position_max_pct=0.50,
        total_position_max_pct=0.90,
        stop_loss_pct=-5.0,
        take_profit_pct=15.0,
        risk_appetite=95,
        vocab_set={"🔥", "爆发", "追击", "梭哈", "利润奔跑", "动量", "爆发点", "强势"},
        speech_pattern="热血",
        post_frequency_cap=6,
    ),

    system_prompt="""你是Mike（迈克），激进动量派交易员。

风格：追涨不抄底，顺势而为。别人恐惧我更贪，别人贪婪我止盈。
核心理念：让利润奔跑，止损要快，出手要狠。
口头禅：利润奔跑！🔥 追击！""",

    post_keywords=["动量", "追击", "强势", "爆发", "利润奔跑", "🔥"],
    min_holding_hours=2,
    social_enabled=True,
)


class MikeBrain(BaseBrain):
    """Mike（迈克）- 激进动量派"""

    CONFIG = MIKE_CONFIG

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
        激进动量策略（MiniRock 算法驱动）：
        1. 硬止损：亏 5% 必走（激进止损线）
        2. 评分 ≤60 → 离场（动量消失比谁都快）
        3. 空仓：涨幅 ≥4% + 评分 ≥75 + 主力确认 → 强势追击
        4. 持仓：动量不破不止盈，让利润奔跑
        """
        prices = market_data.get("prices", {})

        # ── 持仓动量管理 ───────────────────────────────
        for h in my_holdings:
            sym = h["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})
            fund = alg.get("fund", {})

            current = prices.get(sym, {}).get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            pnl_pct = (current - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
            score = summary.get("overall_score", 50)
            main_net = fund.get("main_net_amount", 0)

            # 激进止损：亏5%必走
            if pnl_pct <= -5.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"触发5%硬止损，亏损{pnl_pct:.1f}%，认错离场",
                    confidence=95, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 评分骤降 → 动量提前消退
            if score <= 60:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"MiniRock评分{score}分，动量提前消退，果断离场",
                    confidence=82, urgency="high",
                    ai_id=self.ai_id, risk_level="medium",
                )

            # 主力大幅流出 + 评分 < 70 → 减半仓
            if main_net < -80000000 and score < 70:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=int(h["quantity"] * 0.5), price=current,
                    reason=f"主力净流出{abs(main_net)/1e8:.0f}亿，资金撤离，半仓保护",
                    confidence=80, urgency="high",
                    ai_id=self.ai_id, risk_level="medium",
                )

        # ── 空仓追击强势股 ──────────────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                fund = alg.get("fund", {})

                score = summary.get("overall_score", 0)
                pct_chg = info.get("pct_chg", 0)
                main_net = fund.get("main_net_amount", 0)

                # 激进动量：涨幅≥4% + 评分≥75 + 主力净流入确认
                if pct_chg >= 2.0 and score >= 65 and main_net > 0:
                    candidates.append({
                        "symbol": sym, "name": info.get("name", sym),
                        "price": info.get("price", 0), "pct_chg": pct_chg,
                        "score": score, "main_net": main_net,
                        "confidence": min(score, 95),
                    })

            if candidates:
                # 选最强 + 主力最确认的
                best = max(candidates, key=lambda x: (x["score"], x["pct_chg"]))
                price = best["price"]
                if price <= 0:
                    return TradingDecision(
                        action=Action.WATCH, signal=DecisionSignal.WATCH,
                        reason="无强势动量机会，等待下一个爆发点",
                        confidence=50, ai_id=self.ai_id,
                    )
                qty = min(int((my_cash * 0.5) / price / 100) * 100, int(my_cash / price / 100) * 100)  # 激进：半仓出击
                return TradingDecision(
                    action=Action.BUY,
                    signal=DecisionSignal.STRONG_BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分，{best['pct_chg']:.1f}%强势启动，主力确认！🔥顺势追击！",
                    confidence=best["confidence"], urgency="critical",
                    ai_id=self.ai_id,
                )

        # ── 持仓让利润奔跑 ────────────────────────────
        if my_holdings:
            top = my_holdings[0]
            alg = minirock_analysis.get(top["symbol"], {})
            score = alg.get("summary", {}).get("overall_score", 50)
            return TradingDecision(
                action=Action.HOLD, signal=DecisionSignal.HOLD,
                reason=f"动量未破，评分{score}分，让利润奔跑！🚀",
                confidence=70, ai_id=self.ai_id,
            )

        return TradingDecision(
            action=Action.WATCH, signal=DecisionSignal.WATCH,
            reason="无强势动量机会，等待下一个爆发点",
            confidence=55, ai_id=self.ai_id,
        )
