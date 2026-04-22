#!/usr/bin/env python3
"""
MiniRock 情感评分系统 v2.0
- 每批10条（避免prompt过长导致截断）
- 直接调用MiniMax API（跳过fallback提速）
- 精简prompt（JSON格式严格要求）
"""
import sqlite3
import sys
import os
import time
import json
import logging
import re
import asyncio
import aiohttp
from datetime import datetime

# ========== 配置 ==========
VENV_PYTHON = '/var/www/familystock/api/venv/bin/python3'
SQLITE_PATH = '/var/www/familystock/api/data/family_stock.db'
LOG_PATH = '/var/log/sentiment_analyzer.log'
BATCH_SIZE = 10        # 每批10条（避免prompt过长导致截断）
MAX_BATCHES = 99999   # 无限制，跑完所有数据
SLEEP_BETWEEN = 3     # 批次间隔秒

# ========== 加载环境变量 ==========
def load_env():
    """从 ~/.hermes/.env 加载环境变量"""
    from pathlib import Path
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k, v)
    os.environ.setdefault('MINIMAX_CN_BASE_URL', 'https://api.minimaxi.com/v1')

load_env()

# ========== MiniMax API ==========
MINIMAX_KEY = os.getenv('MINIMAX_CN_API_KEY', os.getenv('MINIMAX_API_KEY', ''))
MINIMAX_URL = os.getenv('MINIMAX_CN_BASE_URL', 'https://api.minimaxi.com/v1') + '/chat/completions'
MODEL = 'MiniMax-M2.7-highspeed'

