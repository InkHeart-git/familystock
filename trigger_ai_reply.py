#!/usr/bin/env python3
"""
触发AI回复脚本 - 被api_server.py异步调用
用法: python3 trigger_ai_reply.py <post_id> <mentions_json> <user_content>
"""
import sys
import json
import sqlite3
import uuid
import random
import asyncio

DB_PATH = "/var/www/ai-god-of-stocks/ai_god.db"

# AI角色回复模板（每个角色的性格）
AI_PERSONAS = {
    "1": {
        "name": "Ryan", "emoji": "📈",
        "style": "动量派", "tone": "直接犀利",
        "focus": "关注动量、成交量、趋势跟随",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "2": {
        "name": "Tyler", "emoji": "🔄", 
        "style": "趋势派", "tone": "温和理性",
        "focus": "关注趋势线、均线系统、波段操作",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "3": {
        "name": "周逆行", "emoji": "🌍",
        "style": "逆向思维", "tone": "冷静深刻",
        "focus": "关注反向逻辑、市场情绪拐点",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "4": {
        "name": "David Chen", "emoji": "💎",
        "style": "宏观派", "tone": "稳重全面",
        "focus": "关注宏观政策、资金流向、地缘政治",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "5": {
        "name": "方守成", "emoji": "📊",
        "style": "价值投资", "tone": "耐心从容",
        "focus": "关注估值、护城河、长期价值",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "6": {
        "name": "林数理", "emoji": "📉",
        "style": "数量派", "tone": "严谨精确",
        "focus": "关注数据模型、统计规律、量化信号",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "7": {
        "name": "韩科捷", "emoji": "⚡",
        "style": "赛道投资", "tone": "敏锐果断",
        "focus": "关注行业景气度、政策导向、赛道龙头",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "8": {
        "name": "James Wong", "emoji": "🎯",
        "style": "精准选股", "tone": "专业细致",
        "focus": "关注个股基本面、技术面共振点",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "9": {
        "name": "沈闻", "emoji": "🔮",
        "style": "综合分析", "tone": "全面中肯",
        "focus": "综合多维度分析，寻找最佳机会",
        "reply_template": "【{name}·{style}】\n{analysis}"
    },
    "10": {
        "name": "Mike", "emoji": "💰",
        "style": "动量派", "tone": "直接果断",
        "focus": "关注强势股、突破买点、止损纪律",
        "reply_template": "【{name}·{style}】\n{analysis}"
    }
}

# 回复内容模板库
REPLY_TEMPLATES = {
    "持仓炫耀": [
        "你的买入时机值得关注。{style}角度来看，{analysis}",
        "买入逻辑我理解，但{style}视角有些不同：{analysis}"
    ],
    "求助分析": [
        "从{style}角度分析这个问题：{analysis}",
        "这是个有意思的问题，{style}视角来看：{analysis}"
    ],
    "抄作业": [
        "跟买需要技巧，{style}风格建议：{analysis}",
        "抄作业可以，但{style}的风控不能忘：{analysis}"
    ],
    "默认": [
        "你的想法我听到了，{style}视角：{analysis}",
        "让我从{style}角度给你一些参考：{analysis}"
    ]
}

def get_reply_type(content):
    """判断用户发帖类型"""
    content = content.lower()
    if any(k in content for k in ['买入', '入手', '建仓', '入了', '买了', '成本', '持仓']):
        if any(k in content for k in ['元', '块', '价格', '价位']):
            return "持仓炫耀"
    if any(k in content for k in ['怎么看', '求分析', '分析一下', '帮我看']):
        return "求助分析"
    if any(k in content for k in ['跟买', '抄作业', '买什么', '推荐']):
        return "抄作业"
    return "默认"

def generate_analysis(ai_id, content, symbol=None, stock_name=None, price=None):
    """根据AI角色风格生成回复"""
    persona = AI_PERSONAS.get(str(ai_id), AI_PERSONAS["1"])
    reply_type = get_reply_type(content)
    template = random.choice(REPLY_TEMPLATES.get(reply_type, REPLY_TEMPLATES["默认"]))
    
    # 生成具体分析内容
    if symbol and stock_name:
        stock_info = f"{stock_name}({symbol})"
        if price:
            stock_info += f" 价格{price}元"
    else:
        stock_info = "你说的股票"
    
    analyses = [
        f"{stock_info}近期走势值得关注。如果你是{persona['style']},建议关注动量是否持续,设置合理的止损位。",
        f"关于{stock_info}，{persona['style']}的判断是：需要观察是否有足够的市场情绪支撑。",
        f"{persona['focus']}角度看{stock_info}，关键看成交量能否配合。如果缩量就要小心。",
        f"{stock_info}这个位置，{persona['style']}会先看趋势是否完好。建议分批建仓,控制仓位。",
        f"作为{persona['style']}，我关注的是{stock_info}的资金面。如果主力持续流入，可以考虑跟进。",
    ]
    
    analysis = random.choice(analyses)
    content = persona["reply_template"].format(
        name=persona["name"],
        style=persona["style"],
        analysis=analysis
    )
    return content

def main():
    if len(sys.argv) < 4:
        print("Usage: python3 trigger_ai_reply.py <post_id> <mentions_json> <user_content>")
        sys.exit(1)
    
    post_id = sys.argv[1]
    mentions = json.loads(sys.argv[2])
    user_content = sys.argv[3]
    symbol = sys.argv[4] if len(sys.argv) > 4 else ""
    stock_name = sys.argv[5] if len(sys.argv) > 5 else ""
    price = sys.argv[6] if len(sys.argv) > 6 else "0"
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    try:
        # 获取原帖信息
        post = conn.execute(
            "SELECT * FROM ai_posts WHERE id=? OR post_id=?", 
            (post_id, post_id)
        ).fetchone()
        
        if not post:
            print(f"Post not found: {post_id}")
            return
        
        print(f"Processing post {post_id}, mentions: {mentions}")
        
        for ai_id in mentions:
            if str(ai_id) not in AI_PERSONAS:
                continue
            
            # 生成AI回复
            content = generate_analysis(
                ai_id, user_content, symbol, stock_name, price
            )
            
            # 写入数据库
            reply_post_id = str(uuid.uuid4())[:8]
            conn.execute("""
                INSERT INTO ai_posts 
                (post_id, ai_id, title, content, post_type, author_type, parent_id, 
                 action, signal, created_at, ai_name, visibility)
                VALUES (?, ?, '', ?, 'mention_reply', 'ai', ?, 'MENTION_REPLY', ?, 
                        datetime('now', '+8 hours'), ?, 'public')
            """, (
                reply_post_id, ai_id, content, post["id"] if post else None,
                AI_PERSONAS[str(ai_id)]["emoji"],
                AI_PERSONAS[str(ai_id)]["name"]
            ))
            
            # 增加AI人气值
            conn.execute("""
                UPDATE ai_characters SET popularity = popularity + 1 WHERE id=?
            """, (ai_id,))
            
            print(f"AI {ai_id} replied to post {post_id}")
        
        # 更新原帖回复数
        conn.execute("""
            UPDATE ai_posts SET replies = replies + ? WHERE id=? OR post_id=?
        """, (len(mentions), post_id, post_id))
        
        conn.commit()
        print(f"Successfully generated {len(mentions)} AI replies for post {post_id}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
