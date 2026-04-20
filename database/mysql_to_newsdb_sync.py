#!/usr/bin/env python3
"""
MySQL(familystock) → SQLite(news.db) 新闻同步
把MySQL里4576条历史新闻同步到 news.db 并做情感分析
"""
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

import pymysql
import sqlite3
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
logger = logging.getLogger()

DB_MYSQL = {
    'host': 'localhost',
    'user': 'familystock',
    'password': 'Familystock@2026',
    'database': 'familystock',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}
DB_SQLITE = '/var/www/ai-god-of-stocks/data/news.db'

BATCH_SIZE = 200


def get_mysql_news():
    conn = pymysql.connect(**DB_MYSQL)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, title, content, source, url, published_at,
                   sentiment_score, keywords
            FROM news
            WHERE title IS NOT NULL AND title != ''
            ORDER BY published_at ASC
        """)
        rows = cur.fetchall()
    conn.close()
    logger.info(f"MySQL读取: {len(rows)} 条新闻")
    return rows


def sync_to_sqlite(rows: list) -> int:
    """
    同步到SQLite，INSERT OR IGNORE（已有则跳过）
    sentiment 为 NULL 的新闻用 LLM 分析情感
    """
    conn = sqlite3.connect(DB_SQLITE)
    conn.execute("PRAGMA journal_mode=WAL")

    inserted = 0
    needs_analysis = []

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        for r in batch:
            # 转换 MySQL sentiment_score (decimal) → SQLite sentiment (float)
            sentiment_raw = r.get('sentiment_score')
            sentiment_val = float(sentiment_raw) if (sentiment_raw is not None and sentiment_raw != '') else None

            keywords = r.get('keywords', '') or ''

            try:
                pub_at = r['published_at'].strftime('%Y-%m-%d %H:%M:%S') if isinstance(r['published_at'], datetime) else str(r['published_at'])
            except:
                pub_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            title_key = r.get('title', '')[:200]
            source_key = r.get('source', '') or '未知'
            # 用 (source, title) 作为去重键
            cur = conn.execute("""
                DELETE FROM news WHERE source = ? AND substr(title, 1, 200) = ?
            """, (source_key, title_key))
            cur = conn.execute("""
                INSERT INTO news
                (title, content, source, url, published_at, sentiment, keywords, relevance, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('title', ''),
                r.get('content', '') or '',
                r.get('source', '') or '未知',
                r.get('url', '') or '',
                pub_at,
                sentiment_val,
                keywords,
                0.5,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            if cur.rowcount > 0:
                inserted += 1
                if sentiment_val is None:
                    needs_analysis.append((r['title'], r.get('content', '') or '', r['url']))

        logger.info(f"  批次 {i//BATCH_SIZE + 1}: 已插入 {inserted} 条")
        time.sleep(0.1)

    conn.commit()
    conn.close()
    return inserted, needs_analysis


def analyze_sentiment_batch(items: list) -> list:
    """
    对无情感的news用LLM分析情感
    返回: [(url, sentiment_score), ...]
    """
    if not items:
        return []

    results = []
    # 批量分析（每批5条，控制速率）
    for i in range(0, len(items), 5):
        batch = items[i:i+5]
        for title, content, url in batch:
            sentiment = analyze_single(title, content)
            results.append((url, sentiment))
            logger.info(f"  情感分析: {title[:40]} → {sentiment:+.2f}")
            time.sleep(0.3)
    return results


def analyze_single(title: str, content: str) -> float:
    """用LLM分析单条新闻情感，返回 -1~1 """
    try:
        import asyncio
        from engine.llm_client import get_llm_client
        client = get_llm_client()

        text = f"{title}\n{content[:200]}".strip()
        prompt = (
            f"分析以下财经新闻的情感倾向，只输出一个数字：\n"
            f"1=非常利好，0.5=略利好，0=中性，-0.5=略利空，-1=非常利空\n\n"
            f"新闻：{text}"
        )

        async def _run():
            r = await client.generate(prompt, max_tokens=8)
            # 提取数字
            import re
            m = re.search(r'[-−]?[\d.]+', str(r).strip())
            if m:
                val = float(m.group())
                return max(-1.0, min(1.0, val))
            return 0.0

        return asyncio.run(_run())
    except Exception as e:
        logger.warning(f"  LLM情感分析失败: {e}")
        return 0.0


def update_sentiment(url_to_sentiment: list):
    """更新 SQLite 中对应 URL 新闻的情感值"""
    if not url_to_sentiment:
        return
    conn = sqlite3.connect(DB_SQLITE)
    for url, sentiment in url_to_sentiment:
        conn.execute("UPDATE news SET sentiment=? WHERE url=? AND (sentiment IS NULL OR sentiment='')", (sentiment, url))
    conn.commit()
    conn.close()
    logger.info(f"  更新 {len(url_to_sentiment)} 条情感值")


def main():
    logger.info("=== MySQL → SQLite 新闻同步 ===")

    # 1. 读取 MySQL 全部新闻
    rows = get_mysql_news()
    if not rows:
        logger.warning("MySQL无新闻数据")
        return

    # 2. 同步到 SQLite
    inserted, needs_analysis = sync_to_sqlite(rows)
    logger.info(f"✅ 同步完成: 新增 {inserted} 条")

    # 3. LLM 情感分析（无情感的记录）
    if needs_analysis:
        logger.info(f"📰 开始LLM情感分析: {len(needs_analysis)} 条无情感新闻...")
        analyzed = analyze_sentiment_batch(needs_analysis)
        update_sentiment(analyzed)
        logger.info(f"✅ 情感分析完成: {len(analyzed)} 条")
    else:
        logger.info("✅ 所有新闻已有情感标注")

    # 4. 验证
    conn = sqlite3.connect(DB_SQLITE)
    total = conn.execute("SELECT COUNT(*) FROM news").fetchone()[0]
    with_sent = conn.execute("SELECT COUNT(*) FROM news WHERE sentiment IS NOT NULL AND sentiment != ''").fetchone()[0]
    logger.info(f"=== SQLite news.db 最终统计 ===")
    logger.info(f"  总新闻数: {total}")
    logger.info(f"  有情感标注: {with_sent}")
    logger.info(f"  无情感: {total - with_sent}")
    conn.close()


if __name__ == '__main__':
    main()
