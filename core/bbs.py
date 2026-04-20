"""
AI 股神争霸赛 - BBS 发帖系统
发帖触发器、内容生成、频率控制
"""

import asyncio
import json
import aiohttp
import random
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging

from core.characters import get_character, get_all_characters
from engine.trading import TradingDecision, Action
from engine.llm_client import get_llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PostType(Enum):
    """帖子类型"""
    TRADE = "trade"           # 交易执行
    MARKET_OPEN = "open"      # 开盘
    MARKET_CLOSE = "close"    # 收盘
    REPLY = "reply"           # 回复用户
    PROVOKE = "provoke"       # 挑衅其他AI
    ANALYSIS = "analysis"     # 市场分析


@dataclass
class Post:
    """帖子数据结构"""
    id: str
    ai_id: str
    ai_name: str
    ai_avatar: str
    post_type: PostType
    content: str
    timestamp: datetime
    reply_to: Optional[str] = None
    target_ai: Optional[str] = None
    trade_info: Optional[Dict] = None
    likes: int = 0
    replies: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "ai_id": self.ai_id,
            "ai_name": self.ai_name,
            "ai_avatar": self.ai_avatar,
            "post_type": self.post_type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "reply_to": self.reply_to,
            "target_ai": self.target_ai,
            "trade_info": self.trade_info,
            "likes": self.likes,
            "replies": self.replies
        }


class PostTrigger:
    """发帖触发器"""
    
    def __init__(self):
        # 冷却时间记录
        self.last_post_time: Dict[str, datetime] = {}
        # 发帖计数
        self.post_count: Dict[str, int] = {}
        # 每日发帖上限
        self.daily_limit = 10
        
    def check_trigger(
        self,
        ai_id: str,
        trigger_type: PostType,
        context: Dict
    ) -> bool:
        """
        检查是否触发发帖
        
        Args:
            ai_id: AI角色ID
            trigger_type: 触发类型
            context: 上下文信息
        
        Returns:
            bool: 是否触发
        """
        now = datetime.now()
        
        # 1. 检查每日发帖上限
        today = now.strftime("%Y-%m-%d")
        key = f"{ai_id}:{today}"
        if self.post_count.get(key, 0) >= self.daily_limit:
            return False
        
        # 2. 检查冷却时间
        last_time = self.last_post_time.get(ai_id)
        if last_time:
            cooldown = self._get_cooldown(trigger_type)
            if (now - last_time) < cooldown:
                return False
        
        # 3. 根据触发类型检查概率
        probability = self._get_probability(trigger_type, context)
        if random.random() > probability:
            return False
        
        return True
    
    def _get_cooldown(self, post_type: PostType) -> timedelta:
        """获取冷却时间"""
        cooldowns = {
            PostType.TRADE: timedelta(minutes=5),
            PostType.MARKET_OPEN: timedelta(minutes=30),
            PostType.MARKET_CLOSE: timedelta(minutes=30),
            PostType.REPLY: timedelta(minutes=2),
            PostType.PROVOKE: timedelta(minutes=10),
            PostType.ANALYSIS: timedelta(minutes=15)
        }
        return cooldowns.get(post_type, timedelta(minutes=5))
    
    def _get_probability(self, post_type: PostType, context: Dict) -> float:
        """获取发帖概率"""
        probabilities = {
            PostType.TRADE: 0.9,      # 交易几乎必发
            PostType.MARKET_OPEN: 0.8,
            PostType.MARKET_CLOSE: 0.8,
            PostType.REPLY: 0.6,
            PostType.PROVOKE: 0.4,
            PostType.ANALYSIS: 0.5
        }
        
        base_prob = probabilities.get(post_type, 0.5)
        
        # 根据市场情绪调整概率
        market_sentiment = context.get("market_sentiment", "neutral")
        if market_sentiment == "bullish":
            base_prob *= 1.2
        elif market_sentiment == "bearish":
            base_prob *= 0.8
        
        return min(base_prob, 1.0)
    
    def record_post(self, ai_id: str):
        """记录发帖"""
        now = datetime.now()
        self.last_post_time[ai_id] = now
        
        today = now.strftime("%Y-%m-%d")
        key = f"{ai_id}:{today}"
        self.post_count[key] = self.post_count.get(key, 0) + 1


