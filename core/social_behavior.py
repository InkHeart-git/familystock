"""
AI 股神争霸赛 - 社交人格系统
让每个AI像真人一样有独特的社交行为模式
"""

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime, timedelta
import random


@dataclass
class SocialTraits:
    """社交人格特质"""
    expressiveness: int  # 表现欲 0-100
    talkativeness: int   # 话痨度 0-100
    aggressiveness: int  # 攻击性 0-100
    emotional_stability: int  # 情绪稳定性 0-100
    conformity: int      # 从众性 0-100
    

# ==================== 10个AI的社交人格定义 ====================

SOCIAL_PERSONALITIES = {
    # 风云五虎
    "trend_chaser": SocialTraits(
        expressiveness=85,      # 很高，喜欢晒收益
        talkativeness=70,       # 中等偏长，喜欢分析
        aggressiveness=75,      # 经常挑衅其他AI
        emotional_stability=40, # 盈亏波动大，影响发帖
        conformity=80           # 追逐热点
    ),
    "quant_queen": SocialTraits(
        expressiveness=50,      # 中等，只在有数据时发言
        talkativeness=60,       # 专业分析，不长不短
        aggressiveness=30,      # 偶尔吐槽，但不主动攻击
        emotional_stability=90, # 理性，不受盈亏影响
        conformity=20           # 独立判断，不跟风
    ),
    "value_veteran": SocialTraits(
        expressiveness=35,      # 低，惜字如金
        talkativeness=80,       # 一旦发言就是长篇大论
        aggressiveness=20,      # 温和，喜欢教导
        emotional_stability=95, # 极稳，长期视角
        conformity=10           # 独立思考
    ),
    "scalper_fairy": SocialTraits(
        expressiveness=90,      # 极高，实时播报
        talkativeness=50,       # 简洁急促
        aggressiveness=65,      # 喜欢反驳
        emotional_stability=35, # 情绪随盘口波动
        conformity=70           # 跟随情绪
    ),
    "macro_master": SocialTraits(
        expressiveness=60,      # 有观点就分享
        talkativeness=75,       # 宏观分析需要篇幅
        aggressiveness=45,      # 偶尔点评别人短视
        emotional_stability=85, # 宏观视角稳
        conformity=30           # 独立判断
    ),
    # 灵动小五
    "tech_whiz": SocialTraits(
        expressiveness=75,      # 高，喜欢分享新技术
        talkativeness=65,       # 技术解释需要一定篇幅
        aggressiveness=55,      # 对技术判断很自信
        emotional_stability=60, # 一般
        conformity=40           # 适度独立
    ),
    "dividend_hunter": SocialTraits(
        expressiveness=40,      # 低，沉稳
        talkativeness=55,       # 适中
        aggressiveness=25,      # 温和
        emotional_stability=90, # 很稳，收息心态
        conformity=15           # 独立判断
    ),
    "turnaround_pro": SocialTraits(
        expressiveness=70,      # 较高，发现机会喜欢分享
        talkativeness=70,       # 需要解释反转逻辑
        aggressiveness=50,      # 中等
        emotional_stability=55, # 一般，等反转需要耐心
        conformity=35           # 逆向思维
    ),
    "momentum_kid": SocialTraits(
        expressiveness=80,      # 高，年轻活跃
        talkativeness=60,       # 适中
        aggressiveness=70,      # 高，喜欢挑战
        emotional_stability=45, # 较低，年轻人冲动
        conformity=75           # 跟随动量
    ),
    "event_driven": SocialTraits(
        expressiveness=65,      # 中等偏高
        talkativeness=65,       # 需要解释事件影响
        aggressiveness=40,      # 中等
        emotional_stability=70, # 较好
        conformity=50           # 看事件而定
    )
}


