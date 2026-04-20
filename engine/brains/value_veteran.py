"""
方守成 - 价值投资大脑
风格：老练稳健，注重基本面，安全边际，长线持有
"""

import logging
from typing import Dict, List, Any

from engine.brains.base import BaseBrain, CharacterConfig, Personality
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal

logger = logging.getLogger("ValueVeteran")


VALUE_VETERAN_CONFIG = CharacterConfig(
    ai_id="value_veteran",
    db_id=3,  # DB primary key id=3 (方守成)
    name="方守成",
    emoji="🦉",
    style="价值投资",
    group="风云五虎",
    initial_capital=1000000.0,
    description="老练的价值投资者，注重基本面和估值安全边际",
    personality=Personality(
        expressiveness=35,
        talkativeness=80,
        aggressiveness=20,
        emotional_stability=95,
        conformity=10,
        holding_days_min=10,
        holding_days_max=20,
        position_max_pct=0.30,
        total_position_max_pct=0.70,
        stop_loss_pct=-8.0,
        take_profit_pct=15.0,
        risk_appetite=30,
        vocab_set={"安全边际", "护城河", "基本面", "估值", "长期主义"},
        speech_pattern="老练",
        post_frequency_cap=3,
    ),
    system_prompt="你是方守成，老练的价值投资者。特点是安全边际优先、不追热点、长期持有、稳健为王。",
    post_keywords=["估值", "PE", "PB", "ROE", "现金流", "分红"],
    min_holding_hours=48,
    social_enabled=True,
)


class ValueVeteranBrain(BaseBrain):
    """方守成 - 价值投资大脑"""
    
    CONFIG = VALUE_VETERAN_CONFIG

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
        价值投资逻辑（MiniRock 算法驱动）：
        1. 安全边际：DCF 估值折价 ≥30% 才重仓
        2. 现金流健康度：必须连续 ≥3 年为正
        3. 造假检测：风险等级高 → 不碰
        4. 大跌时加仓（价值投资核心），但先看算法评分
        """
        prices = market_data.get("prices", {})

        for h in my_holdings:
            sym = h["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})
            valuation = alg.get("valuation", {})
            cashflow = alg.get("cashflow", {})
            fraud = alg.get("fraud_detection", {})

            current = prices.get(sym, {}).get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            pnl_pct = (current - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
            score = summary.get("overall_score", 50)

            # 造假风险高 → 止损离场
            fraud_level = str(fraud.get("risk_level", "")).lower()
            if "高" in fraud_level or "中" in fraud_level:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"财务造假风险提示（{fraud.get('risk_level')}），价值底线不可逾越，止损出局",
                    confidence=92, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 跌破安全边际 10% → 止损
            if pnl_pct <= -10.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"跌破安全边际，亏损{pnl_pct:.1f}%，止损",
                    confidence=90, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )

            # 跌幅 ≥4% 且算法评分仍 ≥55 → 加仓（价值投资逢低加仓）
            if -10 < pnl_pct <= -4 and score >= 55:
                add_qty = int((my_cash * 0.20) / current / 100) * 100
                if add_qty >= 100:
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=sym, name=h.get("name", sym),
                        quantity=add_qty, price=current,
                        reason=f"MiniRock评分{score}分，下跌{pnl_pct:.1f}%提供加仓机会，拉开成本",
                        confidence=80, urgency="high",
                        ai_id=self.ai_id,
                    )

        # ── 空仓选股 ──────────────────────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                valuation = alg.get("valuation", {})
                cashflow = alg.get("cashflow", {})

                score = summary.get("overall_score", 0)
                pct_chg = info.get("pct_chg", 0)
                upside = valuation.get("premium_discount", 0)  # 正=折价

                # 价值投资：DCF折价 ≥20% + 评分 ≥65 + 现金流健康 + 非大盘蓝筹（贵州茅台/平安银行不碰）
                if score >= 65 and upside >= 20:
                    candidates.append({
                        "symbol": sym, "name": info.get("name", sym),
                        "price": info.get("price", 0), "pct_chg": pct_chg,
                        "score": score, "upside": upside,
                        "confidence": min(score, 90),
                    })

            if candidates:
                best = max(candidates, key=lambda x: (x["score"], x["upside"]))
                price = best["price"]
                if price <= 0:
                    return TradingDecision(
                        action=Action.WATCH, signal=DecisionSignal.WATCH,
                        reason="市场未提供足够的安全边际（DCF折价≥20%），继续等待",
                        confidence=50, ai_id=self.ai_id,
                    )
                qty = int((my_cash * 0.30) / price / 100) * 100
                return TradingDecision(
                    action=Action.BUY, signal=DecisionSignal.BUY,
                    symbol=best["symbol"], name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分，DCF折价{best['upside']:.0f}%，安全边际充足，价值布局机会",
                    confidence=best["confidence"], urgency="normal",
                    ai_id=self.ai_id,
                )

        if my_holdings:
            top = my_holdings[0]
            alg = minirock_analysis.get(top["symbol"], {})
            score = alg.get("summary", {}).get("overall_score", 50)
            return TradingDecision(
                action=Action.HOLD, signal=DecisionSignal.HOLD,
                reason=f"MiniRock评分{score}分，基本面未变，价值投资不在乎短期波动",
                confidence=70, ai_id=self.ai_id,
            )

        return TradingDecision(
            action=Action.WATCH, signal=DecisionSignal.WATCH,
            reason="市场未提供足够的安全边际（DCF折价≥20%），继续等待",
            confidence=60, ai_id=self.ai_id,
        )