async def call_minimax(prompt: str, system: str = '') -> str:
    """直接调用MiniMax API"""
    headers = {
        'Authorization': f'Bearer {MINIMAX_KEY}',
        'Content-Type': 'application/json',
    }
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    
    payload = {
        'model': MODEL,
        'messages': messages,
        'max_tokens': 600,
        'temperature': 0.1,
    }
    
    async with aiohttp.ClientSession() as sess:
        async with sess.post(MINIMAX_URL, headers=headers, json=payload,
                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
            text = await resp.text()
            if resp.status != 200:
                raise Exception(f'HTTP {resp.status}: {text[:200]}')
            data = json.loads(text)
            return data['choices'][0]['message']['content']

# ========== 日志 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ========== 评分 ==========
async def score_batch(batch, client):
    """对一批新闻评分，batch=[(nid, title, content), ...]"""
    if not batch:
        return []
    
    # 精简prompt，每条一行
    lines = []
    for i, (nid, title, content) in enumerate(batch):
        c = (content or '')[:100].replace('\n', ' ')
        lines.append(f'{i+1}|{nid}|{title[:50]}|{c}')
    
    example = '{"r":[{"i":"ID1","s":0.5},{"i":"ID2","s":-0.3}]}'
    sep = '|||'
    prompt = f'''判断以下新闻对A股影响，返回JSON格式（只输出JSON，禁止其他内容）:
{example}
分数: 1=极利好, 0.5=利好, 0=中性, -0.5=利空, -1=极利空
{sep.join(lines)}'''
    
    try:
        response = await client(prompt, system='你是一个专业的A股财经新闻情感分析师。输出格式: {"r":[{"i":"新闻ID","s":分数}]}')
        
        # 提取JSON（容错：处理```json包裹和截断）
        text = response.strip()
        # 去掉 ```json 包裹
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        # 去掉 <think> 思考块
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # 尝试修复截断JSON
        # 1. 找最后一个完整的对象
        m = re.search(r'\{\s*"r"\s*:\s*\[.*\]\s*\}', text, re.DOTALL)
        if not m:
            # 2. 尝试截取到最后一个有效闭合
            m = re.search(r'\{\s*"r"\s*:\s*\[', text, re.DOTALL)
            if m:
                # 找到起始位置，尝试补全
                partial = text[m.start():]
                # 尝试修复常见截断
                partial = re.sub(r'({"i":"|{"s":)"[^"]*$', '', partial)
                text = partial
        
        # 先移除所有 <think>...</think> 思考块
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        text = text.strip()
        
        # 尝试直接解析整个text（先去掉 ```json 包裹）
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        text = text.strip()
        
        # 找JSON对象或数组
        m = re.search(r'\{\s*"r"\s*:\s*\[.*?\]\s*\}', text, re.DOTALL)
        if m:
            data = json.loads(m.group())
            results = data.get('r', [])
        else:
            # 尝试直接解析整个text
            try:
                data = json.loads(text)
                results = data.get('r', [])
            except json.JSONDecodeError:
                results = []
        
        # 转换格式: {"i": "id", "s": score} → [(nid, score), ...]
        scores = []
        for r in results:
            nid = str(r.get('i', ''))
            score = float(r.get('s', 0))
            score = max(-1.0, min(1.0, score))
            # 保留所有有效分数（含中性0），避免新闻永远卡在待评分队列
            if nid and score == score:  # 过滤NaN
                scores.append((nid, score))
        
        return scores

    except json.JSONDecodeError as e:
        logger.warning(f'JSON解析失败: {e}, 剩余text: {text[:100]}')
        return []
    except Exception as e:
        logger.warning(f'评分失败: {e}')
        return []

# ========== 数据库 ==========
def get_conn():
    conn = sqlite3.connect(SQLITE_PATH, timeout=60)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA busy_timeout=60000')
    return conn

def get_unsent(conn, limit=10):
    cur = conn.execute('''
        SELECT id, title, content FROM news 
        WHERE sentiment IS NULL OR sentiment = 0 OR sentiment = 0.0
        ORDER BY id DESC LIMIT ?
    ''', (limit,))
    return [(str(r[0]), r[1], r[2]) for r in cur.fetchall()]

def update_sentiments(conn, scores):
    if not scores:
        return 0
    cur = conn.cursor()
    cur.executemany('UPDATE news SET sentiment=? WHERE id=?', 
                   [(score, nid) for nid, score in scores])
    conn.commit()
    return len(scores)

def get_stats(conn):
    row = conn.execute('''
        SELECT COUNT(*) as total,
               COUNT(CASE WHEN sentiment IS NOT NULL AND sentiment != 0 THEN 1 END) as scored,
               AVG(CASE WHEN sentiment IS NOT NULL AND sentiment != 0 THEN sentiment END) as avg
        FROM news
    ''').fetchone()
    return {'total': row[0], 'scored': row[1], 'unscored': row[2], 'avg': round(row[2] or 0, 3)}

# ========== 主函数 ==========
async def main_async():
    logger.info('=' * 60)
    logger.info(f'MiniRock 情感评分系统 v2.0 | {datetime.now()}')
    logger.info('=' * 60)
    
    if not MINIMAX_KEY:
        logger.error('MINIMAX_API_KEY not set'); sys.exit(1)
    logger.info(f'MiniMax API: {MINIMAX_KEY[:15]}...')

    conn = get_conn()
    stats = get_stats(conn)
    logger.info(f'当前: 总{stats["total"]}条, 已评分{stats["scored"]}条, 待评分{stats["unscored"]}条')
    
    if stats['unscored'] == 0:
        logger.info('所有新闻已完成评分'); conn.close(); return

    total_scored = 0
    
    for batch_num in range(1, MAX_BATCHES + 1):
        batch = get_unsent(conn, limit=BATCH_SIZE)
        if not batch:
            logger.info('没有更多待评分新闻')
            break
        
        logger.info(f'批次 #{batch_num}: {len(batch)}条...')
        
        scores = await score_batch(batch, call_minimax)
        
        if scores:
            saved = update_sentiments(conn, scores)
            total_scored += saved
            logger.info(f'  → 更新 {saved} 条')
            for nid, s in scores[:3]:
                logger.info(f'    [{nid}] {s:+.2f}')
        else:
            logger.warning('  → 无有效结果')
        
        time.sleep(SLEEP_BETWEEN)
    
    conn.close()
    
    final_stats = get_stats(get_conn())
    logger.info(f'\n✅ 完成! 本轮: {total_scored}条')
    logger.info(f'    累计: {final_stats["scored"]}/{final_stats["total"]}已评分, avg={final_stats["avg"]}')

def main():
    asyncio.run(main_async())

if __name__ == '__main__':
    main()
