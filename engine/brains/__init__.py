"""AI股神争霸 - 统一智能大脑系统"""
from engine.brains.base import BaseBrain, CharacterConfig, Personality, Session, get_current_session
from engine.brains.trend_chaser import TrendChaserBrain
from engine.brains.quant_queen import QuantQueenBrain
from engine.brains.value_veteran import ValueVeteranBrain
from engine.brains.momentum_kid import MomentumKidBrain
from engine.brains.macro_master import MacroMasterBrain
from engine.brains.tech_whiz import TechWhizBrain
from engine.brains.dividend_hunter import DividendHunterBrain
from engine.brains.turnaround_pro import TurnaroundProBrain
from engine.brains.event_driven import EventDrivenBrain
from engine.brains.mike import MikeBrain

# 导出所有AI大脑
ALL_BRAINS = [
    TrendChaserBrain,
    QuantQueenBrain,
    ValueVeteranBrain,
    MomentumKidBrain,
    MacroMasterBrain,
    TechWhizBrain,
    DividendHunterBrain,
    TurnaroundProBrain,
    EventDrivenBrain,
    MikeBrain,
]

__all__ = [
    "BaseBrain", "CharacterConfig", "Personality", "Session", "get_current_session",
    "TrendChaserBrain", "QuantQueenBrain", "ValueVeteranBrain",
    "MomentumKidBrain", "MacroMasterBrain", "TechWhizBrain",
    "DividendHunterBrain", "TurnaroundProBrain", "EventDrivenBrain",
    "MikeBrain",
    "ALL_BRAINS",
]
