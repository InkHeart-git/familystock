#!/usr/bin/env python3
"""
Task 5: 交易信号可视化 - 同步AI帖子到BBS并添加emoji信号
将 ai_god.db 中的 ai_posts 同步到 familystock 的 bbs.db，并添加信号emoji
"""
import sqlite3
import uuid
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    handlers=[
        logging.FileHandler('/var/www/ai-god-of-stocks/logs/bbs_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

AI_GOD_DB = "/var/www/ai-god-of-stocks/ai_god.db"
BBS_DB = "/var/www/ai-god-of-stocks/ai_god.db"

# emoji映射
SIGNAL_EMOJI = {
    "buy": "🟢",      # 建议加仓
    "sell": "🔴",     # 建议减仓
    "hold": "🟡",     # 继续持有
    "watch": "⚪",    # 观望
}

# 头像emoji
AI_AVATARS = {
    "1": "📈", "2": "📊", "3": "💎", "4": "⚡", "5": "🌍",
    "6": "🚀", "7": "💰", "8": "🔄", "9": "📈", "10": "🎯"
}

def get_ai_god_posts():
    """从 ai_god.db 获取最新的 ai_posts"""
    conn = sqlite3.connect(AI_GOD_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT post_id, ai_id, ai_name, title, content, action, created_at
        FROM ai_posts 
        ORDER BY created_at DESC 
        LIMIT 50
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def sync_to_bbs(posts):
    """同步帖子到 bbs.db"""
    conn = sqlite3.connect(BBS_DB)
    cursor = conn.cursor()
    
    synced = 0
    skipped = 0
    
    for post in posts:
        post_id = post['post_id']
        ai_id = post['ai_id']
        ai_name = post['ai_name']
        title = post['title']
        content = post['content']
        action = post.get('action', 'watch') or 'watch'
        signal_emoji = SIGNAL_EMOJI.get(action, SIGNAL_EMOJI['watch'])
        timestamp = post['created_at']
        
        # 获取头像emoji
        avatar = AI_AVATARS.get(str(ai_id), "📊")
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM bbs_posts WHERE id=?", (post_id,))
        if cursor.fetchone():
            skipped += 1
            continue
        
        # 转换内容：添加信号emoji到标题
        signal_prefix = f"{signal_emoji} "
        if not title.startswith(signal_emoji):
            title = f"{signal_prefix}{title}"
        
        # 插入 bbs_posts 表
        cursor.execute("""
            INSERT INTO bbs_posts (id, ai_id, ai_name, ai_avatar, post_type, content, signal, timestamp, replies, likes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
        """, (post_id, ai_id, ai_name, avatar, action, f"**{title}**\n\n{content}", signal_emoji, timestamp))
        
        synced += 1
    
    conn.commit()
    conn.close()
    
    return synced, skipped

def main():
    logger.info("========== Task 5: BBS信号同步 ==========")
    
    # 获取 ai_god 中的帖子
    posts = get_ai_god_posts()
    logger.info(f"从 ai_god.db 获取 {len(posts)} 条帖子")
    
    if not posts:
        logger.info("没有新帖子需要同步")
        return
    
    # 同步到 bbs
    synced, skipped = sync_to_bbs(posts)
    logger.info(f"同步完成: 新增 {synced} 条, 跳过 {skipped} 条")
    
    # 显示最新帖子
    logger.info("\n📊 最新BBS帖子预览:")
    for post in posts[:5]:
        action = post.get('action', 'watch')
        emoji = SIGNAL_EMOJI.get(action, '⚪')
        logger.info(f"  {emoji} [{post['ai_name']}] {post['title'][:40]}...")

if __name__ == "__main__":
    main()
