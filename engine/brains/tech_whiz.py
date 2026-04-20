"""
韩科捷 - 科技投资大脑
风格：专注科技成长股，关注研发/渗透率/国产替代
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from typing import Dict, List, Any
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


TECH_WHIZ_CONFIG = CharacterConfig(
    ai_id="tech_whiz",
    db_id=6,  # DB primary key id=6 (韩科捷)
    name="韩科捷",
    emoji="🚀",
    style="科技投资",
    group="灵动小五",
    initial_capital=100000.0,
    description="专注科技成长股，国产替代赛道",
    personality=Personality(
        expressiveness=75, talkativeness=65, aggressiveness=55,
        emotional_stability=60, conformity=40,
        holding_days_min=3, holding_days_max=8,
        position_max_pct=0.40, total_position_max_pct=0.80,
        stop_loss_pct=-6.0, take_profit_pct=12.0, risk_appetite=70,
        vocab_set={"科技", "创新", "研发", "渗透率", "国产替代", "高增长"},
        speech_pattern="热血", post_frequency_cap=5,
    ),
    system_prompt="你是韩科捷，科技投资专家。专注半导体/AI/软件等科技成长赛道。",
    post_keywords=["科技", "半导体", "AI", "国产替代", "渗透率"],
    min_holding_hours=6, social_enabled=True,
)


class TechWhizBrain(BaseBrain):
    """韩科捷 - 科技投资大脑"""
    CONFIG = TECH_WHIZ_CONFIG

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
        科技投资逻辑（MiniRock 算法驱动）：
        1. 持仓：用算法综合评分管理，评分 ≤55 → 减仓
        2. 空仓：找科技赛道 + 评分 ≥70 + 资金流支持
        3. 科技股止损：亏 6% 必走
        4. 造假检测：财务风险高 → 不碰
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

            if pnl_pct <= -6.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"科技股波动加大，触发止损{pnl_pct:.1f}%，纪律优先",
                    confidence=92, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 造假风险 → 离场
            fraud_risk = str(fraud.get("risk_level", "")).lower()
            if "高" in fraud_risk:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"财务造假风险提示，科技股底线不可逾越",
                    confidence=88, urgency="high",
                    ai_id=self.ai_id, risk_level="high",
                )

            if score <= 55:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=int(h["quantity"] * 0.5), price=current,
                    reason=f"MiniRock评分{score}分，科技赛道动能减弱，减仓",
                    confidence=78, urgency="normal",
                    ai_id=self.ai_id, risk_level="medium",
                )

        # ── 空仓选科技股 ──────────────────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                fund = alg.get("fund", {})

                score = summary.get("overall_score", 0)
                pct_chg = info.get("pct_chg", 0)
                main_net = fund.get("main_net_amount", 0)

                # 科技股：评分 ≥70 + 涨幅 ≥2% + 主力净流入
                if score >= 70 and pct_chg >= 2.0 and main_net > 0:
                    candidates.append({
                        "symbol": sym, "name": info.get("name", sym),
                        "price": info.get("price", 0), "pct_chg": pct_chg,
                        "score": score,
                        "confidence": min(score, 92),
                    })

            if candidates:
                best = max(candidates, key=lambda x: x["score"])
                price = best["price"]
                qty = int((my_cash * 0.40) / price / 100) * 100
                return TradingDecision(
                    action=Action.BUY, signal=DecisionSignal.BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分，科技赛道强势，{best['pct_chg']:.1f}%涨幅启动，成长动量强🚀",
                    confidence=best["confidence"], urgency="normal",
                    ai_id=self.ai_id,
                )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="科技逻辑未变" if my_holdings else "等待科技机会",
            confidence=60, ai_id=self.ai_id,
        )
