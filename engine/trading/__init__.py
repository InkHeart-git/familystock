"""交易决策模块"""
from engine.trading.decision_engine import DecisionEngine, TradingDecision, Action, DecisionSignal, PositionReview

# 向后兼容：从 engine/trading.py (旧文件) 导入旧版类，避免循环导入
import importlib.util
import sys

# 直接从 engine/trading.py 文件加载旧版类
_trading_old_spec = importlib.util.spec_from_file_location("_trading_old", "/var/www/ai-god-of-stocks/engine/trading.py")
_trading_old = importlib.util.module_from_spec(_trading_old_spec)
sys.modules["_trading_old"] = _trading_old
_trading_old_spec.loader.exec_module(_trading_old)

ActionType = _trading_old.ActionType
Holding = _trading_old.Holding
Portfolio = _trading_old.Portfolio
TradeDecision = _trading_old.TradeDecision
TradingEngine = _trading_old.TradingEngine
PortfolioManager = _trading_old.PortfolioManager

__all__ = [
    "DecisionEngine", "TradingDecision", "Action", "DecisionSignal", "PositionReview",
    "ActionType", "Holding", "Portfolio", "TradeDecision",
    "TradingEngine", "PortfolioManager"
]
