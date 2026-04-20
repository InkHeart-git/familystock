"""
林数理 - 量化分析大脑
风格：冷静理性，数据驱动，严格执行策略
"""

import asyncio
import logging
from typing import Dict, List, Any

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal

logger = logging.getLogger("QuantQueen")


QUANT_QUEEN_CONFIG = CharacterConfig(
    ai_id="quant_queen",
    db_id=2,  # DB primary key id=2 (林数理)
    name="林数理",
    emoji="📊",
    style="量化分析",
    group="风云五虎",
    initial_capital=1000000.0,
    description="冷静理性的量化分析型AI交易员，完全依靠数据和算法",
    personality=Personality(
        expressiveness=50,
        talkativeness=60,
        aggressiveness=30,
        emotional_stability=90,
        conformity=20,
        holding_days_min=2,
        holding_days_max=5,
        position_max_pct=0.35,
        total_position_max_pct=0.85,
        stop_loss_pct=-5.0,
        take_profit_pct=8.0,
        risk_appetite=55,
        vocab_set={"数据显示", "量化信号", "模型", "概率", "回测"},
        speech_pattern="理性",
        post_frequency_cap=5,
    ),
    system_prompt="你是林数理，冷静理性的量化分析型AI交易员。特点是数据说话、算法决策、纪律严明。",
    post_keywords=["MACD", "KDJ", "RSI", "均线", "金叉", "死叉"],
    min_holding_hours=8,
    social_enabled=True,
)


class QuantQueenBrain(BaseBrain):
    """林数理 - 量化分析大脑"""
    
    CONFIG = QUANT_QUEEN_CONFIG

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
        量化决策逻辑（MiniRock 算法驱动）：
        1. 技术指标：金叉/死叉 + RSI 超买超卖
        2. 综合评分 ≤50 → 减仓/止损
        3. 空仓：等技术回调 + MACD 金叉信号才入场
        """
        prices = market_data.get("prices", {})

        # ── 持仓检查 ───────────────────────────────────────
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

            # 硬止损：亏 7% 走
            if pnl_pct <= -7.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"量化止损，亏损{pnl_pct:.1f}%，纪律优先",
                    confidence=95, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 算法评分差：≤50 分 → 减仓
            if score <= 50:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=int(h["quantity"] * 0.5), price=current,
                    reason=f"MiniRock综合评分{score}分，量化信号偏空，减仓观望",
                    confidence=80, urgency="normal",
                    ai_id=self.ai_id, risk_level="medium",
                )

            # MACD 死叉 → 减仓
            macd = str(tech.get("macd", ""))
            if "死叉" in macd or "向下" in macd:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=int(h["quantity"] * 0.5), price=current,
                    reason=f"MACD出现死叉，量化模型显示短期动能减弱",
                    confidence=78, urgency="normal",
                    ai_id=self.ai_id,
                )

        # ── 空仓选股（Phase 2: 评分排序选最优）─────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                if not alg:
                    continue
                summary = alg.get("summary", {})
                tech = alg.get("technical", {})

                score = summary.get("overall_score", 0)
                tech_score = tech.get("score", 50)
                pct_chg = info.get("pct_chg", 0)
                macd = str(tech.get("macd", ""))
                rsi = tech.get("rsi", 50)

                # Phase 2: 评分≥50且技术面正向即可纳入候选
                if score < 50 or tech_score < 40:
                    continue

                is_golden = "金叉" in macd or "向上" in macd
                is_oversold = isinstance(rsi, (int, float)) and rsi < 35
                signal = "MACD金叉" if is_golden else ("RSI超卖" if is_oversold else "技术支撑")

                candidates.append({
                    "symbol": sym, "name": info.get("name", sym),
                    "price": info.get("price", 0), "pct_chg": pct_chg,
                    "score": score, "tech_score": tech_score,
                    "confidence": min(score, 92),
                    "signal": signal,
                })

            if candidates:
                best = max(candidates, key=lambda x: (x["score"], x["tech_score"]))
                price = best["price"]
                if price <= 0:
                    return TradingDecision(
                        action=Action.WATCH, signal=DecisionSignal.WATCH,
                        reason="无符合量化条件的标的，等待模型信号",
                        confidence=50, ai_id=self.ai_id,
                    )
                qty = min(int((my_cash * 0.35) / price / 100) * 100, int(my_cash / price / 100) * 100)
                return TradingDecision(
                    action=Action.BUY, signal=DecisionSignal.BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock量化信号：评分{best['score']}分，{best['signal']}，概率优势明显",
                    confidence=best["confidence"], urgency="normal",
                    ai_id=self.ai_id,
                )

        # ── 持仓观望 ──────────────────────────────────────
        if my_holdings:
            top = my_holdings[0]
            alg = minirock_analysis.get(top["symbol"], {})
            score = alg.get("summary", {}).get("overall_score", 50)
            return TradingDecision(
                action=Action.HOLD, signal=DecisionSignal.HOLD,
                reason=f"MiniRock评分{score}分，量化指标未触发，持仓观察",
                confidence=65, ai_id=self.ai_id,
            )

        return TradingDecision(
            action=Action.WATCH, signal=DecisionSignal.WATCH,
            reason="无符合量化条件的标的，等待模型信号",
            confidence=55, ai_id=self.ai_id,
        )
