"""
Tyler（泰勒）- 趋势跟踪大脑
风格：年轻激进，追逐热点，追涨杀跌，止损果断
"""

import asyncio
import logging
import random
from typing import Dict, List, Optional, Any

import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from engine.brains.base import BaseBrain, CharacterConfig, Personality, Session
from engine.trading.decision_engine import TradingDecision, Action, DecisionSignal
from engine.posting.content_generator import PostType

logger = logging.getLogger("TrendChaser")


# ==================== 角色配置 ====================

TREND_CHASER_CONFIG = CharacterConfig(
    ai_id="trend_chaser",
    db_id=1,  # DB primary key id=1 (Tyler（泰勒）)
    name="Tyler（泰勒）",
    emoji="🚀",
    style="趋势跟踪",
    group="风云五虎",
    initial_capital=1000000.0,
    description="年轻激进的趋势跟踪型AI交易员，追逐热点，止损果断",
    
    personality=Personality(
        expressiveness=85,
        talkativeness=70,
        aggressiveness=75,
        emotional_stability=40,
        conformity=80,
        holding_days_min=1,
        holding_days_max=3,
        position_max_pct=0.40,
        total_position_max_pct=0.90,
        stop_loss_pct=-5.0,
        take_profit_pct=10.0,
        risk_appetite=85,
        vocab_set={"冲鸭", "YYDS", "拿捏", "梭哈", "All in", "趋势", "突破", "强势"},
        speech_pattern="热血",
        post_frequency_cap=6,
    ),
    
    system_prompt="""你是Tyler（泰勒），年轻激进的趋势跟踪型AI交易员。

特点：
- 追逐市场热点，相信"强者恒强"
- 仓位较高，敢于梭哈
- 止损坚决，5%止损线
- 持仓1-3天，不恋战
- 年轻热血，说话直接

发言风格：常用"冲鸭！""YYDS""拿捏了""梭哈！"

你只分析你持有的股票，不持有的一概不分析。""",
    
    post_keywords=["趋势", "突破", "强势", "动能", "龙头", "追涨"],
    min_holding_hours=4,
    social_enabled=True,
)


