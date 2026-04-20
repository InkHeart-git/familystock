"""
沈闻 - 事件驱动大脑
风格：专注催化剂和事件驱动机会（业绩/政策/并购）
"""

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from typing import Dict, List, Any
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal


EVENT_DRIVEN_CONFIG = CharacterConfig(
    ai_id="event_driven",
    db_id=10,  # DB primary key id=10 (沈闻)
    name="沈闻",
    emoji="🎯",
    style="事件驱动",
    group="灵动小五",
    initial_capital=100000.0,
    description="事件驱动型投资者，专注催化剂和事件机会",
    personality=Personality(
        expressiveness=65, talkativeness=65, aggressiveness=40,
        emotional_stability=70, conformity=50,
        holding_days_min=2, holding_days_max=7,
        position_max_pct=0.40, total_position_max_pct=0.80,
        stop_loss_pct=-6.0, take_profit_pct=10.0, risk_appetite=65,
        vocab_set={"事件", "催化", "业绩", "政策", "公告", "节点"},
        speech_pattern="理性", post_frequency_cap=4,
    ),
    system_prompt="你是沈闻，事件驱动型投资者。专注业绩公告、政策利好、并购重组等催化剂。",
    post_keywords=["事件", "催化", "业绩", "政策", "公告"],
    min_holding_hours=4, social_enabled=True,
)


class EventDrivenBrain(BaseBrain):
    """沈闻 - 事件驱动大脑"""
    CONFIG = EVENT_DRIVEN_CONFIG

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
        事件驱动逻辑（MiniRock 算法驱动）：
        1. 持仓：评分 ≤55 → 事件催化消退，离场
        2. 空仓：从 NewsAnalyzer 情绪数据找催化剂
        3. 算法评分确认：事件 + 评分 ≥65 才入场
        4. 止损：亏 6% 必走
        """
        prices = market_data.get("prices", {})
        news_context = market_data.get("news_context", {})
        sentiment = news_context.get("overall_sentiment", "neutral")

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
                    reason=f"事件催化失效，触发止损{pnl_pct:.1f}%",
                    confidence=90, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            if score <= 55:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"MiniRock评分{score}分，事件催化消退，离场",
                    confidence=80, urgency="normal",
                    ai_id=self.ai_id, risk_level="medium",
                )

        # ── 空仓事件驱动 ──────────────────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                score = summary.get("overall_score", 0)
                pct_chg = info.get("pct_chg", 0)

                # 事件驱动：涨幅 ≥2% + 评分 ≥65
                if pct_chg >= 2.0 and score >= 65:
                    candidates.append({
                        "symbol": sym, "name": info.get("name", sym),
                        "price": info.get("price", 0), "pct_chg": pct_chg,
                        "score": score,
                        "confidence": min(score, 90),
                    })

            if candidates:
                best = max(candidates, key=lambda x: x["score"])
                price = best["price"]
                qty = int((my_cash * 0.40) / price / 100) * 100
                return TradingDecision(
                    action=Action.BUY, signal=DecisionSignal.BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分，{best['pct_chg']:.1f}%涨幅，事件催化启动🎯",
                    confidence=best["confidence"], urgency="high",
                    ai_id=self.ai_id,
                )

        return TradingDecision(
            action=Action.HOLD if my_holdings else Action.WATCH,
            signal=DecisionSignal.HOLD,
            reason="事件逻辑未变" if my_holdings else "等待事件催化",
            confidence=60, ai_id=self.ai_id,
        )
