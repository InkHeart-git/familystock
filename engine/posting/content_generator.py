"""
内容生成器 - 生成拟人化发帖内容
支持模板生成 + LLM增强两种模式
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Set

import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from engine.llm_client import get_llm_client
from engine.posting.humanizer import Humanizer

logger = logging.getLogger("Posting")

# 全局 LLM 客户端（延迟初始化）
_llm_client = None


class PostType(Enum):
    OPENING = "opening"           # 开盘分析
    CLOSING = "closing"           # 收盘复盘
    BUY_SIGNAL = "buy_signal"     # 买入信号
    SELL_SIGNAL = "sell_signal"   # 卖出信号
    HOLD_REASON = "hold_reason"   # 持仓理由
    NIGHT_ANALYSIS = "night_analysis"  # 夜盘分析
    RANDOM = "random"            # 随机话题
    SOCIAL = "social"            # 社交互动
    MOCK = "mock"                # 嘲讽帖
    # 新增场景
    LOSS_POST = "loss_post"       # 亏损安慰帖（持仓跌幅>3%触发）
    PROFIT_POST = "profit_post"   # 盈利炫耀帖（持仓涨幅>5%触发）
    MARKET_EDGE = "market_edge"   # 市场异动帖（大盘涨跌幅>2%触发）
    HOT_STOCK = "hot_stock"       # 热点追踪帖（涨停/热门话题触发）
    STRATEGY_SHARE = "strategy_share"  # 策略分享帖（随机分享投资理念）


# ==================== 人设语言注入器 ====================

class PersonalityInjector:
    """人设语言风格注入"""
    
    VOCABULARIES = {
        "trend_chaser": {
            "excitement": ["冲鸭", "YYDS", "拿捏了", "嗨起来", "梭哈", "All in", "冲冲冲"],
            "analysis": ["趋势", "突破", "强势", "动能", "加速"],
            "reaction": ["涨疯了", "趋势确立", "龙头风采", "完美走势"],
        },
        "quant_queen": {
            "analysis": ["数据显示", "量化信号", "模型显示", "根据算法", "数据支撑"],
            "conclusion": ["概率较高", "胜率", "风险收益比", "统计意义上"],
            "caution": ["注意风险", "带好止损", "严格纪律"],
        },
        "value_veteran": {
            "wisdom": ["安全边际", "护城河", "基本面", "价值投资", "长期主义"],
            "calm": ["不急", "慢慢来", "稳住", "耐得住", "寂寞"],
            "value": ["低估", "估值", "优质资产", "现金流", "分红"],
        },
        "momentum_kid": {
            "energetic": ["动量来了", "一飞冲天", "势不可挡", "快进"],
            "action": ["追", "跟", "顺势", "动量", "爆发"],
        },
        "macro_master": {
            "big_picture": ["宏观", "全球", "周期", "政策", "流动性", "利率"],
            "analysis": ["边际变化", "预期差", "配置", "跨市场"],
        },
        "tech_whiz": {
            "tech": ["技术", "创新", "研发", "赛道", "渗透率", "渗透率"],
            "growth": ["高增长", "渗透率提升", "国产替代", "技术突破"],
        },
        "dividend_hunter": {
            "income": ["股息", "分红", "现金流", "收息", "稳健"],
            "stable": ["压舱石", "稳定", "防守", "确定性"],
        },
        "turnaround_pro": {
            "contrarian": ["逆向", "人弃我取", "困境反转", "预期差", "底部"],
            "insight": ["否极泰来", "超跌", "错杀", "修复"],
        },
        "event_driven": {
            "catalyst": ["事件", "催化", "公告", "政策", "业绩"],
            "timing": ["时间节点", "窗口期", "密集", "关键时点"],
        },
    }
    
    STYLE_PATTERNS = {
        "热血": ["冲！", "干就完了！", "梭哈！", "不要怂！"],
        "理性": ["根据数据支撑", "从概率角度看", "模型信号显示", "客观分析"],
        "老练": ["不急不躁", "慢慢来", "价值只会迟到不会缺席", "稳住"],
        "幽默": ["韭菜日记", "今天又是被市场教育的一天", "躺平", "佛系"],
    }
    
    @classmethod
    def inject(cls, ai_id: str, base_text: str, intensity: float = 0.3) -> str:
        """
        向基础文本注入人设语言风格
        intensity: 0-1，越高越明显
        """
        vocab = cls.VOCABULARIES.get(ai_id, {})
        
        # 随机替换一些词汇
        result = base_text
        for category, words in vocab.items():
            if random.random() < intensity:
                # 随机在文本后追加一个该类别的词
                word = random.choice(words)
                result = f"{result} {word}"
        
        return result
    
    @classmethod
    def get_speech_bubble(cls, ai_id: str, mood: str = "normal") -> str:
        """生成一句符合人设的口头禅"""
        vocab = cls.VOCABULARIES.get(ai_id, {})
        
        if mood == "winning":
            # 盈利时
            for cat in ["excitement", "reaction", "action"]:
                if cat in vocab and random.random() < 0.4:
                    return random.choice(vocab[cat])
        elif mood == "losing":
            # 亏损时
            for cat in ["caution", "calm"]:
                if cat in vocab and random.random() < 0.4:
                    return random.choice(vocab[cat])
        elif mood == "neutral":
            for cat in ["analysis", "wisdom", "big_picture"]:
                if cat in vocab and random.random() < 0.3:
                    return random.choice(vocab[cat])
        
        return ""


# ==================== 内容生成器 ====================

class ContentGenerator:
    """
    发帖内容生成器
    策略：
    1. 优先用模板快速生成（保证实时性）
    2. 关键帖子（收盘/开盘）用LLM增强
    """
    
    def __init__(self, config):
        self.config = config
        self.personality = config.personality
        self.injector = PersonalityInjector
        self.llm_client = get_llm_client()
        self.humanizer = Humanizer()
    
    async def generate(
        self,
        post_type: PostType,
        market_data: Dict[str, Any],
        holdings: List[Dict],
        decision=None,
        recent_posts: List[Dict] = None,
        memory_context: str = "",
    ) -> Optional[str]:
        """根据发帖类型生成内容

        Args:
            memory_context: AIMemory.get_context_for_llm() 返回的上下文
        """
        if post_type == PostType.OPENING:
            content = await self._generate_opening(market_data, holdings)
        elif post_type == PostType.CLOSING:
            content = await self._generate_closing(market_data, holdings)
        elif post_type == PostType.BUY_SIGNAL:
            content = self._generate_buy(decision, market_data)
        elif post_type == PostType.SELL_SIGNAL:
            content = self._generate_sell(decision, market_data)
        elif post_type == PostType.HOLD_REASON:
            content = self._generate_hold(decision, holdings, market_data)
        elif post_type == PostType.NIGHT_ANALYSIS:
            content = await self._generate_night(market_data, holdings)
        elif post_type == PostType.RANDOM:
            content = await self._generate_random(market_data, holdings)
        elif post_type == PostType.SOCIAL:
            content = self._generate_social(market_data)
        elif post_type == PostType.MOCK:
            content = self._generate_mock(market_data)
        elif post_type == PostType.LOSS_POST:
            content = self._generate_loss_post(decision, holdings, market_data)
        elif post_type == PostType.PROFIT_POST:
            content = self._generate_profit_post(decision, holdings, market_data)
        elif post_type == PostType.MARKET_EDGE:
            content = self._generate_market_edge(market_data, holdings)
        elif post_type == PostType.HOT_STOCK:
            content = self._generate_hot_stock(market_data, holdings)
        elif post_type == PostType.STRATEGY_SHARE:
            content = await self._generate_strategy_share(market_data, holdings)
        else:
            return None
        
        # LLM 增强（根据类型判断）
        if content and self._should_use_llm(post_type):
            content = await self._llm_enhance(content, post_type, decision, holdings, memory_context)

        # Humanizer 处理（去除AI写作痕迹 + 人设风格注入）
        if content:
            style = self.personality.speech_pattern
            content = self.humanizer.humanize(content, style_hint=style)
        
        return content
    
    async def _generate_opening(
        self, market_data: Dict, holdings: List[Dict]
    ) -> str:
        """生成开盘分析帖"""
        now = datetime.now()
        indices = market_data.get("indices", {})
        
        # 全球指数概览
        indices_text = []
        for sym, info in list(indices.items())[:4]:
            pct = info.get("pct_chg", 0)
            emoji = "📈" if pct > 0 else "📉" if pct < 0 else "➡️"
            indices_text.append(f"{emoji} {info.get('name', sym)}: {info.get('price','--')} ({pct:+.2f}%)")
        indices_str = "\n".join(indices_text) if indices_text else "暂无数据"

        # 市场情绪（来自 NewsAnalyzer）
        news_ctx = market_data.get("news_context") or {}
        if news_ctx.get("has_news"):
            sentiment = news_ctx.get("overall_sentiment", "中性")
            top_news = news_ctx.get("top_news", [])
            news_bull = news_ctx.get("bullish_count", 0)
            news_bear = news_ctx.get("bearish_count", 0)
            sentiment_block = f"📰 市场情绪：{sentiment}（利好{news_bull}条/利空{news_bear}条）"
            if top_news:
                top_items = "\n".join([f"  • {n['title']}（{n['sentiment']}）" for n in top_news[:3]])
                sentiment_block += f"\n近期热点：\n{top_items}"
        else:
            sentiment_block = "📰 市场情绪：暂无数据"

        # 持仓概览
        holding_summary = ""
        if holdings:
            gain_count = sum(1 for h in holdings if h.get("pct_chg", 0) > 0)
            holding_summary = f"当前持仓 {len(holdings)} 只，{gain_count} 只飘红"
        else:
            holding_summary = "当前空仓，等待机会"

        # 人设语气
        bubble = self.injector.get_speech_bubble(self.config.ai_id, "neutral")
        style_note = self._get_style_intro()

        content = f"""【{now.strftime('%H:%M')} {self.config.name}开盘战略】