class SocialBehaviorEngine:
    """社交行为引擎"""
    
    def __init__(self):
        self.last_post_time: Dict[str, datetime] = {}
        self.last_reply_time: Dict[str, datetime] = {}
        self.daily_post_count: Dict[str, int] = {}
        
    def get_traits(self, ai_id: str) -> SocialTraits:
        """获取AI的社交人格"""
        return SOCIAL_PERSONALITIES.get(ai_id, SocialTraits(50, 50, 50, 50, 50))
    
    def should_post(self, ai_id: str, context: Dict) -> bool:
        """
        决定是否应该发帖
        
        Args:
            ai_id: AI角色ID
            context: {
                'today_pnl_pct': 今日盈亏百分比,
                'is_hot_topic': 是否是热门话题,
                'hour': 当前小时,
                'is_trading_time': 是否交易时间
            }
        """
        traits = self.get_traits(ai_id)
        now = datetime.now()
        
        # 基础概率（由表现欲决定）
        base_prob = traits.expressiveness / 100
        
        # 情绪加成
        emotion_boost = self._calculate_emotion_boost(traits, context)
        
        # 话题热度加成
        hot_boost = self._calculate_hot_boost(traits, context)
        
        # 时段调整
        time_adjust = self._calculate_time_adjustment(traits, context)
        
        # 冷却时间惩罚
        cooldown_penalty = self._calculate_cooldown_penalty(ai_id, now)
        
        # 最终概率
        final_prob = base_prob + emotion_boost + hot_boost + time_adjust + cooldown_penalty
        final_prob = max(0, min(1, final_prob))  # 限制在0-1之间
        
        return random.random() < final_prob
    
    def should_reply(self, ai_id: str, target_post: Dict, context: Dict) -> bool:
        """
        决定是否应该回复某条帖子
        
        Args:
            ai_id: 自己的ID
            target_post: 目标帖子信息
            context: 上下文
        """
        traits = self.get_traits(ai_id)
        now = datetime.now()
        
        # 基础概率
        base_prob = traits.expressiveness / 100 * 0.6  # 回复比发帖概率低
        
        # 被@加成（任何人被@都会大概率回复）
        mention_boost = 0.4 if context.get('was_mentioned') else 0
        
        # 攻击性加成（喜欢反驳别人）
        if target_post.get('ai_id') != ai_id:
            aggress_boost = (traits.aggressiveness / 100) * 0.2
        else:
            aggress_boost = 0
        
        # 话题相关度（从众性高的人更容易参与热门讨论）
        if context.get('is_hot_topic'):
            conformity_boost = (traits.conformity / 100) * 0.15
        else:
            conformity_boost = 0
        
        # 冷却惩罚
        cooldown_penalty = self._calculate_reply_cooldown(ai_id, now)
        
        final_prob = base_prob + mention_boost + aggress_boost + conformity_boost + cooldown_penalty
        final_prob = max(0, min(1, final_prob))
        
        return random.random() < final_prob
    
    def get_reply_style(self, ai_id: str, target_post: Dict) -> Dict:
        """
        获取回复风格
        
        Returns:
            {
                'tone': 'provocative'|'supportive'|'neutral'|'analytical',
                'length': 'short'|'medium'|'long',
                'emotion': 'excited'|'calm'|'frustrated'|'confident'
            }
        """
        traits = self.get_traits(ai_id)
        
        # 确定语气
        if traits.aggressiveness > 70 and target_post.get('ai_id') != ai_id:
            tone = 'provocative'  # 挑衅
        elif traits.aggressiveness < 30:
            tone = 'supportive'   # 支持/教导
        elif traits.emotional_stability > 70:
            tone = 'analytical'   # 理性分析
        else:
            tone = 'neutral'      # 中性
        
        # 确定长度
        if traits.talkativeness > 70:
            length = 'long'
        elif traits.talkativeness < 40:
            length = 'short'
        else:
            length = 'medium'
        
        # 确定情绪
        if traits.emotional_stability < 40:
            emotion = 'excited' if random.random() > 0.5 else 'frustrated'
        elif traits.emotional_stability > 80:
            emotion = 'calm'
        else:
            emotion = 'confident'
        
        return {'tone': tone, 'length': length, 'emotion': emotion}
    
    def get_non_trading_behavior(self, ai_id: str, hour: int) -> Optional[str]:
        """
        获取非交易时段的行为
        
        Returns:
            行为类型或None
        """
        traits = self.get_traits(ai_id)
        
        # 晚间复盘时间 (15:00-22:00)
        if 15 <= hour <= 22:
            prob = traits.expressiveness / 100
            if random.random() < prob * 0.5:  # 表现欲高的人更可能复盘
                return 'evening_review'
        
        # 深夜时间 (22:00-7:00) - 真人要睡觉
        elif hour >= 22 or hour <= 7:
            # 极低概率夜猫子发帖
            if random.random() < 0.02:
                return 'late_night_thought'
            return None
        
        # 早盘前 (7:00-9:30)
        elif 7 <= hour < 9:
            if hour == 8:  # 8点后开始活跃
                prob = traits.expressiveness / 100
                if random.random() < prob * 0.3:
                    return 'pre_market_preview'
        
        return None
    
    def _calculate_emotion_boost(self, traits: SocialTraits, context: Dict) -> float:
        """计算情绪加成"""
        pnl = context.get('today_pnl_pct', 0)
        stability = traits.emotional_stability
        
        # 情绪不稳定的人更容易受盈亏影响
        volatility_factor = (100 - stability) / 100
        
        if pnl > 3:  # 大赚
            return 0.25 * volatility_factor  # 亢奋，更爱发帖
        elif pnl > 1:  # 小赚
            return 0.1 * volatility_factor
        elif pnl < -3:  # 大亏
            return -0.15 * volatility_factor  # 沮丧，可能沉默
        elif pnl < -1:  # 小亏
            return -0.05 * volatility_factor
        
        return 0
    
    def _calculate_hot_boost(self, traits: SocialTraits, context: Dict) -> float:
        """计算热门话题加成"""
        if context.get('is_hot_topic'):
            return (traits.conformity / 100) * 0.2
        return 0
    
    def _calculate_time_adjustment(self, traits: SocialTraits, context: Dict) -> float:
        """计算时段调整"""
        if not context.get('is_trading_time'):
            # 非交易时间，表现欲高的人更活跃
            return (traits.expressiveness - 50) / 100 * 0.1
        return 0
    
    def _calculate_cooldown_penalty(self, ai_id: str, now: datetime) -> float:
        """计算发帖冷却惩罚"""
        last_post = self.last_post_time.get(ai_id)
        if not last_post:
            return 0
        
        minutes_since = (now - last_post).total_seconds() / 60
        
        if minutes_since < 15:
            return -0.4  # 15分钟内刚发过，大幅降低概率
        elif minutes_since < 60:
            return -0.2  # 1小时内
        elif minutes_since < 180:
            return -0.1  # 3小时内
        
        return 0
    
    def _calculate_reply_cooldown(self, ai_id: str, now: datetime) -> float:
        """计算回复冷却惩罚"""
        last_reply = self.last_reply_time.get(ai_id)
        if not last_reply:
            return 0
        
        minutes_since = (now - last_reply).total_seconds() / 60
        
        if minutes_since < 10:
            return -0.3
        elif minutes_since < 30:
            return -0.15
        
        return 0
    
    def record_post(self, ai_id: str):
        """记录发帖时间"""
        self.last_post_time[ai_id] = datetime.now()
        self.daily_post_count[ai_id] = self.daily_post_count.get(ai_id, 0) + 1
    
    def record_reply(self, ai_id: str):
        """记录回复时间"""
        self.last_reply_time[ai_id] = datetime.now()
    
    def reset_daily_count(self):
        """重置每日计数"""
        self.daily_post_count.clear()


# 全局实例
social_engine = SocialBehaviorEngine()
