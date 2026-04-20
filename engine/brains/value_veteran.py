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
        价值投资逻辑：
        1. 基本面不变，不因短期波动卖出
        2. 只有估值过高才考虑减仓
        3. 下跌时加仓（拉开成本）
        4. 空仓时只买低PE/高ROE的蓝筹
        """
        prices = market_data.get("prices", {})
        
        # 1. 大跌时考虑加仓（价值投资逢低加仓）
        for h in my_holdings:
            sym = h["symbol"]
            price_info = prices.get(sym, {})
            pct_chg = price_info.get("pct_chg", 0)
            current = price_info.get("price", h.get("avg_cost", 0))
            avg_cost = h.get("avg_cost", 0)
            
            if current > 0 and avg_cost > 0:
                pnl_pct = (current - avg_cost) / avg_cost * 100
                
                # 跌幅超过5%且基本面没变：加仓
                if pct_chg <= -4 and pnl_pct > -10:
                    add_qty = int((my_cash * 0.2) / current / 100) * 100
                    if add_qty >= 100:
                        return TradingDecision(
                            action=Action.BUY, signal=DecisionSignal.BUY,
                            symbol=sym, name=h.get("name", sym),
                            quantity=add_qty, price=current,
                            reason=f"价值投资：下跌{pct_chg:.1f}%提供加仓机会，拉开成本",
                            confidence=80, urgency="high", ai_id=self.ai_id,
                        )
                
                # 跌幅超8%止损（价值投资也有红线）
                if pnl_pct <= -8.0:
                    return TradingDecision(
                        action=Action.SELL, signal=DecisionSignal.STRONG_SELL,
                        symbol=sym, name=h.get("name", sym),
                        quantity=h["quantity"], price=current,
                        reason=f"跌破安全边际，止损出局",
                        confidence=90, urgency="critical", ai_id=self.ai_id,
                    )
        
        # 2. 空仓时寻找价值标的
        if not my_holdings and my_cash > 10000:
            # 价值投资不轻易出手，等好价格
            # 这里简化为：找跌幅较大的蓝筹股（等回调）
            candidates = []
            for sym, info in prices.items():
                pct = info.get("pct_chg", 0)
                amount = info.get("amount", 0)
                # 成交额大（非小盘股）+ 今日小跌或横盘
                if amount > 500000000 and -3 <= pct <= 1:
                    candidates.append((sym, info, pct))
            
            if candidates:
                # 选跌幅相对大的（更安全的价格）
                candidates.sort(key=lambda x: x[2])
                sym, info, pct = candidates[0]
                price = info.get("price", 0)
                if price > 0:
                    qty = int((my_cash * 0.3) / price / 100) * 100
                    return TradingDecision(
                        action=Action.BUY, signal=DecisionSignal.BUY,
                        symbol=sym, name=info.get("name", sym),
                        quantity=qty, price=price,
                        reason=f"价值投资机会：{info.get('name',sym)}调整{pct:.1f}%，安全边际出现",
                        confidence=75, urgency="normal", ai_id=self.ai_id,
                    )
        
        # 3. 持仓不动
        if my_holdings:
            return TradingDecision(
                action=Action.HOLD, signal=DecisionSignal.HOLD,
                reason="基本面未变，价值投资不在乎短期波动",
                confidence=70, ai_id=self.ai_id,
            )
        
        return TradingDecision(
            action=Action.WATCH, signal=DecisionSignal.WATCH,
            reason="市场未提供足够的安全边际，继续等待",
            confidence=60, ai_id=self.ai_id,
        )
