"""
交易决策引擎 - 统一入口
负责持仓评估、信号生成、决策输出
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

logger = logging.getLogger("Trading")


class Action(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"  # 观望，不操作


class DecisionSignal(Enum):
    STRONG_BUY = "strong_buy"    # 强烈买入
    BUY = "buy"                  # 买入
    HOLD = "hold"                # 持有
    SELL = "sell"                # 减仓
    STRONG_SELL = "strong_sell"  # 清仓
    WATCH = "watch"              # 观望


@dataclass
class TradingDecision:
    """交易决策"""
    action: Action
    signal: DecisionSignal
    symbol: str = ""
    name: str = ""
    quantity: int = 0
    price: float = 0.0
    reason: str = ""
    confidence: float = 0.0    # 0-100
    urgency: str = "normal"    # "low", "normal", "high", "critical"
    ai_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 风控标记
    risk_level: str = "medium"  # "low", "medium", "high"
    stop_loss_pct: float = -5.0
    take_profit_pct: float = 10.0
    pnl_pct: float = 0.0        # 持仓盈亏%（由brain填充）
    avg_cost: float = 0.0       # 持仓成本价（由brain填充）
    
    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "signal": self.signal.value,
            "symbol": self.symbol,
            "name": self.name,
            "quantity": self.quantity,
            "price": self.price,
            "reason": self.reason,
            "confidence": self.confidence,
            "urgency": self.urgency,
            "ai_id": self.ai_id,
            "timestamp": self.timestamp.isoformat(),
            "risk_level": self.risk_level,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
        }


@dataclass
class PositionReview:
    """持仓审查结果"""
    symbol: str
    name: str
    quantity: int
    avg_cost: float
    current_price: float
    pnl_pct: float
    holding_days: int
    signal: DecisionSignal
    action: Action
    reason: str
    should_close: bool = False  # 是否应该清仓


class DecisionEngine:
    """
    统一决策引擎
    策略：先风控，再持仓审查，最后机会发现
    """
    
    def __init__(self, ai_id: str, risk_params: Dict):
        self.ai_id = ai_id
        self.stop_loss = risk_params.get("stop_loss_pct", -5.0)
        self.take_profit = risk_params.get("take_profit_pct", 10.0)
        self.max_position_pct = risk_params.get("position_max_pct", 0.4)
        self.total_position_max = risk_params.get("total_position_max_pct", 0.9)
    
    def review_positions(
        self,
        holdings: List[Dict],
        prices: Dict[str, Dict],
        risk_profile: Dict,
    ) -> List[PositionReview]:
        """
        审查所有持仓，给出操作建议
        风控优先：止损 > 止盈 > 持有
        """
        reviews = []
        
        for h in holdings:
            symbol = h["symbol"]
            name = h.get("name", symbol)
            avg_cost = h.get("avg_cost", 0)
            qty = h.get("quantity", 0)
            
            # 获取当前价格
            price_data = prices.get(symbol, {})
            current_price = price_data.get("price", avg_cost)
            pct_chg = price_data.get("pct_chg", 0)
            
            if current_price == 0 or avg_cost == 0:
                continue
            
            pnl_pct = (current_price - avg_cost) / avg_cost * 100
            holding_days = self._calc_holding_days(h)
            
            # 决策逻辑
            action = Action.HOLD
            signal = DecisionSignal.HOLD
            reason = "持仓不变"
            should_close = False
            
            # 1. 止损检查（优先级最高）
            if pnl_pct <= self.stop_loss:
                action = Action.SELL
                signal = DecisionSignal.STRONG_SELL
                reason = f"触发止损线 ({pnl_pct:.1f}%)"
                should_close = True
            
            # 2. 止盈检查
            elif pnl_pct >= self.take_profit:
                action = Action.SELL
                signal = DecisionSignal.SELL
                reason = f"达到止盈目标 ({pnl_pct:.1f}%)"
            
            # 3. 持仓超期检查
            elif holding_days > risk_profile.get("max_holding_days", 10):
                action = Action.SELL
                signal = DecisionSignal.SELL
                reason = f"持仓超时 ({holding_days}天)，换仓"
            
            # 4. 趋势走坏（跌幅过大）
            elif pct_chg < -3 and pnl_pct < -2:
                action = Action.SELL
                signal = DecisionSignal.SELL
                reason = f"趋势走坏，盘中下跌{pct_chg:.1f}%"
            
            reviews.append(PositionReview(
                symbol=symbol,
                name=name,
                quantity=qty,
                avg_cost=avg_cost,
                current_price=current_price,
                pnl_pct=pnl_pct,
                holding_days=holding_days,
                signal=signal,
                action=action,
                reason=reason,
                should_close=should_close,
            ))
        
        return reviews
    
    def find_buy_opportunities(
        self,
        cash: float,
        current_positions: List[Dict],
        market_data: Dict,
        watchlist: List[Dict],
        risk_profile: Dict,
    ) -> List[TradingDecision]:
        """
        发现买入机会
        在卖出现金后，决定买什么
        """
        decisions = []
        
        total_value = cash + sum(
            h.get("current_price", h.get("avg_cost", 0)) * h.get("quantity", 0)
            for h in current_positions
        )
        
        # 可用于买入的资金
        available_cash = cash
        for review in self.review_positions(current_positions, {}, risk_profile):
            if review.action in (Action.SELL, Action.HOLD):
                # 卖出的资金可以用于再买入（但要留部分现金）
                sell_value = review.quantity * review.current_price
                available_cash += sell_value * 0.8  # 80%回流
        
        if available_cash < 1000:
            return decisions
        
        # 从watchlist中选股
        for candidate in watchlist[:3]:  # 最多看3个
            symbol = candidate["symbol"]
            price = candidate.get("price", 0)
            pct_chg = candidate.get("pct_chg", 0)
            
            if price <= 0:
                continue
            
            # 计算可买数量（按单票上限）
            max_value = total_value * self.max_position_pct
            max_qty = int(max_value / price / 100) * 100  # 整手
            
            if max_qty < 100:
                continue
            
            # 趋势跟踪派：追涨；价值派：等回调
            style = risk_profile.get("style", "")
            if style == "trend_chaser":
                # 趋势派：要求今日涨幅 > 2%
                if pct_chg < 2:
                    continue
            elif style == "value_veteran":
                # 价值派：要求回调或横盘
                if pct_chg > 1:
                    continue
            
            decisions.append(TradingDecision(
                action=Action.BUY,
                signal=DecisionSignal.BUY if pct_chg < 5 else DecisionSignal.STRONG_BUY,
                symbol=symbol,
                name=candidate.get("name", symbol),
                quantity=max_qty,
                price=price,
                reason=f"选入关注：{pct_chg:+.2f}%",
                confidence=70 + min(pct_chg, 15),
                ai_id=self.ai_id,
            ))
        
        return decisions
    
    def _calc_holding_days(self, holding: Dict) -> int:
        """计算持仓天数"""
        try:
            updated_at = holding.get("updated_at", "")
            if not updated_at:
                return 0
            # 格式: "2026-04-17 15:30:00"
            buy_date = datetime.strptime(updated_at[:19], "%Y-%m-%d %H:%M:%S")
            return (datetime.now() - buy_date).days
        except:
            return 0
