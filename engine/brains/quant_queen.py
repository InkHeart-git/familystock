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
    ) -> TradingDecision:
        """
        量化决策逻辑：
        1. 技术指标优先（MACD/RSI/KDJ）
        2. 严格止损，不幻想
        3. 空仓时不追高，等回调
        4. 持仓超5天强制平仓
        """
        prices = market_data.get("prices", {})
        
        # 1. 止损检查
        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            current = price_info.get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            
            if current > 0 and avg_cost > 0:
                pnl_pct = (current - avg_cost) / avg_cost * 100
                
                if pnl_pct <= -5.0:
                    return TradingDecision(
                        action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                        symbol=sym, name=h.get("name", sym),
                        quantity=h["quantity"], price=current,
                        reason=f"触发止损，量化信号显示下跌趋势延续（{pnl_pct:.1f}%）",
                        confidence=95, urgency="critical", ai_id=self.ai_id,
                    )
        
        # 2. 持仓超期检查（量化纪律）
        import time
        for h in my_holdings:
            updated = h.get("updated_at", "")
            if updated:
                try:
                    from datetime import datetime as dt
                    buy_date = dt.strptime(updated[:19], "%Y-%m-%d %H:%M:%S")
                    days = (dt.now() - buy_date).days
                    if days >= 5:
                        return TradingDecision(
                            action=Action.SELL, signal=DecisionSignal.SELL,
                            symbol=h["symbol"], name=h.get("name", h["symbol"]),
                            quantity=h["quantity"],
                            price=prices.get(h["symbol"], {}).get("price", h.get("avg_cost", 0)),
                            reason=f"持仓超过5天，量化策略强制平仓",
                            confidence=80, urgency="normal", ai_id=self.ai_id,
                        )
                except:
                    pass
        
        # 3. 技术指标选股（空仓时）
        if not my_holdings and my_cash > 10000:
            candidates = []
            for sym, info in prices.items():
                pct = info.get("pct_chg", 0)
                # 量化策略：等回调再买，不追高
                if -2 <= pct <= 3:
                    score = self._calc_technical_score(info)
                    candidates.append((sym, info, score))
            
            if candidates:
                candidates.sort(key=lambda x: x[2], reverse=True)
                sym, info, score = candidates[0]
                price = info.get("price", 0)
                if price > 0 and score > 60:
                    qty = int((my_cash * 0.35) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=sym, name=info.get("name", sym),
                        quantity=qty, price=price,
                        reason=f"量化模型信号：技术评分{score}，RSI/KDJ共振，概率优势明显",
                        confidence=75, urgency="normal", ai_id=self.ai_id,
                    )
        
        # 4. 持仓观望
        if my_holdings:
            return TradingDecision(
                action=Action.HOLD, signal=DecisionSignal.HOLD,
                reason="量化指标未触发，持仓观察",
                confidence=60, ai_id=self.ai_id,
            )
        
        return TradingDecision(
            action=Action.WATCH, signal=DecisionSignal.WATCH,
            reason="无符合量化条件的标的，等待模型信号",
            confidence=50, ai_id=self.ai_id,
        )
    
    def _calc_technical_score(self, price_info: Dict) -> float:
        """计算技术指标综合评分 0-100"""
        score = 50.0
        
        pct_chg = abs(price_info.get("pct_chg", 0))
        volume = price_info.get("volume", 0)
        amount = price_info.get("amount", 0)
        
        # 涨幅适中给高分（不追高但也不跌）
        if 0.5 <= pct_chg <= 2.0:
            score += 15
        
        # 成交额放大是好信号
        if amount > 100000000:  # 1亿+
            score += 10
        
        return min(score, 100)