class TrendChaserBrain(BaseBrain):
    """Tyler 趋势跟踪大脑"""

    CONFIG = TREND_CHASER_CONFIG

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
        趋势跟踪决策逻辑（MiniRock 算法驱动）：
        
        决策优先级：
        1. 硬止损：亏 ≥8% 必走（不管算法说什么）
        2. 算法决策：MiniRock 综合评分 + 裁判系统 action
        3. 资金流确认：主力净流入才考虑买
        4. 趋势保护：MACD/KDJ 技术面恶化则走
        5. 空仓时：综合评分 ≥75 分才考虑追入
        """
        import random
        prices = market_data.get("prices", {})
        
        # ── 1. 持仓检查：算法驱动决策 ─────────────────────────────
        for h in my_holdings:
            sym = h["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})
            tech = alg.get("technical", {})
            fund = alg.get("fund", {})
            
            current = prices.get(sym, {}).get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            pnl_pct = (current - avg_cost) / avg_cost * 100 if avg_cost > 0 else 0
            
            # 硬止损：亏8%必走
            if pnl_pct <= -8.0:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"触发硬止损，亏损{pnl_pct:.1f}%，纪律优先",
                    confidence=98, urgency="critical",
                    ai_id=self.ai_id, risk_level="high",
                )
            
            # 硬止盈：赚20%走一半
            if pnl_pct >= 20.0:
                sell_qty = int(h["quantity"] * 0.5)
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=sell_qty, price=current,
                    reason=f"达到止盈目标+20%，锁定利润",
                    confidence=92, urgency="high",
                    ai_id=self.ai_id,
                )
            
            # 算法裁判系统：评分 ≤45 分 → 卖出
            score = summary.get("overall_score", 50)
            action = summary.get("action", "持有")
            if score <= 45:
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=h["quantity"], price=current,
                    reason=f"MiniRock综合评分{score}分（{action}），趋势走坏，果断离场",
                    confidence=85, urgency="high",
                    ai_id=self.ai_id, risk_level="high",
                )
            
            # 资金流恶化：主力大幅流出 → 减仓
            main_net = fund.get("main_net_amount", 0)
            if main_net < -50000000 and score < 65:  # 主力净流出超5千万且评分偏低
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=int(h["quantity"] * 0.5), price=current,
                    reason=f"主力净流出{abs(main_net)/1e8:.1f}亿元，资金面恶化，半仓观望",
                    confidence=80, urgency="high",
                    ai_id=self.ai_id, risk_level="medium",
                )
            
            # 技术面恶化：MACD 死叉 → 减仓
            macd = tech.get("macd", "")
            if "死叉" in str(macd) or "向下" in str(macd):
                return TradingDecision(
                    action=Action.SELL, signal=DecisionSignal.SELL,
                    symbol=sym, name=h.get("name", sym),
                    quantity=int(h["quantity"] * 0.5), price=current,
                    reason=f"MACD出现死叉，技术面转弱，半仓保护利润",
                    confidence=78, urgency="normal",
                    ai_id=self.ai_id,
                )
        
        # ── 2. 空仓时寻找机会：算法评分驱动 ─────────────────────
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                alg = minirock_analysis.get(sym, {})
                summary = alg.get("summary", {})
                tech = alg.get("technical", {})
                fund = alg.get("fund", {})
                
                score = summary.get("overall_score", 0)
                action = summary.get("action", "观望")
                pct_chg = info.get("pct_chg", 0)
                
                # 趋势跟踪：只追涨幅 ≥3% 且 评分 ≥70 分 的标的
                if pct_chg >= 3.0 and score >= 70 and action in ("买入", "增持"):
                    # 主力资金确认（当日净流入）
                    main_net = fund.get("main_net_amount", 0)
                    # 强势股：主力净流入 OR 大盘情绪好
                    if main_net > 0 or score >= 80:
                        candidates.append({
                            "symbol": sym, "name": info.get("name", sym),
                            "price": info.get("price", 0),
                            "pct_chg": pct_chg,
                            "score": score,
                            "action": action,
                            "confidence": min(score, 95),
                        })
            
            if candidates:
                # 选评分最高 + 涨幅最大的
                best = max(candidates, key=lambda x: (x["score"], x["pct_chg"]))
                price = best["price"]
                if price <= 0:
                    return TradingDecision(
                        action=Action.WATCH, signal=DecisionSignal.WATCH,
                        reason="暂无符合条件的机会（评分≥70分且强势），保持空仓",
                        confidence=50, ai_id=self.ai_id,
                    )
                qty = min(int((my_cash * 0.4) / price / 100) * 100, int(my_cash / price / 100) * 100)
                return TradingDecision(
                    action=Action.BUY,
                    signal=DecisionSignal.STRONG_BUY if best["score"] >= 85 else DecisionSignal.BUY,
                    symbol=best["symbol"],
                    name=best["name"],
                    quantity=qty, price=price,
                    reason=f"MiniRock评分{best['score']}分（{best['action']}），"
                           f"今日涨幅{best['pct_chg']:.2f}%，趋势确立，趋势跟踪启动！🚀",
                    confidence=best["confidence"],
                    urgency="high" if best["score"] >= 85 else "normal",
                    ai_id=self.ai_id,
                )
        
        # ── 3. 持仓观望 ─────────────────────────────────────────
        if my_holdings:
            top_holding = my_holdings[0]
            sym = top_holding["symbol"]
            alg = minirock_analysis.get(sym, {})
            summary = alg.get("summary", {})
            score = summary.get("overall_score", 50)
            return TradingDecision(
                action=Action.HOLD, signal=DecisionSignal.HOLD,
                reason=f"持仓中，MiniRock评分{score}分，趋势未破，耐心持有",
                confidence=65, ai_id=self.ai_id,
            )
        
        # ── 4. 空仓且无机会 ──────────────────────────────────────
        return TradingDecision(
            action=Action.WATCH, signal=DecisionSignal.WATCH,
            reason="暂无符合条件的机会（评分≥70分且强势），保持空仓",
            confidence=50,
            ai_id=self.ai_id,
        )
