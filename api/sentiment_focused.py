#!/usr/bin/env python3
"""只对有正文(>30字)的新闻评分"""
import sqlite3, os, time, json, logging, sys, asyncio, aiohttp, re
from datetime import datetime

SQLITE_PATH = '/var/www/familystock/api/data/family_stock.db'
MODEL = 'MiniMax-M2.7-highspeed'
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
MINIMAX_KEY = os.getenv('MINIMAX_CN_API_KEY', os.getenv('MINIMAX_API_KEY', ''))
MINIMAX_URL = os.getenv('MINIMAX_CN_BASE_URL', 'https://api.minimaxi.com/v1') + '/chat/completions'

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler('/tmp/sentiment_focused.log'), logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

async def call_minimax(prompt, system=''):
    headers = {'Authorization': f'Bearer {MINIMAX_KEY}', 'Content-Type': 'application/json'}
    messages = [{'role': 'system', 'content': system}] if system else []
    messages.append({'role': 'user', 'content': prompt})
    payload = {'model': MODEL, 'messages': messages, 'max_tokens': 600, 'temperature': 0.1}
    async with aiohttp.ClientSession() as sess:
        async with sess.post(MINIMAX_URL, headers=headers, json=payload,
                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise Exception(f'HTTP {resp.status}')
            return json.loads(text)['choices'][0]['message']['content']

def get_conn():
    conn = sqlite3.connect(SQLITE_PATH, timeout=60)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=30000')
    return conn

def get_batch(conn):
    """只取有正文且未评分的"""
    cur = conn.execute('''
        SELECT id, title, content FROM news 
        WHERE length(content) > 30
          AND sentiment IS NULL
        ORDER BY id DESC LIMIT ?
    ''', (BATCH_SIZE,))
    return [(str(r[0]), r[1], r[2]) for r in cur.fetchall()]

def update(conn, scores):
    if not scores: return 0
    cur = conn.cursor()
    cur.executemany('UPDATE news SET sentiment=? WHERE id=?', [(s, i) for i, s in scores])
    conn.commit()
    return len(scores)

def parse_scores(text, batch):
    try:
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
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
    if not MINIMAX_KEY:
        logger.error('No API key'); return
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
            resp = await call_minimax(prompt, system='你是专业财经分析师。返回严格JSON格式。')
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
