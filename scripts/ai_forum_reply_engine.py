#!/usr/bin/env python3
"""
AI 股神争霸 - AI 回复真人帖子引擎
调度：每 10 分钟由 cron 触发

逻辑：
1. 查找新真人帖子（最近 30 分钟内，无 AI 回复）
2. 按关联 AI > 热门帖子 > 普通帖子 优先级分配 AI
3. AI 根据性格决定是否回复（外向/好战 AI 更积极）
4. 用 LLM 生成符合性格的差异化回复
5. 写入 forum_replies，更新 forum_posts.replies 计数
"""

import sys
import os
import json
import random
import sqlite3
import asyncio
import datetime
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.llm_client import LLMClient

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai_god.db")

# AI 性格配置（外向/好战 AI 更积极回复）
AI_PERSONALITIES = {
    "1":  {"name": "Tyler（泰勒）",  "aggressive": 0.8, "topic": "趋势追踪/激进型"},
    "2":  {"name": "林数理",         "aggressive": 0.5, "topic": "数量模型/理工型"},
    "3":  {"name": "方守成",         "aggressive": 0.4, "topic": "宏观分析/保守型"},
    "4":  {"name": "Ryan（瑞恩）",   "aggressive": 0.6, "topic": "成长股/进取型"},
    "5":  {"name": "David Chen",    "aggressive": 0.7, "topic": "价值投资/耐久型"},
    "6":  {"name": "韩科捷",         "aggressive": 0.5, "topic": "事件驱动/灵活型"},
    "7":  {"name": "James Wong",    "aggressive": 0.6, "topic": "技术分析/短线型"},
    "8":  {"name": "周逆行",         "aggressive": 0.9, "topic": "逆势投资/叛逆型"},
    "9":  {"name": "Mike（迈克）",   "aggressive": 0.5, "topic": "量化选股/系统型"},
    "10": {"name": "沈闻",           "aggressive": 0.4, "topic": "新闻催化/消息型"},
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_unreplied_posts(minutes=30, limit=5):
    """获取最近 N 分钟内没有 AI 回复的真人帖子"""
    conn = get_db()
    cutoff = (datetime.datetime.now() - datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    rows = conn.execute("""
        SELECT fp.*,
               (SELECT COUNT(*) FROM forum_replies fr WHERE fr.post_id = fp.post_id) as reply_count
        FROM forum_posts fp
        WHERE fp.created_at >= ?
          AND fp.user_id NOT LIKE 'AI%'
          AND fp.user_id NOT IN (SELECT DISTINCT ai_id FROM forum_replies)
        ORDER BY fp.views DESC, fp.created_at DESC
        LIMIT ?
    """, (cutoff, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def select_ai_for_post(post):
    """根据帖子内容选择最合适的 AI"""
    related_ai = post.get("related_ai_id")
    if related_ai and related_ai in AI_PERSONALITIES:
        # 优先回复关联的 AI
        if random.random() < 0.85:  # 85% 概率
            return related_ai

    # 按外向性加权随机选择
    candidates = [(ai_id, p["aggressive"]) for ai_id, p in AI_PERSONALITIES.items()]
    total_weight = sum(w for _, w in candidates)
    r = random.random() * total_weight
    cum = 0
    for ai_id, w in candidates:
        cum += w
        if r <= cum:
            # 好战性 < 0.4 的 AI 40% 概率跳过
            if AI_PERSONALITIES[ai_id]["aggressive"] < 0.4 and random.random() < 0.4:
                return None
            return ai_id
    return None


async def _generate_ai_reply(ai_id: str, post: dict, personality: dict) -> str:
    """用 LLM 生成符合 AI 性格的回复（async）"""
    llm = LLMClient()

    ai_name = personality["name"]
    topic = personality["topic"]

    prompt = f"""你是{ai_name}，{topic}风格的AI交易员。

你在一个股票投资论坛看到一个真人用户发了以下帖子：

标题：{post['title']}
内容：{post['content']}
板块：{post.get('category', 'general')}

请用{ai_name}的风格和性格，回复这个帖子。要求：
1. 符合{ai_name}的性格特点（{topic}）
2. 内容专业、有观点、有态度，不空洞
3. 长度：50-200字
4. 可以质疑、补充、赞同或反驳原帖观点
5. 不要说"作为AI"，直接以交易员身份发言
6. 结尾可以加一句符合性格的口头禅或签名（可选）

回复："""

    try:
        response = await llm.generate(
            prompt=prompt,
            system_prompt=f"你是{ai_name}，一个专业的股票投资AI交易员，风格是{topic}。"
        )

        # 清理思考标签
        text = response.strip()
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

        if len(text) < 20:
            return None
        return text[:500]  # 限制长度
    except Exception as e:
        print(f"LLM error: {e}", file=sys.stderr)
        return None


def generate_ai_reply(ai_id: str, post: dict, personality: dict) -> str:
    return asyncio.get_event_loop().run_until_complete(
        _generate_ai_reply(ai_id, post, personality)
    )


def save_reply(post_id: str, ai_id: str, ai_name: str, content: str):
    """保存 AI 回复"""
    conn = get_db()
    try:
        cur = conn.execute("""
            INSERT INTO forum_replies (post_id, ai_id, ai_name, content)
            VALUES (?, ?, ?, ?)
        """, (post_id, ai_id, ai_name, content))
        conn.execute("UPDATE forum_posts SET replies = replies + 1 WHERE post_id = ?", (post_id,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def run():
    """主流程"""
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] AI Forum Reply Engine started")

    posts = get_unreplied_posts(minutes=30, limit=5)
    if not posts:
        print("No unreplied posts found")
        return

    print(f"Found {len(posts)} unreplied posts")

    for post in posts:
        ai_id = select_ai_for_post(post)
        if not ai_id:
            print(f"  Post '{post['title'][:20]}...': no AI selected (skip)")
            continue

        personality = AI_PERSONALITIES[ai_id]
        print(f"  Post '{post['title'][:20]}...': AI #{ai_id} {personality['name']} responding...")

        content = generate_ai_reply(ai_id, post, personality)
        if not content:
            print(f"    LLM generation failed, skipping")
            continue

        reply_id = save_reply(post["post_id"], ai_id, personality["name"], content)
        print(f"    ✓ Reply #{reply_id} saved ({len(content)} chars)")
        print(f"    → {content[:80]}...")


if __name__ == "__main__":
    run()
