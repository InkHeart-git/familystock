#!/usr/bin/env python3
"""只对有正文(>30字)的新闻评分"""
import sqlite3, os, time, json, logging, sys, asyncio, re
from datetime import datetime

SQLITE_PATH = '/var/www/familystock/api/data/family_stock.db'
BATCH_SIZE = 10
SLEEP_BETWEEN = 3

def load_env():
    from pathlib import Path
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k, v)

load_env()

import sys as _sys
_sys.path.insert(0, '/var/www/ai-god-of-stocks')
from engine.llm_guardian import call as guardian_call

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('/var/log/sentiment_focused.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

async def call_llm(prompt, system=''):
    """统一LLM调用（通过llm_guardian自动fallback）"""
    loop = asyncio.get_event_loop()
    ok, content, provider = await loop.run_in_executor(
        None, lambda: guardian_call(prompt, system=system, model_preference='minimax')
    )
    if not ok:
        raise Exception(f'LLM all providers failed: {content}')
    logger.info(f'  [LLM] via {provider}')
    return content

def get_conn():
    conn = sqlite3.connect(SQLITE_PATH)
    conn.execute('PRAGMA journal_mode=WAL')
    return conn

def get_batch(conn):
    cur = conn.execute(
        "SELECT id, title, content FROM news WHERE sentiment IS NULL AND LENGTH(COALESCE(content,'')) > 30 ORDER BY published_at DESC LIMIT ?",
        (BATCH_SIZE,)
    )
    return cur.fetchall()

def update(conn, scores):
    n = 0
    for nid, score in scores:
        conn.execute("UPDATE news SET sentiment=? WHERE id=?", (score, nid))
        n += 1
    conn.commit()
    return n

def parse_scores(text, batch):
    try:
        # 过滤思考标签
        text = re.sub(r'<think>[^\]]*?\]\s*', '', text, flags=re.DOTALL)
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text).strip()
        m = re.search(r'\{\s*"r"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
        if not m:
            try: data = json.loads(text); results = data.get('r', [])
            except: return []
        else:
            data = json.loads(m.group()); results = data.get('r', [])
        scores = []
        for r in results:
            nid = str(r.get('i', ''))
            score = float(r.get('s', 0))
            score = max(-1.0, min(1.0, score))
            if nid: scores.append((nid, score))
        return scores
    except:
        return []

async def main():
    logger.info('情感评分系统 v2 (llm_guardian protected)')
    conn = get_conn()
    batch_num = 0
    total = 0
    while True:
        batch = get_batch(conn)
        if not batch: logger.info('全部完成!'); break
        batch_num += 1
        logger.info(f'批次 #{batch_num}: {len(batch)}条...')
        lines = [f'{i+1}|{nid}|{title[:40]}|{(c or "")[:80].replace(chr(10)," ")}'
                 for i,(nid,title,c) in enumerate(batch)]
        prompt = '财经新闻情感评分，返回JSON: {"r":[{"i":"ID","s":分数}]}\n分数: 1极利好,0.5利好,0中性,-0.5利空,-1极利空\n' + '\n'.join(lines)
        try:
            resp = await call_llm(prompt, system='你是专业财经分析师。返回严格JSON格式。')
            scores = parse_scores(resp, batch)
            saved = update(conn, scores)
            total += saved
            logger.info(f'  → 入库 {saved} 条')
            for nid, s in scores[:3]: logger.info(f'    [{nid}] {s:+.2f}')
        except Exception as e:
            logger.error(f'  → 失败: {e}')
        await asyncio.sleep(SLEEP_BETWEEN)
    conn.close()
    logger.info(f'✅ 完成! 本轮入库: {total} 条')

asyncio.run(main())
