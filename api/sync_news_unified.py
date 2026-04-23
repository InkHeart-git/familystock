#!/usr/bin/env python3
"""
MiniRock 统一新闻采集脚本 v1.0
数据源: 财联社(主力) + 同花顺(补充) + Tushare(兜底)
写入: family_stock.db
调度: 每30分钟 cron
"""
import requests
import sqlite3
import time
import re
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# ========== 配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('/var/log/sync_news_unified.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

VENV_PYTHON = '/var/www/familystock/api/venv/bin/python3'
SQLITE_PATH = '/var/www/familystock/api/data/family_stock.db'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# ========== 数据库初始化 ==========
def get_conn():
    """获取数据库连接（WAL模式，超时30秒防锁）"""
    conn = sqlite3.connect(SQLITE_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    """确保必要字段存在"""
    conn = get_conn()
    cur = conn.cursor()
    
    # 新增字段（兼容已有数据）
    new_columns = [
        ('relevance', 'REAL DEFAULT 0'),
        ('event_type', 'TEXT DEFAULT "normal"'),
        ('author', 'TEXT DEFAULT ""'),
        ('blogger_source', 'TEXT DEFAULT ""'),
        ('source_platform', 'TEXT DEFAULT ""'),
        ('hot_score', 'REAL DEFAULT 0'),
        ('keywords', 'TEXT DEFAULT ""'),
    ]
    
    existing = {row[1] for row in conn.execute("PRAGMA table_info(news)").fetchall()}
    
    for col_name, col_def in new_columns:
        if col_name not in existing:
            conn.execute(f"ALTER TABLE news ADD COLUMN {col_name} {col_def}")
            logger.info(f"新增字段: {col_name}")
    
    conn.commit()
    conn.close()
    logger.info("数据库初始化完成")

# ========== 工具函数 ==========
def extract_stock_codes(text):
    """从文本中提取A股股票代码"""
    if not text:
        return []
    # 匹配 6 位数字，以 0/3/6 开头
    codes = re.findall(r'\b([036]\d{5})\b', text)
    valid = []
    for code in codes:
        if code not in valid:  # 去重
            # 过滤明显不是股票的场景（如日期、时间戳）
            if not re.match(r'^[036]\d{5}$', code):
                continue
            valid.append(code)
    return valid[:5]  # 最多5个

def clean_html(text):
    """简单HTML清理"""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&')
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:200]

def normalize_time(time_str):
    """标准化时间字符串"""
    if not time_str:
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    # 处理各种格式
    time_str = str(time_str)
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%m-%d %H:%M']:
        try:
            return datetime.strptime(time_str, fmt).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def is_duplicate(conn, title, source):
    """检查是否重复（同一标题+同一来源）"""
    cur = conn.execute(
        "SELECT id FROM news WHERE title = ? AND source = ? LIMIT 1",
        (title.strip(), source)
    )
    return cur.fetchone() is not None