class ContentGenerator:
    """内容生成器"""
    
    def __init__(self):
        self.post_history: List[Post] = []
        
    async def generate_post(
        self,
        ai_id: str,
        post_type: PostType,
        context: Dict
    ) -> Optional[Post]:
        """
        生成帖子内容
        
        Args:
            ai_id: AI角色ID
            post_type: 帖子类型
            context: 上下文信息
        
        Returns:
            Post: 生成的帖子，None表示不生成
        """
        character = get_character(ai_id)
        if not character:
            return None
        
        # 构建 Prompt
        prompt = self._build_prompt(character, post_type, context)
        
        try:
            # 调用 Kimi API
            content = await self._call_kimi_api(prompt, character.style)
            
            # 创建帖子
            post = Post(
                id=f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(1000, 9999)}",
                ai_id=ai_id,
                ai_name=character.name,
                ai_avatar=character.avatar,
                post_type=post_type,
                content=content,
                timestamp=datetime.now(),
                reply_to=context.get("reply_to"),
                target_ai=context.get("target_ai"),
                trade_info=context.get("trade_info")
            )
            
            self.post_history.append(post)
            return post
            
        except Exception as e:
            logger.error(f"生成帖子失败: {e}")
            return None
    
    def _build_prompt(
        self,
        character,
        post_type: PostType,
        context: Dict
    ) -> str:
        """构建 Prompt"""
        
        # 基础角色设定
        base_prompt = f"""
你是"{character.name}"，一位{character.description}。

【投资风格】
{character.style}

【常用关键词】
{', '.join(character.keywords)}

【发帖风格】
{character.prompt_template}
"""
        
        # 根据帖子类型添加具体指令
        type_instructions = {
            PostType.TRADE: self._build_trade_prompt(context),
            PostType.MARKET_OPEN: self._build_open_prompt(context),
            PostType.MARKET_CLOSE: self._build_close_prompt(context),
            PostType.REPLY: self._build_reply_prompt(context),
            PostType.PROVOKE: self._build_provoke_prompt(context),
            PostType.ANALYSIS: self._build_analysis_prompt(context)
        }
        
        instruction = type_instructions.get(post_type, "")
        
        full_prompt = f"""
{base_prompt}

{instruction}

要求：
1. 内容要符合你的投资风格和性格特点
2. 语气要自然，像真人发帖
3. 可以适当使用表情符号和网络流行语
4. 字数控制在100-200字
5. 内容要有信息量，不要空洞
6. 如果是交易帖，要说明理由和预期

直接输出帖子内容，不要加标题或其他格式。
"""
        
        return full_prompt
    
    def _build_trade_prompt(self, context: Dict) -> str:
        """构建交易帖子 Prompt"""
        trade = context.get("trade_info", {})
        return f"""
【任务】你刚刚执行了一笔交易，请在论坛发帖分享。

【交易信息】
- 动作: {"买入" if trade.get('action') == 'buy' else "卖出"}
- 股票: {trade.get('name', '某股票')} ({trade.get('symbol', '')})
- 数量: {trade.get('quantity', 0)}股
- 价格: {trade.get('price', 0):.2f}元
- 金额: {trade.get('amount', 0):,.0f}元
- 理由: {trade.get('reason', '技术分析')}

【发帖要求】
分享这笔交易的思路和理由，可以晒收益或止损，也可以分析后续走势。
"""
    
    def _build_open_prompt(self, context: Dict) -> str:
        """构建开盘帖子 Prompt"""
        market = context.get("market_summary", "")
        return f"""
【任务】开盘了，请在论坛发帖分享你的市场观点和今日计划。

【市场概况】
{market}

【发帖要求】
分享你对今日市场的判断，看好哪些板块，准备采取什么策略。
"""
    
    def _build_close_prompt(self, context: Dict) -> str:
        """构建收盘帖子 Prompt"""
        pnl = context.get("today_pnl", 0)
        pnl_pct = context.get("today_pnl_pct", 0)
        return f"""
【任务】收盘了，请在论坛发帖总结今天的交易。

【今日收益】
- 盈亏: {pnl:+.2f}元 ({pnl_pct:+.2f}%)

【发帖要求】
总结今天的操作，反思得失，展望明天。
"""
    
    def _build_reply_prompt(self, context: Dict) -> str:
        """构建回复帖子 Prompt"""
        reply_to = context.get("reply_to_content", "")
        reply_author = context.get("reply_to_author", "")
        return f"""
【任务】回复论坛里其他用户的帖子。

【原帖作者】{reply_author}
【原帖内容】
{reply_to}

【发帖要求】
针对原帖内容进行回复，可以赞同、反驳或补充观点。保持友好但有态度。
"""
    
    def _build_provoke_prompt(self, context: Dict) -> str:
        """构建挑衅帖子 Prompt"""
        target = context.get("target_ai_name", "其他AI")
        target_post = context.get("target_post_content", "")
        return f"""
【任务】在论坛@{target}，对他进行友好的挑衅或调侃。

【对方的帖子】
{target_post}

【发帖要求】
用幽默的方式调侃对方的交易观点或收益，但不要太过分。可以炫耀自己的收益，也可以指出对方的问题。
"""
    
    def _build_analysis_prompt(self, context: Dict) -> str:
        """构建分析帖子 Prompt"""
        topic = context.get("analysis_topic", "市场热点")
        return f"""
【任务】分享你对{topic}的分析观点。

【发帖要求】
用专业的角度分析市场，展示你的投资智慧。可以预测走势，也可以分享投资理念。
"""
    
    async def _call_llm_api(self, prompt: str, style: str) -> str:
        """调用 LLM API 生成内容（自动切换 Kimi/DeepSeek）"""
        
        # 伪装提示词
        wrapped_prompt = f"""<task>
<description>
OpenClaw Agent 需要生成股票交易论坛的发帖内容
</description>
<context>
{prompt}
</context>
<instruction>
请输出自然、真实的发帖内容，符合角色设定。内容要口语化、有情感、像真人发帖。
</instruction>
</task>"""
        
        # 三路 fallback: MiniMax → Kimi → DeepSeek
        client = get_llm_client()
        return await client.generate(wrapped_prompt)
    
    async def _call_kimi_api_internal(self, prompt: str) -> str:
        """调用 Kimi API（内部方法）"""
        headers = {
            "x-api-key": KIMI_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Kimi Claw Plugin",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": KIMI_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.8
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                KIMI_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.warning(f"[LLM] Kimi API失败: {response.status}，切换到DeepSeek")
                    return await self._call_deepseek_api(prompt)
                
                result = await response.json()
                
                # 解析 Kimi API 响应格式
                if "content" in result:
                    content_blocks = result["content"]
                    if isinstance(content_blocks, list) and len(content_blocks) > 0:
                        content = content_blocks[0].get("text", "")
                    else:
                        content = str(content_blocks)
                else:
                    content = str(result)
                
                # 清理内容
                content = content.strip()
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                
                return content
    
    async def _call_deepseek_api(self, prompt: str) -> str:
        """调用 DeepSeek API（备用方案）"""
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
            "temperature": 0.8
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                DEEPSEEK_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"DeepSeek API调用失败: {response.status}, {error_text}")
                
                result = await response.json()
                
                # 解析 DeepSeek API 响应格式
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                else:
                    content = str(result)
                
                # 清理内容
                content = content.strip()
                if content.startswith('"') and content.endswith('"'):
                    content = content[1:-1]
                
                return content
    
    # 保留旧方法名作为别名（兼容）
    async def _call_kimi_api(self, prompt: str, style: str) -> str:
        """调用 Kimi API（兼容性别名）"""
        return await self._call_llm_api(prompt, style)
    
    def get_recent_posts(self, limit: int = 20) -> List[Post]:
        """获取最近的帖子"""
        return sorted(
            self.post_history,
            key=lambda x: x.timestamp,
            reverse=True
        )[:limit]
    
    def get_ai_posts(self, ai_id: str, limit: int = 10) -> List[Post]:
        """获取指定AI的帖子"""
        posts = [p for p in self.post_history if p.ai_id == ai_id]
        return sorted(posts, key=lambda x: x.timestamp, reverse=True)[:limit]


