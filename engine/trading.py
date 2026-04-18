"""
AI 股神争霸赛 - 交易决策引擎
买卖决策、仓位管理、风险控制
"""

import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
import logging

from core.characters import get_character, get_risk_profile
from data.preprocessor import MarketData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionType(Enum):
    """交易动作类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Holding:
    """持仓记录"""
    symbol: str
    name: str
    quantity: int
    buy_price: float
    buy_date: date
    current_price: float = 0.0
    
    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price
    
    @property
    def cost_basis(self) -> float:
        return self.quantity * self.buy_price
    
    @property
    def unrealized_pnl(self) -> float:
        return self.market_value - self.cost_basis
    
    @property
    def unrealized_pnl_pct(self) -> float:
        if self.buy_price == 0:
            return 0
        return (self.current_price - self.buy_price) / self.buy_price


@dataclass
class Portfolio:
    """投资组合"""
    ai_id: str
    cash: float
    holdings: List[Holding] = field(default_factory=list)
    total_value: float = 0.0
    
    def update_prices(self, market_data: Dict[str, float]):
        """更新持仓价格"""
        for holding in self.holdings:
            if holding.symbol in market_data:
                holding.current_price = market_data[holding.symbol]
        
        self.total_value = self.cash + sum(h.market_value for h in self.holdings)
    
    @property
    def total_market_value(self) -> float:
        return sum(h.market_value for h in self.holdings)
    
    @property
    def position_ratio(self) -> float:
        if self.total_value == 0:
            return 0
        return self.total_market_value / self.total_value
    
    def get_holding(self, symbol: str) -> Optional[Holding]:
        """获取指定持仓"""
        for h in self.holdings:
            if h.symbol == symbol:
                return h
        return None


@dataclass
class TradeDecision:
    """交易决策"""
    action: ActionType
    symbol: str
    name: str
    quantity: int
    price: float
    reason: str
    confidence: float
    ai_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "action": self.action.value,
            "symbol": self.symbol,
            "name": self.name,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.quantity * self.price,
            "reason": self.reason,
            "confidence": self.confidence,
            "ai_id": self.ai_id,
            "timestamp": self.timestamp.isoformat()
        }


class TradingEngine:
    """交易决策引擎"""
    
    def __init__(self, character_id: str, portfolio: Portfolio):
        self.character_id = character_id
        self.character = get_character(character_id)
        self.risk_profile = get_risk_profile(character_id)
        self.portfolio = portfolio
    
    async def make_decision(
        self, 
        market_data: MarketData,
        selected_stocks: List[Dict]
    ) -> Optional[TradeDecision]:
        """
        交易决策主流程
        
        Returns:
            TradeDecision: 交易决策，None表示不交易
        """
        logger.info(f"[{self.character.name}] 开始交易决策...")
        
        # 1. 检查是否需要卖出
        sell_decision = await self._check_sell_signals(market_data)
        if sell_decision:
            logger.info(f"触发卖出信号: {sell_decision.symbol}")
            return sell_decision
        
        # 2. 检查是否可以买入
        if self.portfolio.cash > 0:
            buy_decision = await self._check_buy_signals(market_data, selected_stocks)
            if buy_decision:
                logger.info(f"触发买入信号: {buy_decision.symbol}")
                return buy_decision
        
        # 3. 默认持有
        logger.info("无交易信号，继续持有")
        return None
    
    async def _check_sell_signals(self, market_data: MarketData) -> Optional[TradeDecision]:
        """检查卖出信号"""
        
        for holding in self.portfolio.holdings:
            symbol = holding.symbol
            
            # 获取当前价格
            current_price = self._get_current_price(symbol, market_data)
            if current_price == 0:
                continue
            
            holding.current_price = current_price
            
            # 计算盈亏
            pnl_pct = holding.unrealized_pnl_pct
            holding_days = (datetime.now().date() - holding.buy_date).days
            
            # 止盈信号
            take_profit_pct = self.risk_profile['take_profit']
            if pnl_pct >= take_profit_pct:
                return TradeDecision(
                    action=ActionType.SELL,
                    symbol=symbol,
                    name=holding.name,
                    quantity=holding.quantity,
                    price=current_price,
                    reason=f"止盈卖出，收益{pnl_pct*100:.1f}%（目标{take_profit_pct*100:.1f}%）",
                    confidence=0.9,
                    ai_id=self.character_id
                )
            
            # 止损信号
            stop_loss_pct = self.risk_profile['stop_loss']
            if pnl_pct <= stop_loss_pct:
                return TradeDecision(
                    action=ActionType.SELL,
                    symbol=symbol,
                    name=holding.name,
                    quantity=holding.quantity,
                    price=current_price,
                    reason=f"止损卖出，亏损{abs(pnl_pct)*100:.1f}%（止损线{stop_loss_pct*100:.1f}%）",
                    confidence=0.95,
                    ai_id=self.character_id
                )
            
            # 持仓时间信号
            max_holding_days = self.risk_profile['max_holding_days']
            if holding_days >= max_holding_days:
                return TradeDecision(
                    action=ActionType.SELL,
                    symbol=symbol,
                    name=holding.name,
                    quantity=holding.quantity,
                    price=current_price,
                    reason=f"持仓时间到期，已持有{holding_days}天（最大{max_holding_days}天）",
                    confidence=0.7,
                    ai_id=self.character_id
                )
        
        return None
    
    async def _check_buy_signals(
        self, 
        market_data: MarketData,
        selected_stocks: List[Dict]
    ) -> Optional[TradeDecision]:
        """检查买入信号"""
        
        if not selected_stocks:
            return None
        
        # 检查仓位限制
        max_position = self.risk_profile['total_position_max']
        if self.portfolio.position_ratio >= max_position:
            logger.info(f"仓位已满({self.portfolio.position_ratio*100:.1f}%)，不再买入")
            return None
        
        # 检查持仓数量限制（最多同时持有3只股票）
        if len(self.portfolio.holdings) >= 3:
            logger.info(f"持仓数量已达上限({len(self.portfolio.holdings)}只)")
            return None
        
        # 选择最佳买入标的
        for stock in selected_stocks:
            symbol = stock['symbol']
            
            # 检查是否已持仓
            if self.portfolio.get_holding(symbol):
                continue
            
            # 获取当前价格
            current_price = self._get_current_price(symbol, market_data)
            if current_price == 0:
                continue
            
            # 计算买入数量
            quantity = self._calculate_position_size(stock, current_price)
            
            if quantity >= 100:  # 至少买1手
                stock_name = stock.get('name') or stock['symbol']
                return TradeDecision(
                    action=ActionType.BUY,
                    symbol=symbol,
                    name=stock_name,
                    quantity=quantity,
                    price=current_price,
                    reason=stock.get('llm_reason', stock.get('reasons', ['技术选股'])[0]),
                    confidence=stock.get('llm_confidence', 0.5),
                    ai_id=self.character_id
                )
        
        return None
    
    def _get_current_price(self, symbol: str, market_data: MarketData) -> float:
        """获取股票当前价格"""
        
        # 从行情数据中查找
        for stock in market_data.stock_quotes:
            if stock['symbol'] == symbol:
                return stock.get('close', 0)
        
        return 0
    
    def _calculate_position_size(self, stock: Dict, price: float) -> int:
        """计算买入数量（100股整数倍）"""
        
        # 单票最大仓位
        single_max = self.risk_profile['single_position_max']
        max_position_value = self.portfolio.total_value * single_max
        
        # 可用资金
        available_cash = self.portfolio.cash
        
        # 取较小值
        position_value = min(max_position_value, available_cash * 0.9)  # 留10%现金
        
        # 计算股数（100股整数倍）
        quantity = int(position_value / price / 100) * 100
        
        logger.info(
            f"仓位计算: 可用资金{available_cash:.0f}, "
            f"目标仓位{position_value:.0f}, "
            f"价格{price:.2f}, 数量{quantity}"
        )
        
        return quantity
    
    def execute_trade(self, decision: TradeDecision) -> bool:
        """执行交易（更新持仓）"""
        
        if decision.action == ActionType.BUY:
            # 买入
            amount = decision.quantity * decision.price
            
            if amount > self.portfolio.cash:
                logger.error(f"资金不足: 需要{amount:.2f}，只有{self.portfolio.cash:.2f}")
                return False
            
            # 扣除现金
            self.portfolio.cash -= amount
            
            # 添加持仓
            holding = Holding(
                symbol=decision.symbol,
                name=decision.name,
                quantity=decision.quantity,
                buy_price=decision.price,
                buy_date=datetime.now().date(),
                current_price=decision.price
            )
            self.portfolio.holdings.append(holding)
            
            # 更新总资产
            self.portfolio.total_value = self.portfolio.cash + sum(h.market_value for h in self.portfolio.holdings)
            
            logger.info(
                f"买入成功: {decision.name} {decision.quantity}股 "
                f"@{decision.price:.2f}，金额{amount:.2f}"
            )
            return True
            
        elif decision.action == ActionType.SELL:
            # 卖出
            holding = self.portfolio.get_holding(decision.symbol)
            if not holding:
                logger.error(f"持仓不存在: {decision.symbol}")
                return False
            
            # 计算卖出金额
            amount = decision.quantity * decision.price
            
            # 增加现金
            self.portfolio.cash += amount
            
            # 移除持仓
            self.portfolio.holdings.remove(holding)
            
            # 计算盈亏
            pnl = amount - holding.cost_basis
            pnl_pct = pnl / holding.cost_basis * 100
            
            logger.info(
                f"卖出成功: {decision.name} {decision.quantity}股 "
                f"@{decision.price:.2f}，金额{amount:.2f}，"
                f"盈亏{pnl:+.2f}({pnl_pct:+.2f}%)"
            )
            return True
        
        return False


class PortfolioManager:
    """投资组合管理器 - 使用PostgreSQL持久化"""
    
    def __init__(self, db_manager=None):
        self.db = db_manager
    
    async def load_portfolio(self, ai_id: str) -> Portfolio:
        """从数据库加载投资组合"""
        if self.db:
            return await self.db.get_portfolio(ai_id)
        
        # 如果没有数据库连接，返回默认
        return Portfolio(
            ai_id=ai_id,
            cash=1000000.0,
            holdings=[],
            total_value=1000000.0
        )
    
    async def save_portfolio(self, portfolio: Portfolio):
        """保存投资组合到数据库"""
        if self.db:
            await self.db.save_portfolio(portfolio)
    
    async def get_all_portfolios(self) -> Dict[str, Portfolio]:
        """获取所有AI的投资组合"""
        from core.characters import get_all_characters
        
        portfolios = {}
        for char_id in get_all_characters().keys():
            portfolios[char_id] = await self.load_portfolio(char_id)
        
        return portfolios
    
    async def update_portfolio_value(self, ai_id: str):
        """更新投资组合的当前价值（从数据库）"""
        if not self.db:
            return
        
        portfolio = await self.load_portfolio(ai_id)
        # 触发持仓更新逻辑
        return portfolio


# 测试代码
async def test():
    """测试交易引擎"""
    
    # 创建投资组合
    portfolio = Portfolio(
        ai_id="trend_chaser",
        cash=1000000.0,
        holdings=[],
        total_value=1000000.0
    )
    
    # 创建交易引擎
    engine = TradingEngine("trend_chaser", portfolio)
    
    # 模拟市场数据
    from data.preprocessor import DataPreprocessor
    preprocessor = DataPreprocessor()
    
    try:
        market_data = await preprocessor.prepare_market_data("2025-03-28")
        
        # 模拟选股结果
        selected_stocks = [
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "close": 12.5,
                "pct_chg": 3.5,
                "llm_confidence": 0.8,
                "llm_reason": "银行板块龙头，资金净流入"
            },
            {
                "symbol": "000002.SZ",
                "name": "万科A",
                "close": 18.2,
                "pct_chg": 2.8,
                "llm_confidence": 0.75,
                "llm_reason": "地产政策利好，估值修复"
            }
        ]
        
        # 测试买入决策
        decision = await engine.make_decision(market_data, selected_stocks)
        
        if decision:
            print(f"\n交易决策:")
            print(f"  动作: {decision.action.value}")
            print(f"  股票: {decision.name} ({decision.symbol})")
            print(f"  数量: {decision.quantity}")
            print(f"  价格: {decision.price:.2f}")
            print(f"  金额: {decision.quantity * decision.price:.2f}")
            print(f"  理由: {decision.reason}")
            print(f"  置信度: {decision.confidence:.2f}")
            
            # 执行交易
            engine.execute_trade(decision)
            
            print(f"\n持仓更新:")
            print(f"  现金: {portfolio.cash:.2f}")
            print(f"  持仓数量: {len(portfolio.holdings)}")
            print(f"  总市值: {portfolio.total_value:.2f}")
        else:
            print("无交易信号")
            
    finally:
        await preprocessor.close()

if __name__ == "__main__":
    asyncio.run(test())
