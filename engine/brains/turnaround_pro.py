"""
周逆行 - 逆向投资大脑
风格：人弃我取，困境反转，抄底超跌股
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from typing import Dict, List, Any
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


TURNAROUND_PRO_CONFIG = CharacterConfig(
    ai_id="turnaround_pro",
    db_id=8,  # DB primary key id=8 (周逆行)
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

    async def think_like_human(
        self,
        market_data: Dict[str, Any],
        my_holdings: List[Dict],
        my_cash: float,
        news: List[Dict],
        minirock_analysis: Dict[str, Dict] = {},
    ) -> TradingDecision:
        """
        逆向投资逻辑（MiniRock 算法驱动）：
        1. 持仓：评分恶化 ≤55 → 认错离场（逆向策略也要认错）
        2. 空仓：超跌 + 评分开始回升（困境反转信号）
        3. 造假检测：风险高 → 绝不逆向（可能是真陷阱）
        4. 止损：亏 8% 必走（逆向策略失败）
        """
        prices = market_data.get("prices", {})

        for h in my_holdings:
            sym = h["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})
            fraud = alg.get("fraud_detection", {})

            current = prices.get(sym, {}).get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            pnl_pct = (current - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
            score = summary.get("overall_score", 50)

            if pnl_pct <= -8.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"逆向策略失效，亏损{pnl_pct:.1f}%，止损认错",
                    confidence=90, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 评分恶化 → 困境可能不是反转，而是真陷阱
            if score <= 55:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"MiniRock评分{score}分，困境未反转，可能是真陷阱，认错离场",
                    confidence=82, urgency="high",
                    ai_id=self.ai_id, risk_level="medium",
                )

        # ── 空仓逆向布局 ──────────────────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                tech = alg.get("technical", {})
                fraud = alg.get("fraud_detection", {})

                score = summary.get("overall_score", 0)
                pct_chg = info.get("pct_chg", 0)
                fraud_risk = str(fraud.get("risk_level", "")).lower()

                # 逆向策略：跌幅 ≥4% + 评分开始回升 ≥50 + 非造假陷阱
                if pct_chg <= -4.0 and score >= 50 and "高" not in fraud_risk:
                    candidates.append({
                        "symbol": sym, "name": info.get("name", sym),
                        "price": info.get("price", 0), "pct_chg": pct_chg,
                        "score": score,
                        "confidence": min(score + abs(pct_chg), 88),
                    })

            if candidates:
                best = max(candidates, key=lambda x: x["score"])
                price = best["price"]
                if price <= 0:
                    return TradingDecision(
                        action=Action.WATCH, signal=DecisionSignal.WATCH,
                        reason="等待逆向机会",
                        confidence=50, ai_id=self.ai_id,
                    )
                qty = int((my_cash * 0.30) / price / 100) * 100
                return TradingDecision(
                    action=Action.BUY, signal=DecisionSignal.BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分超跌{abs(best['pct_chg']):.1f}%，逆向布局，困境反转预期🔄",
                    confidence=best["confidence"], urgency="high",
                    ai_id=self.ai_id,
                )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="逆向逻辑未变" if my_holdings else "等待逆向机会",
            confidence=60, ai_id=self.ai_id,
        )
