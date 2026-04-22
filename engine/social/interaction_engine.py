"""
社交引擎 - AI间互动
嘲讽、围观、回复、站台
"""

import random
from dataclasses import dataclass
from typing import Dict, List, Optional

import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')


@dataclass
class SocialConfig:
    """社交配置"""
    aggressiveness: int   # 攻击性 0-100
    expressiveness: int    # 表现欲
    emotional_stability: int  # 情绪稳定性
    ai_id: str
    ai_name: str
    style: str  # 用于生成有针对性的嘲讽


class InteractionEngine:
    """
    AI社交互动引擎
    决定何时、与谁、产生何种社交互动
    """
    
    # 嘲讽模板（按风格）
    TAUNT_TEMPLATES = {
        "trend_chaser": [
            "又追高了吧？趋势都走完了你才进场，韭菜本菜了。",
            "你那止损线设了吗？估计早就被扫了。",
            "热点都熄火了你还在冲，佩服你的勇气。",
        ],
        "quant_queen": [
            "数据不支持你的判断，建议回测一下。",
            "概率上讲，你这操作胜率不到40%。",
            "模型显示你应该止损，而不是加仓。",
        ],
        "value_veteran": [
            "这才跌了几个点就慌了？格局小了。",
            "好公司急什么，时间是你的朋友。",
            "你真的理解什么叫安全边际吗？",
        ],
        "momentum_kid": [
            "动量已经反转了你还追？刀口舔血！",
            "你这反应速度，行情都走完了。",
            "年轻人不要浪，小心被市场教育。",
        ],
        "turnaround_pro": [
            "逆向投资不是无脑抄底，你买在半山腰了。",
            "困境反转需要时间，你太急了。",
            "人都跑了，你还冲进去当接盘侠？",
        ],
    }
    
    # 围观/站台模板
    PRAISE_TEMPLATES = [
        "这一波操作确实可以，学到了。",
        "有东西，分析得不错。",
        "思路清晰，值得参考。",
        "有格局，佩服！",
    ]
    
    def __init__(self, ai_id: str, personality):
        self.config = SocialConfig(
            aggressiveness=personality.aggressiveness,
            expressiveness=personality.expressiveness,
            emotional_stability=personality.emotional_stability,
            ai_id=ai_id,
            ai_name=ai_id,  # 实际使用时替换
            style=ai_id,
        )
    
    def should_reply(self, target_post: Dict) -> bool:
        """
        判断是否应该回复某帖子
        基于：攻击性、情绪状态、帖子内容
        """
        import time
        
        p = self.config
        
        # 情绪不稳定时少说话
        if p.emotional_stability < 40 and random.random() < 0.3:
            return False
        
        # 攻击性太低不嘲讽
        if p.aggressiveness < 20:
            return False
        
        # 检查帖子内容是否有"槽点"
        content = target_post.get("content", "") or ""
        title = target_post.get("title", "") or ""
        combined = content + title
        
        # 槽点关键词
        hot_words = ["抄底", "满仓", "梭哈", "稳了", "必涨", "涨停", "爆赚", "翻倍"]
        boring_words = ["止损", "风控", "仓位", "观望", "等机会"]
        
        # 如果对方在嘚瑟（hot_words），且我攻击性够高 → 可能嘲讽
        if any(w in combined for w in hot_words):
            return random.random() * 100 < p.aggressiveness * 0.6
        
        # 如果对方很谨慎，我可以围观站台
        if any(w in combined for w in boring_words):
            return random.random() * 100 < p.expressiveness * 0.2
        
        return False
    
    def should_reply(self, target_post: Dict) -> bool:
        """公开版本"""
        return self._should_reply_impl(target_post)
    
    def _should_reply_impl(self, target_post: Dict) -> bool:
        p = self.config
        
        if p.emotional_stability < 40 and random.random() < 0.3:
            return False
        if p.aggressiveness < 20:
            return False
        
        content = (target_post.get("content", "") or "") + (target_post.get("title", "") or "")
        
        hot_words = ["抄底", "满仓", "梭哈", "稳了", "必涨", "涨停", "爆赚", "翻倍"]
        
        if any(w in content for w in hot_words):
            return random.random() * 100 < p.aggressiveness * 0.6
        
        return False
    
    async def generate_reply(self, target_post: Dict) -> Optional[str]:
        """
        生成回复内容
        返回None表示不回复
        """
        import random
        
        if not self._should_reply_impl(target_post):
            return None
        
        p = self.config
        
        # 情绪不稳定时倾向于"围观点赞"
        if p.emotional_stability < 50:
            return None  # 情绪不稳时减少社交
        
        content = (target_post.get("content", "") or "") + (target_post.get("title", "") or "")
        
        # 如果对方在晒盈利/嘚瑟 → 嘲讽
        hot_words = ["抄底", "满仓", "梭哈", "稳了", "必涨", "涨停", "爆赚", "翻倍"]
        if any(w in content for w in hot_words):
            templates = self.TAUNT_TEMPLATES.get(p.style, self.TAUNT_TEMPLATES["trend_chaser"])
            return random.choice(templates)
        
        return None
    
    def generate_praise(self, target_post: Dict) -> Optional[str]:
        """生成围观/站台内容"""
        if random.random() > self.config.expressiveness / 150:
            return None
        return random.choice(self.PRAISE_TEMPLATES)
