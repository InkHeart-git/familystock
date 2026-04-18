"""
AI 股神争霸赛 - 核心模块
"""

from .characters import (
    AICharacter,
    RiskLevel,
    AI_CHARACTERS,
    RISK_PROFILES,
    get_character,
    get_all_characters,
    get_risk_profile
)

from .bbs import (
    Post,
    PostType,
    PostTrigger,
    ContentGenerator,
    BBSSystem
)

__all__ = [
    'AICharacter',
    'RiskLevel',
    'AI_CHARACTERS',
    'RISK_PROFILES',
    'get_character',
    'get_all_characters',
    'get_risk_profile',
    'Post',
    'PostType',
    'PostTrigger',
    'ContentGenerator',
    'BBSSystem'
]
