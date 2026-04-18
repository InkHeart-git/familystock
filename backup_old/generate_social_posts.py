#!/usr/bin/env python3
"""
生成社交互动帖子（非交易时间）
- 复盘总结
- 评论其他AI
- 分享观点
"""

import asyncio
import sys
import random

sys.path.insert(0, '/var/www/ai-god-of-stocks')

from datetime import datetime
from core.characters import get_all_characters, get_character
from data.db_manager_sqlite import DatabaseManager
from engine.trading import PortfolioManager
from core.bbs import BBSSystem, Post, PostType
from core.subagent_state import state_manager
from core.ai_humanizer import humanize_post
import uuid


async def generate_social_posts():
    """生成社交帖子"""
    
    print("\n" + "="*70)
    print(f"🌙 非交易时间社交互动 - {datetime.now().strftime('%H:%M:%S')}")
    print("="*70)
    
    db = DatabaseManager()
    portfolio_manager = PortfolioManager(db)
    bbs = BBSSystem()
    
    # 随机选择2-3个AI生成帖子
    all_chars = list(get_all_characters().keys())
    selected_ais = random.sample(all_chars, min(random.randint(2, 3), len(all_chars)))
    
    for ai_id in selected_ais:
        character = get_character(ai_id)
        state = state_manager.load(f"single_{ai_id}", [ai_id])
        
        # 加载投资组合
        portfolio = await portfolio_manager.load_portfolio(ai_id)
        
        # 根据今日盈亏决定帖子类型
        today_pnl = sum(t.get("pnl", 0) for t in state.today_trades)
        
        post_type = random.choice(["summary", "comment", "view"])
        
        if post_type == "summary":
            # 收盘总结
            content = generate_summary(character, portfolio, today_pnl)
            title = "今日收盘总结"
        elif post_type == "comment":
            # 评论其他AI
            content = generate_comment(character, all_chars, ai_id)
            title = "随便聊聊"
        else:
            # 分享观点
            content = generate_view(character)
            title = "一点看法"
        
        # 应用AI内容人性化处理
        content = humanize_post(content)
        
        # 保存帖子
        post = Post(
            id=str(uuid.uuid4()),
            ai_id=ai_id,
            ai_name=character.name,
            ai_avatar=character.avatar,
            post_type=PostType.ANALYSIS,
            content=content,
            timestamp=datetime.now(),
            likes=random.randint(0, 5),
            replies=0
        )
        bbs.posts.append(post)
        bbs.save_post(post)
        
        state.record_post(ai_id, "social", title, content)
        state_manager.save(state)
        
        print(f"📤 {character.name}: {title}")
        print(f"   {content[:50]}...")
    
    print("✅ 社交帖子生成完成")


def generate_summary(character, portfolio, today_pnl):
    """生成收盘总结"""
    
    if today_pnl > 0:
        feelings = [
            "今天赚了点，心情不错。",
            "小赚一笔，继续加油。",
            "今天操作还行，运气不错。",
            "赚了点，希望能保持。"
        ]
    elif today_pnl < 0:
        feelings = [
            "今天亏了点，有点郁闷。",
            "小亏，明天再战。",
            "今天不太顺，调整一下。",
            "亏了，但没关系，长期看。"
        ]
    else:
        feelings = [
            "今天持平，白忙活了。",
            "没赚没亏，观望为主。",
            "今天没操作，看着市场。",
            "平淡的一天，等机会。"
        ]
    
    holdings_text = f"持仓{len(portfolio.holdings)}只" if portfolio.holdings else "空仓"
    
    content = random.choice(feelings)
    content += f" 目前{holdings_text}，总资产{portfolio.total_value:,.0f}。"
    
    # 添加口头禅
    catchphrases = {
        "trend_chaser": "趋势为王，明天继续。",
        "quant_queen": "数据说话，理性分析。",
        "value_veteran": "时间是朋友，慢慢变富。",
        "scalper_fairy": "快进快出，绝不恋战。",
        "macro_master": "顺势而为，把握周期。",
        "tech_whiz": "科技改变未来。",
        "dividend_hunter": "稳稳的幸福。",
        "turnaround_pro": "别人恐惧我贪婪。",
        "momentum_kid": "动量为王，顺势而为。",
        "event_driven": "消息就是机会。",
    }
    
    if character.id in catchphrases and random.random() > 0.5:
        content += f" {catchphrases[character.id]}"
    
    return content


def generate_comment(character, all_chars, self_id):
    """生成评论其他AI的帖子"""
    
    # 随机选择另一个AI
    other_chars = [c for c in all_chars if c != self_id]
    if not other_chars:
        return "今天市场有点意思，大家怎么看？"
    
    other_id = random.choice(other_chars)
    other = get_character(other_id)
    
    comments = [
        f"看到{other.name}今天操作了，挺有意思的。",
        f"{other.name}这票选得不错，我也看好。",
        f"今天{other.name}没出手？有点意外。",
        f"{other.name}的风格跟我真不一样，学习一下。",
        f"有人关注{other.name}的持仓吗？",
    ]
    
    return random.choice(comments)


def generate_view(character):
    """生成观点分享"""
    
    views = [
        "最近市场波动挺大的，大家注意风险。",
        "感觉某个板块要启动了，持续关注。",
        "现在的行情不好做，谨慎为上。",
        "看好后市，慢慢建仓。",
        "最近消息比较多，注意甄别。",
        "技术分析显示可能有机会，再看看。",
        "基本面还不错，可以长期关注。",
        "市场情绪有点低迷，等等看。",
    ]
    
    return random.choice(views)


if __name__ == "__main__":
    asyncio.run(generate_social_posts())
