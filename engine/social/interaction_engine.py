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
    
    # 嘲讽模板（按风格）— 每个风格至少8条，防止重复
    TAUNT_TEMPLATES = {
        "trend_chaser": [
            "又追高了吧？趋势都走完了你才进场，韭菜本菜了。",
            "你那止损线设了吗？估计早就被扫了。",
            "热点都熄火了你还在冲，佩服你的勇气。",
            "追涨杀跌的老手了，可惜每次都买在最高点。",
            "你这操作，机构看了都摇头。",
            "还在追题材？主力都出货了你不知道吧。",
            "趋势交易做成了趋势接盘，服了。",
            "这仓位管理，爆仓只是时间问题。",
            "你买的这个位置，我都想给你上个闹钟。",
            "动量策略追高没问题，但你追的是最后一棒啊。",
        ],
        "quant_queen": [
            "数据不支持你的判断，建议回测一下。",
            "概率上讲，你这操作胜率不到40%。",
            "模型显示你应该止损，而不是加仓。",
            "因子暴露这么大，不怕踩雷吗？",
            "你的量化策略里没有择时模块吗？",
            "夏普比这么低，还不如买国债。",
            "相关性分析做了吗？别把运气当实力。",
            "因子衰减这么快，你没观察到吗？",
            "回测天堂，实盘地狱，说的就是这种策略。",
            "风控模块是摆设吧？",
        ],
        "value_veteran": [
            "这才跌了几个点就慌了？格局小了。",
            "好公司急什么，时间是你的朋友。",
            "你真的理解什么叫安全边际吗？",
            "估值低不代表马上涨，你急什么。",
            "越跌越买的前提是公司基本面没问题，你确认吗？",
            "价值投资不是无脑持有，要跟踪护城河变化。",
            "你以为的黄金坑，可能是价值陷阱。",
            "逆向投资需要勇气，但更需要研究深度。",
            "买了就骂，卖了就吹，这不是投资是赌博。",
            "好球来了你反而跑了，后面追高的又是谁？",
        ],
        "momentum_kid": [
            "动量已经反转了你还追？刀口舔血！",
            "你这反应速度，行情都走完了。",
            "年轻人不要浪，小心被市场教育。",
            "动量策略追高没错，但你是在接飞刀。",
            "量价配合呢？缩量上涨还敢追？",
            "涨了你才相信，跌了你就不信了？",
            "趋势跟踪追市，结果追到了最高点。",
            "别人贪婪你更贪婪，这叫情绪共振，懂吗？",
            "你这买入时机，机构和量化都比你强。",
            "动量来了你不敢追，涨完了你才冲。",
        ],
        "turnaround_pro": [
            "逆向投资不是无脑抄底，你买在半山腰了。",
            "困境反转需要时间，你太急了。",
            "人都跑了，你还冲进去当接盘侠？",
            "困境反转的逻辑还在吗？行业拐点到了？",
            "你以为够低了，其实下面还有地下室。",
            "抄底抄在半山腰，痛吗？",
            "困境反转策略最怕的是越困境越反转不了。",
            "别和市场作对，趋势的修复需要催化剂。",
            "左侧交易的核心是分批建仓，你一把梭什么？",
            "困境中持有需要信仰，但更需要逻辑验证。",
        ],
        "tech_whiz": [
            "技术形态都破位了你还拿着？",
            "MACD死叉了你看不见？",
            "量价背离这么明显，你不做背离修复的吗？",
            "支撑破了就是破了，别侥幸。",
            "你看的这个技术指标，量化资金早就用它割韭菜了。",
            "kdj高位死叉还不跑，等着被套？",
            "技术分析做的是概率，你这个位置胜率很低。",
            "均线都空头排列了，还在幻想反弹？",
            "突破失败了，你知道这叫什么吗？叫假突破。",
            "图形派的核心是止损果断，你做到了吗？",
        ],
        "macro_master": [
            "宏观环境这么差，你还满仓操作？",
            "利率上行周期里，成长股估值杀你没看见？",
            "人民币贬值通道里，你买的是出口受益股吗？",
            "外围市场这么弱，A股能独善其身？",
            "宏观对冲你不懂，就别重仓赌方向。",
            "政策底到了，市场底还远着呢。",
            "你研究的这些宏观数据，机构早就知道了。",
            "汇率波动这么大，QDII基金你不考虑？",
            "宏观周期上行时你仓位呢？睡着了？",
            "懂宏观的人都加仓了，你却在减仓。",
        ],
        "dividend_hunter": [
            "高股息不代表不会跌，股价跌起来一样狠。",
            "你以为买高股息就能躺赚？股价跌死你。",
            "股息率高是因为股价跌出来的，注意区分。",
            "低估值高分红的公司，机构都不傻，为啥不抱团？",
            "吃股息要耐得住，别股价波动几天就跑了。",
            "高股息策略在加息周期里一样会挨打。",
            "你买的高股息股，分红真的能持续吗？",
            "别把分红当安全垫，股价跌50%你分红要10年回本。",
            "赚股息的人赚的是股价不跌的安心，你呢？",
            "红利策略要看DCF，不是光看股息率。",
        ],
    }

    # 全局嘲讽冷却：每条模板被使用后，4小时内不被同AI重复使用
    # 格式：{ai_id: {template_content[:20]: last_used_timestamp}}
    _taunt_cooldown: dict = {}
    
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
        import time

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
            # 过滤掉还在冷却中的模板（4小时内同AI不能重复使用同一模板）
            now = time.time()
            COOLDOWN = 4 * 3600  # 4小时
            available = [
                t for t in templates
                if self._taunt_cooldown.get(p.ai_id, {}).get(t[:20], 0) + COOLDOWN < now
            ]
            if not available:
                return None  # 所有模板都在冷却中
            chosen = random.choice(available)
            # 标记该模板已被使用
            if p.ai_id not in self._taunt_cooldown:
                self._taunt_cooldown[p.ai_id] = {}
            self._taunt_cooldown[p.ai_id][chosen[:20]] = now
            return chosen

        return None
    
    def generate_praise(self, target_post: Dict) -> Optional[str]:
        """生成围观/站台内容"""
        if random.random() > self.config.expressiveness / 150:
            return None
        return random.choice(self.PRAISE_TEMPLATES)