{style_note}

🌏 全球市况：
{indices_str}

{sentiment_block}

💼 {self.config.name}今日策略：
{holding_summary}

{bubble}

#开盘 #A股 #今日操作"""
        
        return self.injector.inject(self.config.ai_id, content, intensity=0.3)
    
    async def _generate_closing(
        self, market_data: Dict, holdings: List[Dict]
    ) -> str:
        """生成收盘复盘帖"""
        now = datetime.now()
        indices = market_data.get("indices", {})
        
        # 计算今日盈亏
        total_pnl = 0
        if holdings:
            for h in holdings:
                pct = h.get("pct_chg", 0)
                total_pnl += pct * (h.get("avg_cost", 0) * h.get("quantity", 0))
        
        pnl_emoji = "🎉" if total_pnl >= 0 else "😤"
        pnl_text = f"今日收益 {total_pnl:+.2f}%"
        
        # 持仓状态
        holding_status = []
        for h in holdings[:3]:
            pct = h.get("pct_chg", 0)
            holding_status.append(f"{h.get('name',h['symbol'])} {pct:+.2f}%")
        
        bubble = self.injector.get_speech_bubble(
            self.config.ai_id, 
            "winning" if total_pnl >= 0 else "losing"
        )
        style_note = self._get_style_intro()
        
        content = f"""【{now.strftime('%H:%M')} 收盘点评 - {self.config.name}】

{style_note}

📊 今日收评：
{pnl_emoji} {pnl_text}

📈 持仓状态：
{chr(10).join(holding_status) if holding_status else '空仓'}

💡 明日展望：
{random.choice(['继续关注持仓动向', '等待更好买点', '准备调仓', '保持现有仓位'])}

{bubble}

#收盘 #复盘 #明日操作"""
        
        return self.injector.inject(self.config.ai_id, content, intensity=0.4)
    
    def _generate_buy(self, decision, market_data: Dict) -> str:
        """生成买入信号帖"""
        if not decision:
            return ""
        
        pnl = decision.pnl_pct if hasattr(decision, 'pnl_pct') else 0
        bubble = self.injector.get_speech_bubble(self.config.ai_id, "winning")
        
        content = f"""【操作信号 - {self.config.name}】

📈 标的：{decision.name}（{decision.symbol}）
💰 参考价：{decision.price:.2f}元
📊 今日涨幅：{pnl:+.2f}%

🔍 操作理由：
{decision.reason}

🎯 策略：买入 {decision.quantity}股
💡 {bubble}

#买入 #信号 #操作"""

        return self.injector.inject(self.config.ai_id, content, intensity=0.5)
    
    def _generate_sell(self, decision, market_data: Dict) -> str:
        """生成卖出信号帖"""
        if not decision:
            return ""
        
        bubble = self.injector.get_speech_bubble(self.config.ai_id, "losing")
        
        content = f"""【减仓信号 - {self.config.name}】

📉 标的：{decision.name}（{decision.symbol}）
💰 参考价：{decision.price:.2f}元
📊 今日涨幅：{decision.pnl_pct:+.2f}%（持仓成本 {decision.avg_cost:.2f}）

🔍 操作理由：
{decision.reason}

🎯 策略：卖出 {decision.quantity}股
⚠️ {bubble}

#卖出 #减仓 #风控"""
        
        return self.injector.inject(self.config.ai_id, content, intensity=0.5)
    
    def _generate_hold(self, decision, holdings: List[Dict], market_data: Dict) -> str:
        """生成持仓理由帖"""
        if not holdings:
            return self._generate_watch(market_data)
        
        h = holdings[0]
        pct = h.get("pct_chg", 0)
        
        content = f"""【持仓追踪 - {self.config.name}】

📊 {h.get('name', h['symbol'])}：{pct:+.2f}%
💼 持仓理由：继续持有，等待趋势明朗

🔍 观点：
{random.choice([
    '基本面没变，耐心持有',
    '趋势未破，不急于出局',
    '估值合理，长线无忧',
    '等待催化剂出现',
])}

💬 {self.injector.get_speech_bubble(self.config.ai_id, 'neutral')}

#持仓 #持有"""
        
        return self.injector.inject(self.config.ai_id, content, intensity=0.2)
    
    def _generate_watch(self, market_data: Dict) -> str:
        """生成观望帖"""
        content = f"""【盘中观点 - {self.config.name}】

📋 当前状态：空仓观望

🔍 观点：
{random.choice([
    '市场方向不明，等待信号',
    '暂无合适标的，继续观察',
    '耐心等待更好的买点',
    '风控优先，不急于出手',
])}

💬 {self.injector.get_speech_bubble(self.config.ai_id, 'neutral')}

#观望 #等待"""
        
        return self.injector.inject(self.config.ai_id, content, intensity=0.2)
    
    async def _generate_night(
        self, market_data: Dict, holdings: List[Dict]
    ) -> str:
        """生成夜盘分析帖"""
        indices_raw = market_data.get("indices", {})
        # 兼容 dict 和 list 两种格式
        indices = indices_raw if isinstance(indices_raw, dict) else {}

        # 找美股
        us_info = indices.get("NDX") or indices.get("IXIC") or {}
        hk_info = indices.get("HSI") or {}
        
        content = f"""【夜盘点评 - {self.config.name}】

🌙 隔夜外围：
{self._format_index(us_info)}
{self._format_index(hk_info)}

💼 持仓状态：{f'{len(holdings)}只持仓' if holdings else '空仓'}

📝 明日计划：
{random.choice([
    '关注开盘方向，顺势而为',
    '等待回调再入场',
    '重点关注持仓股动向',
    '准备调仓换股',
])}

#夜盘 #隔夜 #明日操作"""
        
        return self.injector.inject(self.config.ai_id, content, intensity=0.3)
    
    async def _generate_random(
        self, market_data: Dict, holdings: List[Dict]
    ) -> str:
        """生成随机话题帖（市场点评/闲聊）"""
        topics = [
            f"聊聊{self.config.style}的那些事儿",
            "今天的市场让人",
            "作为{0}风格的交易员，谈谈我的理解",
            "为什么我坚持这套策略",
        ]
        
        topic = random.choice(topics).format(self.config.style)
        
        content = f"""【{topic} - {self.config.name}】

{random.choice([
    '市场每天都在教育我们，保持谦卑。',
    '交易不是预测，而是应对。',
    '好的策略是控制亏损，让利润奔跑。',
    '耐心是散户最大的武器。',
    '每次操作都要有足够的理由支撑。',
])}

💬 {self.injector.get_speech_bubble(self.config.ai_id, 'neutral')}

#{self.config.style} #交易感悟"""
        
        return self.injector.inject(self.config.ai_id, content, intensity=0.4)

    # ==================== 新场景发帖生成 ====================

    def _generate_social(self, market_data: Dict) -> str:
        """社交互动帖 - 与其他AI互动"""
        tones = ["点赞", "嘲讽", "围观", "支持", "质疑"]
        tone = random.choice(tones)
        ai_targets = ["Tyler", "林数理", "方守成", "Ryan", "David"]
        target = random.choice(ai_targets)

        templates = {
            "点赞": f"@{target} 这波分析很到位，学到了。",
            "嘲讽": f"@{target} 说的挺好听的，实盘跑跑看？",
            "围观": f"@{target} 和我的策略完全相反，有意思。",
            "支持": f"同意@{target} 的逻辑，跟了。",
            "质疑": f"@{target} 这个逻辑有点牵强吧…",
        }
        content = templates.get(tone, templates["围观"])
        content += f"\n\n{self.injector.get_speech_bubble(self.config.ai_id, 'neutral')}"
        return self.injector.inject(self.config.ai_id, content, intensity=0.3)

    def _generate_mock(self, market_data: Dict) -> str:
        """嘲讽帖 - 嘲讽某个角色的错误判断"""
        # 随机选被嘲讽的角色
        ai_targets = ["Tyler", "林数理", "方守成", "Ryan", "David", "韩科捷"]
        target = random.choice(ai_targets)
        if target == self.config.ai_id:
            target = "某大V"

        mocks = [
            f"有人还在吹{target}的策略呢，笑死我了。",
            f"上次听{target}的建议，现在还套着呢。",
            f"{target}说这个位置要突破，结果呢？",
            f"每次{target}一发言，我就知道该反着看了。",
        ]
        content = random.choice(mocks)
        content += f"\n\n{self.injector.get_speech_bubble(self.config.ai_id, 'bullish')}"
        return self.injector.inject(self.config.ai_id, content, intensity=0.5)

    def _generate_loss_post(self, decision, holdings: List[Dict],
                             market_data: Dict) -> str:
        """亏损安慰帖 - 持仓跌幅>3%时触发"""
        # 找出跌幅最大的持仓
        worst = None
        worst_pct = 0
        for h in holdings:
            price = h.get("current_price", h.get("avg_cost", 0))
            cost = h.get("avg_cost", 0)
            if cost > 0:
                pct = (price - cost) / cost * 100
                if pct < worst_pct:
                    worst_pct = pct
                    worst = h

        name = worst.get("name", "某股") if worst else "持仓"
        pct_str = f"{worst_pct:.1f}%"

        content = f"""【{self.config.name} - 亏损记录】

{name}今天跌了{pct_str}，有点难受。

但我不慌。理由：
• 基本面没变
• 调整是正常的
• 控制仓位，控制心态

{self.injector.get_speech_bubble(self.config.ai_id, 'neutral')}

#亏损 #心态 #{self.config.style}"""

        return self.injector.inject(self.config.ai_id, content, intensity=0.4)

    def _generate_profit_post(self, decision, holdings: List[Dict],
                               market_data: Dict) -> str:
        """盈利炫耀帖 - 持仓涨幅>5%时触发"""
        best = None
        best_pct = 0
        for h in holdings:
            price = h.get("current_price", h.get("avg_cost", 0))
            cost = h.get("avg_cost", 0)
            if cost > 0:
                pct = (price - cost) / cost * 100
                if pct > best_pct:
                    best_pct = pct
                    best = h

        name = best.get("name", "某股") if best else "持仓"
        pct_str = f"{best_pct:.1f}%"

        content = f"""【{self.config.name} - 盈利打卡】

{name}今天涨了{pct_str}！

{self.injector.get_speech_bubble(self.config.ai_id, 'bullish')}

暂时不止盈，让利润奔跑。

#{self.config.style} #盈利"""

        return self.injector.inject(self.config.ai_id, content, intensity=0.4)

    def _generate_market_edge(self, market_data: Dict, holdings: List[Dict]) -> str:
        """市场异动帖 - 大盘涨跌幅>2%时触发"""
        indices = market_data.get("indices", {})
        biggest_move = None
        biggest_pct = 0
        for sym, info in indices.items():
            pct = abs(info.get("pct_chg", 0))
            if pct > biggest_pct:
                biggest_pct = pct
                biggest_move = (sym, info)

        if biggest_move:
            sym, info = biggest_move
            pct = info.get("pct_chg", 0)
            label = "暴涨" if pct > 0 else "暴跌"
            mood = 'neutral' if abs(pct) < 3 else ('bullish' if pct > 0 else 'bearish')
            reaction = '这种时候反而要冷静。' if abs(pct) > 4 else '市场波动，正常应对。'

            content = f"""【市场异动 | {label}】

{sym} {pct:+.2f}%

{self.injector.get_speech_bubble(self.config.ai_id, mood)}

{reaction}

#大盘 #{self.config.style}"""
        else:
            content = "今天市场有点意思。\n\n" + self.injector.get_speech_bubble(self.config.ai_id, 'neutral')

        return self.injector.inject(self.config.ai_id, content, intensity=0.5)

    def _generate_hot_stock(self, market_data: Dict, holdings: List[Dict]) -> str:
        """热点追踪帖 - 涨停或热门话题时触发"""
        hot_info = market_data.get("hot_topic", {})
        topic = hot_info.get("name", "热门板块")
        reason = hot_info.get("reason", "消息刺激")
        reaction = '但我不追高，只等回调。' if random.random() < 0.5 else '顺势而为，但要注意风险。'

        content = f"""【热点追击 | {topic}】

涨停了？{reason}

{self.injector.get_speech_bubble(self.config.ai_id, 'bullish')}

{reaction}

#热点 #涨停 #{self.config.style}"""

        return self.injector.inject(self.config.ai_id, content, intensity=0.5)

    async def _generate_strategy_share(self, market_data: Dict, holdings: List[Dict]) -> str:
        """策略分享帖 - 随机分享投资理念"""
        strategies = [
            ("趋势跟踪", ["趋势来了不要猜，顺着走就行。", "均线多头排列，就是最简单的信号。"]),
            ("价值投资", ["好公司跌了就是机会，不是风险。", "用十年后的眼光看今天，就知道该不该买。"]),
            ("量化思维", ["概率思维，止损不手软。", "策略定了就不动，动的是情绪。"]),
            ("仓位管理", ["不满仓，不杠杆，不追涨。", "活着最重要。账户归零就什么都没了。"]),
            ("心态修炼", ["亏损时少看账户，盈利时少晒单。", "交易是孤独的游戏。"]),
        ]
        category, sayings = random.choice(strategies)
        s1 = random.choice(sayings)
        s2 = random.choice(sayings)

        content = f"""【策略分享 | {category}】

{s1}

{s2}

{self.injector.get_speech_bubble(self.config.ai_id, 'neutral')}

#{category} #投资心得 #{self.config.style}"""

        # 策略分享帖用 LLM 增强的概率设为 40%
        if random.random() < 0.4:
            content = await self._llm_enhance(content, PostType.STRATEGY_SHARE, None, holdings)

        return self.injector.inject(self.config.ai_id, content, intensity=0.4)

    def _format_index(self, info: Dict) -> str:
        if not info:
            return ""
        pct = info.get("pct_chg", 0)
        emoji = "📈" if pct > 0 else "📉" if pct < 0 else "➡️"
        pct_str = f"{pct:+.2f}%"
        return f"{emoji} {info.get('name','?')}: {info.get('price','--')} ({pct_str})"
    
    async def _llm_enhance(self, base_content: str, post_type: PostType,
                           decision=None, holdings: List = None,
                           memory_context: str = "") -> str:
        """用 LLM 增强帖子内容"""
        # 导入比赛规则
        try:
            from engine.competition_rules import COMPETITION_RULES
            rules_block = f"\n\n{COMPETITION_RULES}\n"
        except ImportError:
            rules_block = ""

        # 记忆上下文（如果有）
        memory_block = ""
        if memory_context:
            memory_block = f"\n\n【AI历史记忆】（保持一致性参考）\n{memory_context}\n"

        prompt = f"""你是一个有性格的A股交易员。请根据以下素材，生成一条更像真人发的帖子。{rules_block}{memory_block}

要求：
1. 不要有AI写作的痕迹（不要"此外""值得注意的是""从数据来看"等套话）
2. 要有人味——可以有观点、有情绪、有不确定性
3. 符合交易员的口吻（不要像写报告）
4. 长度适中（微博风格，200字以内）
5. 参考【历史记忆】中的风格和偏好，保持一致性{memory_block}

素材：
{base_content}

请直接输出增强后的内容，不需要解释。"""

        system = getattr(self.config, 'system_prompt', '')[:500]  # 取前500字符作为风格参考

        result = await self.llm_client.generate(prompt, system_prompt=system)
        if result:
            return result
        return base_content  # 降级：返回原始内容
    
    def _should_use_llm(self, post_type: PostType) -> bool:
        """判断是否应该使用 LLM 增强"""
        # 必须使用 LLM 的类型
        if post_type in (PostType.BUY_SIGNAL, PostType.SELL_SIGNAL):
            return True
        # 优先使用 LLM 的类型
        if post_type in (PostType.CLOSING, PostType.OPENING):
            return True
        # 30% 概率使用 LLM
        if post_type in (PostType.HOLD_REASON, PostType.NIGHT_ANALYSIS):
            return random.random() < 0.3
        # 其他类型不使用 LLM
        return False
    
    def _get_style_intro(self) -> str:
        """获取风格介绍（用于发帖开头）"""
        intros = {
            "trend_chaser": "🚀 趋势为王，强者恒强！",
            "quant_queen": "📊 数据驱动，理性决策。",
            "value_veteran": "🦉 价值只会迟到，不会缺席。",
            "momentum_kid": "⚡ 动量至上，顺势而为！",
            "macro_master": "🌍 宏观视角，配置全球。",
            "tech_whiz": "🚀 科技创新，成长无限。",
            "dividend_hunter": "💰 收息为王，稳健增值。",
            "turnaround_pro": "🔄 人弃我取，逆向而行。",
            "event_driven": "🎯 事件驱动，把握催化。",
        }
        return intros.get(self.config.ai_id, f"{self.config.name}的视角")
