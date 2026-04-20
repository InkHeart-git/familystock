"""
Mike（迈克）- 动量投资派
Brain ID: mike
DB ID: 9
"""

from engine.brains.base import BaseBrain, CharacterConfig


class MikeBrain(BaseBrain):
    """Mike（迈克）- 激进动量派"""

    CONFIG = CharacterConfig(
        ai_id="mike",
        db_id=9,  # DB primary key
        name="Mike（迈克）",
        personality="热血",
        description="激进动量派，追涨不抄底，顺势而为",
        style="momentum",
        color="#FF6B35",
    )

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
        import random
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
                if pct_chg >= 4.0 and score >= 75 and main_net > 0:
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
                qty = int((my_cash * 0.50) / price / 100) * 100  # 激进：半仓出击
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