def save_to_db(news_list, source_platform):
    """批量保存到 family_stock.db"""
    if not news_list:
        return 0
    
    conn = get_conn()
    saved = 0
    
    for item in news_list:
        try:
            title = item.get('title', '').strip()
            content = clean_html(item.get('content', '') or item.get('summary', ''))
            source = item.get('source', source_platform)
            url = item.get('url', '')
            published_at = normalize_time(item.get('published_at', ''))
            author = item.get('author', '')
            keywords = item.get('keywords', '')
            event_type = item.get('event_type', 'normal')
            blogger_source = item.get('blogger_source', '')
            
            if not title:
                continue
            
            # 检查重复
            if is_duplicate(conn, title, source):
                continue
            
            conn.execute("""
                INSERT INTO news (title, content, source, url, category, published_at, 
                                 source_platform, author, keywords, event_type, blogger_source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, content, source, url, item.get('category', '财经'),
                  published_at, source_platform, author, keywords, event_type, blogger_source))
            saved += 1
            
        except Exception as e:
            logger.debug(f"保存失败: {e}")
            continue
    
    conn.commit()
    conn.close()
    return saved

# ========== 数据源 1: 财联社 (主力) ==========
def fetch_cls_news():
    """财联社快讯 - 每30分钟50条，有重要度分级"""
    logger.info("抓取财联社...")
    try:
        r = requests.get(
            'https://www.cls.cn/nodeapi/updateTelegraphList',
            params={
                'page': 1,
                'pageSize': 50,
                'hasFirstVipArticle': 0,
                'rn': 50,
                'type': '',
                'lastTime': ''
            },
            headers={**HEADERS, 'Referer': 'https://www.cls.cn/', 'Host': 'www.cls.cn'},
            timeout=15
        )
        d = r.json()
        items = d.get('data', {}).get('roll_data', [])
        
        news_list = []
        for item in items:
            title = item.get('title', '').strip()
            content = item.get('content', '') or item.get('summary', '')
            
            # 提取关键词
            stock_codes = extract_stock_codes(title + content)
            keywords = ','.join(stock_codes)
            
            # 事件类型判断
            event_type = detect_event_type(title, content)
            
            news_list.append({
                'title': title,
                'content': content,
                'source': '财联社',
                'source_platform': 'cls',
                'published_at': item.get('ctime', ''),
                'url': item.get('share_url', ''),
                'category': item.get('tag', '财经'),
                'author': '',
                'keywords': keywords,
                'event_type': event_type,
            })
        
        logger.info(f"  财联社: 获取{len(items)}条")
        return news_list
        
    except Exception as e:
        logger.error(f"  财联社抓取失败: {e}")
        return []

# ========== 数据源 2: 同花顺 ==========
def fetch_ths_news():
    """同花顺财经 - 补充20条"""
    logger.info("抓取同花顺...")
    try:
        news_list = []
        # 不分类，一次性拿20条
        r = requests.get(
            'https://news.10jqka.com.cn/tapp/news/push/stock/',
            params={'page': 1, 'tag': '', 'track': 'website', 'pageSize': 20, 'type': ''},
            headers={**HEADERS, 'Referer': 'https://www.10jqka.com.cn/', 'Host': 'news.10jqka.com.cn'},
            timeout=15
        )
        d = r.json()
        items = d.get('data', {}).get('list', []) if d.get('data') else []
        
        for item in items:
            title = item.get('title', '').strip()
            content = item.get('summary', '') or item.get('content', '')
            stock_codes = extract_stock_codes(title + content)
            event_type = detect_event_type(title, content)
            
            news_list.append({
                'title': title,
                'content': content,
                'source': '同花顺',
                'source_platform': 'ths',
                'published_at': item.get('ctime', ''),
                'url': '',
                'category': item.get('tag', '财经'),
                'author': item.get('from', ''),
                'keywords': ','.join(stock_codes),
                'event_type': event_type,
            })
        
        logger.info(f"  同花顺: 获取{len(news_list)}条")
        return news_list
        
    except Exception as e:
        logger.error(f"  同花顺抓取失败: {e}")
        return []

# ========== 数据源 3: Tushare (兜底, 每30分钟1次) ==========
def fetch_tushare_news():
    """Tushare新闻 - 兜底，每30分钟最多1次"""
    logger.info("抓取Tushare(兜底)...")
    try:
        # 直接HTTP调用，避免tushare库版本问题
        TOKEN = 'b31f583510c577daeaba75b66f1125d36aa9ce380e0a8dd9f999dac2'
        r = requests.post(
            'https://api.tushare.pro',
            json={
                'api_name': 'news',
                'token': TOKEN,
                'params': {'datetime': datetime.now().strftime('%Y%m%d000000'), 'limit': 10},
                'fields': 'datetime,title,content,source,channel'
            },
            headers={'Content-Type': 'application/json'},
            timeout=15
        )
        d = r.json()
        
        if d.get('code') != 0:
            logger.warning(f"  Tushare: {d.get('msg', 'unknown error')}")
            return []
        
        fields = d.get('data', {}).get('fields', [])
        items = d.get('data', {}).get('items', [])
        
        news_list = []
        for item in items:
            row = dict(zip(fields, item))
            title = row.get('title', '').strip()
            content = row.get('content', '') or ''
            stock_codes = extract_stock_codes(title + content)
            event_type = detect_event_type(title, content)
            
            news_list.append({
                'title': title,
                'content': content[:500],
                'source': f"Tushare-{row.get('source', '财经')}",
                'source_platform': 'tushare',
                'published_at': row.get('datetime', ''),
                'url': '',
                'category': '财经',
                'author': '',
                'keywords': ','.join(stock_codes),
                'event_type': event_type,
            })
        
        logger.info(f"  Tushare: 获取{len(news_list)}条")
        return news_list
        
    except Exception as e:
        logger.error(f"  Tushare抓取失败: {e}")
        return []

# ========== 数据源 4: 微博热搜 ==========
def fetch_weibo_hot():
    """微博热搜榜 - 每30分钟抓取"""
    logger.info("抓取微博热搜...")
    try:
        r = requests.get(
            'https://weibo.com/ajax/statuses/hot_band',
            headers={
                **HEADERS,
                'Referer': 'https://weibo.com/',
                'Accept': 'application/json, text/plain, */*',
                'MWeibo-Pwa': '1',
                'X-Requested-With': 'XMLHttpRequest',
            },
            timeout=10
        )
        
        if r.status_code != 200:
            logger.warning(f"  微博热搜: HTTP {r.status_code}")
            return []
        
        d = r.json()
        
        # 微博热搜数据结构: band_list 或 hot_band
        band_list = d.get('data', {}).get('band_list', [])
        
        if not band_list:
            # 尝试其他格式
            band_list = d.get('band_list', [])
        
        news_list = []
        for i, item in enumerate(band_list[:15]):  # 最多15条
            try:
                word = item.get('word', item.get('name', ''))
                if not word:
                    continue
                
                event_type = detect_event_type(word, '')
                stock_codes = extract_stock_codes(word)
                
                news_list.append({
                    'title': f"🔥 {word}",
                    'content': f"微博热搜第{i+1}名",
                    'source': '微博热搜',
                    'source_platform': 'weibo',
                    'published_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'url': f'https://s.weibo.com/weibo?q={word}',
                    'category': '热搜',
                    'author': '',
                    'keywords': ','.join(stock_codes),
                    'event_type': event_type,
                })
            except Exception as e:
                continue
        
        logger.info(f"  微博热搜: 获取{len(news_list)}条")
        return news_list
        
    except Exception as e:
        logger.warning(f"  微博热搜抓取失败: {e}")
        return []

# ========== 数据源 5: RSS订阅 ==========
import xml.etree.ElementTree as ET

RSS_FEEDS = [
    # 财经媒体（已验证可用）
    ('https://rss.sina.com.cn/news/china/focus15.xml', '新浪财经RSS'),
    ('https://www.36kr.com/feed', '36氪RSS'),
]

def fetch_rss_feed(feed_url, feed_name):
    """解析单个RSS feed"""
    news_list = []
    try:
        r = requests.get(feed_url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return news_list
        
        root = ET.fromstring(r.content)
        
        # 通用RSS/Atom解析
        items = root.findall('.//item') or root.findall('.//entry')
        
        for item in items[:10]:  # 每feed最多10条
            try:
                title = ''
                link = ''
                pub_time = ''
                content = ''
                
                # RSS 2.0
                for child in item:
                    tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if tag == 'title':
                        title = child.text or ''
                    elif tag == 'link':
                        link = child.text or ''
                    elif tag == 'pubDate':
                        pub_time = child.text or ''
                    elif tag in ('description', 'content:encoded', 'summary'):
                        content = (child.text or '')[:300]
                
                # Atom
                if not link:
                    link_el = item.find('.//link')
                    if link_el is not None:
                        link = link_el.get('href', '') or link_el.text or ''
                
                if not title:
                    continue
                
                title = ' '.join(title.split()).strip()  # 移除所有多余空白
                if not title:
                    continue
                
                # 保留原始URL（含新浪重定向）

                event_type = detect_event_type(title, content)
                stock_codes = extract_stock_codes(title + content)
                
                news_list.append({
                    'title': title,
                    'content': content,
                    'source': f'RSS-{feed_name}',
                    'source_platform': 'rss',
                    'published_at': normalize_time(pub_time),
                    'url': link,
                    'category': 'RSS',
                    'author': feed_name,
                    'keywords': ','.join(stock_codes),
                    'event_type': event_type,
                })
            except Exception:
                continue
        
    except Exception as e:
        logger.debug(f"  RSS[{feed_name}]解析失败: {e}")
    
    return news_list

def fetch_all_rss():
    """抓取所有RSS源"""
    logger.info("抓取RSS订阅源...")
    all_news = []
    for url, name in RSS_FEEDS:
        news = fetch_rss_feed(url, name)
        all_news.extend(news)
        logger.info(f"  RSS[{name}]: {len(news)}条")
        time.sleep(1)
    return all_news

# ========== 数据源 6: Twitter/X ==========
class FetchNewsFromTwitter:
    """Twitter/X 热搜采集 - 无法访问时静默跳过"""
    
    def __init__(self):
        self.name = 'Twitter'
        self.platform = 'twitter'
    
    def fetch(self):
        """抓取 Twitter/X 热搜榜"""
        logger.info("抓取 Twitter/X 热搜...")
        try:
            # Twitter/X 在国内无法直接访问，尝试通过公开API获取
            # 由于网络限制，优先尝试Nitter实例（开源推特前端）或其他公开渠道
            proxies = {
                'http': os.environ.get('HTTP_PROXY', ''),
                'https': os.environ.get('HTTPS_PROXY', '')
            }
            # 过滤空代理
            proxies = {k: v for k, v in proxies.items() if v}
            
            # 尝试获取 Twitter 热搜
            # 方式1: 公共 trending API（如果有的话）
            # 方式2: 通过 RSS 或公开聚合站获取
            news_list = []
            
            # 尝试通过替代方案获取
            try:
                # 尝试抓取 nitter 实例的热搜（如果可用）
                r = requests.get(
                    'https://nitter.net/explore',
                    headers={
                        **HEADERS,
                        'Accept': 'text/html,application/xhtml+xml',
                    },
                    timeout=5,
                    proxies=proxies if proxies else None
                )
                if r.status_code != 200:
                    raise Exception(f"HTTP {r.status_code}")
            except Exception as e:
                # 网络不通或无法访问，静默跳过
                logger.debug(f"  Twitter/X 无法访问（预期行为）: {e}")
                return []
            
            # 如果能访问，解析热搜内容
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            trending = soup.select('.trending-item')[:10]
            
            for i, item in enumerate(trending):
                try:
                    title_elem = item.select_one('.trend-name') or item.select_one('a')
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    if not title:
                        continue
                    
                    event_type = detect_event_type(title, '')
                    stock_codes = extract_stock_codes(title)
                    
                    news_list.append({
                        'title': f"🐦 {title}",
                        'content': f"Twitter/X 热搜第{i+1}名",
                        'source': 'Twitter/X',
                        'source_platform': 'twitter',
                        'published_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'url': f'https://twitter.com/search?q={title}',
                        'category': '社交媒体',
                        'author': '',
                        'keywords': ','.join(stock_codes),
                        'event_type': event_type,
                    })
                except Exception:
                    continue
            
            logger.info(f"  Twitter/X: 获取{len(news_list)}条")
            return news_list
            
        except Exception as e:
            # 任何异常都静默跳过，不记录错误
            logger.debug(f"  Twitter/X 抓取跳过: {e}")
            return []


# ========== 数据源 7: 抖音/小红书 ==========
class FetchNewsFromDouyin:
    """抖音/小红书 热搜采集"""
    
    def __init__(self):
        self.name = '抖音/小红书'
        self.platform = 'douyin'
    
    def _fetch_douyin_hot(self):
        """抓取抖音热搜"""
        news_list = []
        try:
            # 抖音热搜榜公开接口
            r = requests.get(
                'https://www.douyin.com/aweme/v1/web/general/search/single/',
                params={
                    'search_channel': 'aweme_user_web',
                    'keyword': '热搜',
                    'type': '1',
                    'count': '10',
                },
                headers={
                    **HEADERS,
                    'Referer': 'https://www.douyin.com/',
                    'Host': 'www.douyin.com',
                },
                timeout=10
            )
            
            if r.status_code != 200:
                return news_list
            
            # 尝试解析响应
            try:
                d = r.json()
                items = d.get('data', []) if isinstance(d.get('data'), list) else []
            except:
                # 如果响应不是JSON，尝试其他方式获取热搜
                items = []
            
            # 如果上述方式获取不到，尝试备用方案
            if not items:
                # 抖音话题榜备用
                try:
                    r2 = requests.get(
                        'https://www.douyin.com/aweme/v1/web/hot/search/list/',
                        headers={
                            **HEADERS,
                            'Referer': 'https://www.douyin.com/',
                        },
                        timeout=10
                    )
                    if r2.status_code == 200:
                        d2 = r2.json()
                        word_list = d2.get('data', {}).get('word_list', []) if isinstance(d2.get('data'), dict) else []
                        items = [{'word': w.get('word', ''), 'hot_value': w.get('hot_value', 0)} for w in word_list[:10]]
                except:
                    pass
            
            for i, item in enumerate(items[:10]):
                try:
                    word = item.get('word', item.get('title', '')) if isinstance(item, dict) else str(item)
                    if not word:
                        continue
                    
                    hot_value = item.get('hot_value', 0) if isinstance(item, dict) else 0
                    event_type = detect_event_type(word, '')
                    stock_codes = extract_stock_codes(word)
                    
                    news_list.append({
                        'title': f"📱 {word}",
                        'content': f"抖音热搜第{i+1}名 热度:{hot_value}",
                        'source': '抖音热搜',
                        'source_platform': 'douyin',
                        'published_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'url': f'https://www.douyin.com/search/{word}',
                        'category': '短视频',
                        'author': '',
                        'keywords': ','.join(stock_codes),
                        'event_type': event_type,
                    })
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"  抖音热搜抓取失败: {e}")
        
        return news_list
    
    def _fetch_xiaohongshu_hot(self):
        """抓取小红书热搜"""
        news_list = []
        try:
            # 小红书公开搜索接口
            r = requests.get(
                'https://edith.xiaohongshu.com/api/sns/web/v1/search_hottopic',
                params={'count': 10, 'page': 1},
                headers={
                    **HEADERS,
                    'Referer': 'https://www.xiaohongshu.com/',
                    'Host': 'edith.xiaohongshu.com',
                },
                timeout=10
            )
            
            if r.status_code != 200:
                return news_list
            
            try:
                d = r.json()
                items = d.get('data', {}).get('items', []) if isinstance(d.get('data'), dict) else []
            except:
                items = []
            
            for i, item in enumerate(items[:10]):
                try:
                    word = item.get('word', item.get('title', '')) if isinstance(item, dict) else str(item)
                    if not word:
                        continue
                    
                    event_type = detect_event_type(word, '')
                    stock_codes = extract_stock_codes(word)
                    
                    news_list.append({
                        'title': f"📕 {word}",
                        'content': f"小红书热门话题第{i+1}名",
                        'source': '小红书',
                        'source_platform': 'xiaohongshu',
                        'published_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'url': f'https://www.xiaohongshu.com/search_result?keyword={word}',
                        'category': '社交',
                        'author': '',
                        'keywords': ','.join(stock_codes),
                        'event_type': event_type,
                    })
                except Exception:
                    continue
                    
        except Exception as e:
            logger.debug(f"  小红书热搜抓取失败: {e}")
        
        return news_list
    
    def fetch(self):
        """抓取抖音和小红书热搜"""
        logger.info("抓取 抖音/小红书 热搜...")
        all_news = []
        
        douyin_news = self._fetch_douyin_hot()
        all_news.extend(douyin_news)
        logger.info(f"  抖音热搜: 获取{len(douyin_news)}条")
        time.sleep(1)
        
        xhs_news = self._fetch_xiaohongshu_hot()
        all_news.extend(xhs_news)
        logger.info(f"  小红书: 获取{len(xhs_news)}条")
        
        return all_news


# ========== 事件类型判断 ==========
BLACK_SWAN_KEYWORDS = [
    '制裁', '断供', '违约', '黑天鹅', '战争', '恐袭', '爆炸', '恐怖袭击',
    '军事行动', '核', '生化', '紧急状态', '戒严', '封锁', '撤侨'
]

GRAY_RHINO_KEYWORDS = [
    '债务危机', '产能过剩', '政策收紧', '人口老龄化', '美元加息',
    '通胀', '缩表', '贸易战', '脱钩', '去全球化', '灰犀牛'
]

MACRO_KEYWORDS = [
    '美联储', '加息', '降息', 'QE', 'CPI', 'PPI', 'GDP', '非农',
    '央行', '货币', '财政', '刺激', '衰退', '滞胀'
]

SECTOR_KEYWORDS = [
    '光伏', '锂电池', '新能源车', '半导体', '芯片', '房地产',
    '白酒', '银行', '券商', '保险'
]

def detect_event_type(title, content):
    """AI-free 关键词判断事件类型"""
    text = (title + ' ' + (content or '')).lower()
    
    # 黑天鹅优先
    if any(kw in text for kw in BLACK_SWAN_KEYWORDS):
        return 'black_swan'
    # 灰犀牛
    if any(kw in text for kw in GRAY_RHINO_KEYWORDS):
        return 'gray_rhinoceros'
    # 宏观
    if any(kw in text for kw in MACRO_KEYWORDS):
        return 'macro_risk'
    # 行业
    if any(kw in text for kw in SECTOR_KEYWORDS):
        return 'sector_risk'
    
    return 'normal'

# ========== 数据源 8: Bilibili 博主观点 (摘要+外链合规模型) ==========
BILIBILI_BLOGGER_VIDEOS = [
    # 知名财经博主 - 预置高质量视频列表
    # 格式: (bvid, blogger_name, category, tags)
    # === 价值投资 ===
    ('BV1gtFazsEbT', '但斌', '价值投资', '白酒,AI,牛市,长期持有'),
    ('BV18HXDBREyr', '但斌', '价值投资', '白酒,AI,2026'),
    ('BV1peqQBrEKi', '但斌', '价值投资', '2026,如何投资'),
    ('BV11SqEBpEqL', '但斌', '价值投资', '投资哲学,巴菲特'),
    # === 宏观策略 ===
    ('BV13inozmEem', '洪灏', '宏观策略', 'A股,港股,赚钱,全球配置'),
    ('BV1KVcjzkEYU', '洪灏', '宏观策略', '黄金,白银,贵金属'),
    ('BV1heApzuEtG', '张瑜', '宏观策略', '二季度,宏观,赛道'),
    ('BV1AkzfBTErM', '邢自强', '宏观策略', '大摩,2026,全球经济'),
    ('BV1ZoQtBBEHx', '经济学家', '宏观策略', '滞胀,周期,中国经济'),
    # === 行业研究 ===
    ('BV1UXqfBrEBy', '全球财富论坛', '行业论坛', '中国资产,重估,全球'),
    ('BV1iDXzBKE7D', '行业专家', '商业航天', '商业航天,订单,投资主线'),
    ('BV16JQnBQEkT', '行业专家', '半导体', '算力芯片,国产替代'),
    ('BV1BkdWBTEbT', '行业专家', '光通信', '光模块,OCS,CPO'),
    ('BV1csw1zDEWK', '行业专家', '储能电网', '储能,电网设备,投资主线'),
    ('BV11NzMBbEgf', '行业专家', '光模块', '1.6T,硅光,光通信'),
]

def _extract_bilibili_summary(bvid):
    """用 Jina.ai 提取 Bilibili 视频页内容摘要（摘要+外链合规模型）"""
    try:
        url = f'https://www.bilibili.com/video/{bvid}'
        r = requests.get(
            f'https://r.jina.ai/{url}',
            headers={'Accept': 'text/plain'},
            timeout=12
        )
        if r.status_code != 200 or len(r.text) < 50:
            return None
        
        text = r.text
        
        # 提取标题
        title_match = re.search(r'Title:\s*(.+?)(?:\n|$)', text)
        title = title_match.group(1).strip() if title_match else None
        
        # 提取视频描述/正文（去掉推荐列表，只留主要描述）
        # Jina 返回格式：标题行 + URL行 + Markdown Content + 推荐视频列表
        content_start = text.find('Markdown Content:')
        content_end = text.find('\n\n*   [首页]', content_start) if content_start > 0 else -1
        
        if content_start > 0 and content_end > content_start:
            body = text[content_start:content_end]
            # 清理 Markdown 图片和链接，只保留文字描述
            body = re.sub(r'!\[.*?\]\(.*?\)', '', body)
            body = re.sub(r'\[([^\]]+)\]\(https?://[^\)]+\)', r'\1', body)
            body = re.sub(r'\*+\s*', '', body)
            body = re.sub(r'#+\s*', '', body)
            body = body.replace('Markdown Content:', '').strip()
            # 取前300字作为摘要
            summary = body[:300].strip()
        else:
            summary = ''
        
        return title, summary
        
    except Exception as e:
        logger.debug(f"  Jina提取 {bvid} 失败: {e}")
        return None

def fetch_bilibili_blogger():
    """抓取 Bilibili 财经博主观点（摘要+外链合规模型）"""
    logger.info("抓取 Bilibili 博主观点...")
    news_list = []
    
    for bvid, blogger, category, tags in BILIBILI_BLOGGER_VIDEOS:
        try:
            result = _extract_bilibili_summary(bvid)
            if not result:
                continue
            
            title, summary = result
            if not title:
                continue
            
            # 过滤失效视频
            if any(x in title for x in ['视频去哪了', '验证码', '访问过于频繁', '账号异常']):
                logger.debug(f"  跳过失效视频 {bvid}: {title[:40]}")
                continue
            
            event_type = detect_event_type(title, summary)
            url = f'https://www.bilibili.com/video/{bvid}'
            
            news_list.append({
                'title': title,
                'content': summary,
                'source': f'哔哩哔哩-{blogger}',
                'source_platform': 'bilibili',
                'published_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'url': url,
                'category': category,
                'author': '',
                'keywords': tags,
                'event_type': event_type,
                'blogger_source': blogger,
            })
            logger.info(f"  ✓ {blogger}: {title[:40]}...")
            time.sleep(1)  # 避免频率过高
            
        except Exception as e:
            logger.debug(f"  {bvid} 处理失败: {e}")
            continue
    
    logger.info(f"  Bilibili 博主: 获取{len(news_list)}条")
    return news_list


# ========== 主函数 ==========
def main():
    logger.info("=" * 50)
    logger.info(f"MiniRock 统一新闻采集 v1.0 | {datetime.now()}")
    logger.info("=" * 50)
    
    # 初始化数据库
    init_db()
    
    total_saved = 0
    
    # Step 1: 财联社 (主力)
    news_cls = fetch_cls_news()
    saved_cls = save_to_db(news_cls, 'cls')
    total_saved += saved_cls
    logger.info(f"  → 财联社写入: {saved_cls}条")
    time.sleep(2)
    
    # Step 2: 同花顺 (补充)
    news_ths = fetch_ths_news()
    saved_ths = save_to_db(news_ths, 'ths')
    total_saved += saved_ths
    logger.info(f"  → 同花顺写入: {saved_ths}条")
    time.sleep(2)
    
    # Step 3: Tushare (兜底)
    news_tushare = fetch_tushare_news()
    saved_tushare = save_to_db(news_tushare, 'tushare')
    total_saved += saved_tushare
    logger.info(f"  → Tushare写入: {saved_tushare}条")
    time.sleep(2)
    
    # Step 4: 微博热搜
    news_weibo = fetch_weibo_hot()
    saved_weibo = save_to_db(news_weibo, 'weibo')
    total_saved += saved_weibo
    logger.info(f"  → 微博热搜写入: {saved_weibo}条")
    time.sleep(2)
    
    # Step 5: RSS订阅
    news_rss = fetch_all_rss()
    saved_rss = save_to_db(news_rss, 'rss')
    total_saved += saved_rss
    logger.info(f"  → RSS写入: {saved_rss}条")
    time.sleep(2)

    # Step 6: Twitter/X
    news_twitter = FetchNewsFromTwitter().fetch()
    saved_twitter = save_to_db(news_twitter, 'twitter')
    total_saved += saved_twitter
    logger.info(f"  → Twitter/X写入: {saved_twitter}条")
    time.sleep(2)

    # Step 7: 抖音/小红书
    news_douyin = FetchNewsFromDouyin().fetch()
    saved_douyin = save_to_db(news_douyin, 'douyin')
    total_saved += saved_douyin
    logger.info(f"  → 抖音/小红书写入: {saved_douyin}条")
    time.sleep(2)

    # Step 8: Bilibili 博主观点（摘要+外链合规模型）
    news_bilibili = fetch_bilibili_blogger()
    saved_bilibili = save_to_db(news_bilibili, 'bilibili')
    total_saved += saved_bilibili
    logger.info(f"  → Bilibili博主观点写入: {saved_bilibili}条")

    logger.info(f"✅ 总写入: {total_saved}条")
    
    # 统计黑天鹅/灰犀牛
    conn = get_conn()
    counts = conn.execute("""
        SELECT event_type, COUNT(*) as cnt 
        FROM news 
        WHERE event_type != 'normal' 
        GROUP BY event_type
    """).fetchall()
    for et, cnt in counts:
        logger.info(f"  [{et}]: {cnt}条")
    conn.close()
    
    return total_saved

if __name__ == '__main__':
    main()