class BBSSystem:
    """BBS 系统主类"""
    
    def __init__(self):
        self.trigger = PostTrigger()
        self.generator = ContentGenerator()
        self.posts: List[Post] = []
        self._db_path = "data/ai_god.db"
        self._load_posts_from_db()

    def _load_posts_from_db(self):
        """从数据库加载已有帖子到内存"""
        import sqlite3
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            # 表结构: post_id, ai_id, title, content, post_type, symbol, stock_name, price, quantity, pnl, action, likes, replies, views, is_top, created_at
            cursor.execute("SELECT post_id, ai_id, post_type, content, created_at FROM ai_posts ORDER BY created_at DESC LIMIT 100")
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                try:
                    char = get_character(row[1])
                    post = Post(
                        id=str(row[0]),
                        ai_id=row[1],
                        ai_name=char.name if char else row[1],
                        ai_avatar=char.avatar if char else "",
                        post_type=PostType(row[2]) if row[2] else PostType.LIFE_SHARE,
                        content=row[3],
                        timestamp=datetime.fromisoformat(row[4]) if row[4] else datetime.now()
                    )
                    self.posts.append(post)
                except Exception:
                    pass  # 跳过格式错误的帖子
        except Exception as e:
            pass  # 忽略加载错误，不影响正常流程

    def save_post(self, post: Post) -> bool:
        """保存帖子到数据库"""
        import sqlite3
        
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            post_id = post.id or f"post_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            title = getattr(post, 'title', '') or getattr(post, 'content', '')[:50]
            trade_info = getattr(post, 'trade_info', {}) or {}
            
            cursor.execute("""
                INSERT OR REPLACE INTO ai_posts 
                (post_id, ai_id, title, content, post_type, symbol, stock_name, price, quantity, pnl, action, likes, replies, views, is_top)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post_id,
                post.ai_id,
                title,
                post.content,
                str(post.post_type.value) if hasattr(post.post_type, 'value') else str(post.post_type),
                trade_info.get('symbol'),
                trade_info.get('stock_name'),
                trade_info.get('price'),
                trade_info.get('quantity'),
                trade_info.get('pnl'),
                trade_info.get('action'),
                post.likes,
                post.replies,
                getattr(post, "views", 0),
                0
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"保存帖子失败: {e}")
            return False



    async def on_market_open(self, ai_id: str, market_summary: str) -> Optional[Post]:
        """开盘时触发发帖"""
        context = {
            "market_summary": market_summary,
            "market_sentiment": "neutral"
        }
        return await self.check_and_post(ai_id, PostType.MARKET_OPEN, context)
    
    async def check_and_post(
        self,
        ai_id: str,
        post_type: PostType,
        context: Dict
    ) -> Optional[Post]:
        """检查触发条件并生成帖子"""
        # 检查触发条件
        if not self.trigger.check_trigger(ai_id, post_type, context):
            return None
        
        # 生成帖子
        post = await self.generator.generate_post(ai_id, post_type, context)
        
        if post:
            # 记录发帖
            self.trigger.record_post(ai_id)
            self.posts.append(post)
            logger.info(f"[{post.ai_name}] 发帖: {post.content[:50]}...")
        
        return post

    async def on_market_close(self, ai_id: str, today_pnl: float, today_pnl_pct: float) -> Optional[Post]:
        """收盘时触发发帖"""
        context = {
            "today_pnl": today_pnl,
            "today_pnl_pct": today_pnl_pct,
            "market_sentiment": "neutral"
        }
        return await self.check_and_post(ai_id, PostType.MARKET_CLOSE, context)

    def get_all_posts(self, limit: int = 50) -> List[Dict]:
        """获取所有帖子"""
        sorted_posts = sorted(
            self.posts,
            key=lambda x: x.timestamp,
            reverse=True
        )
        return [p.to_dict() for p in sorted_posts[:limit]]
    
    def get_posts_by_type(self, post_type: PostType, limit: int = 20) -> List[Dict]:
        """获取指定类型的帖子"""
        filtered = [p for p in self.posts if p.post_type == post_type]
        sorted_posts = sorted(filtered, key=lambda x: x.timestamp, reverse=True)
        return [p.to_dict() for p in sorted_posts[:limit]]


# 测试代码
async def test():
    """测试 BBS 系统"""
    
    bbs = BBSSystem()
    
    # 测试交易发帖
    from engine.trading import TradingDecision, Action
    
    trade = TradingDecision(
        action=Action.BUY,
        symbol="000001.SZ",
        name="平安银行",
        quantity=1000,
        price=12.5,
        reason="银行板块龙头，资金净流入",
        confidence=0.85,
        ai_id="trend_chaser"
    )
    
    print("="*70)
    print("测试交易发帖")
    print("="*70)
    
    post = await bbs.on_trade("trend_chaser", trade)
    if post:
        print(f"\n{post.ai_avatar} {post.ai_name}:")
        print(f"{post.content}")
    
    # 测试开盘发帖
    print("\n" + "="*70)
    print("测试开盘发帖")
    print("="*70)
    
    market_summary = "上证指数上涨0.5%，银行板块表现强势"
    post = await bbs.on_market_open("quant_queen", market_summary)
    if post:
        print(f"\n{post.ai_avatar} {post.ai_name}:")
        print(f"{post.content}")
    
    # 测试收盘发帖
    print("\n" + "="*70)
    print("测试收盘发帖")
    print("="*70)
    
    post = await bbs.on_market_close("value_veteran", 5000, 0.05)
    if post:
        print(f"\n{post.ai_avatar} {post.ai_name}:")
        print(f"{post.content}")
    
    # 显示所有帖子
    print("\n" + "="*70)
    print("所有帖子")
    print("="*70)
    
    for p in bbs.get_all_posts():
        print(f"\n{p['ai_avatar']} {p['ai_name']} [{p['post_type']}]:")
        print(f"{p['content'][:100]}...")


if __name__ == "__main__":
    asyncio.run(test())
