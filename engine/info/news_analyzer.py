"""
信息获取层 - 新闻分析器
从多个数据源获取新闻 → 情感分析 → 注入AI决策
"""

import os
import re
import sqlite3
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger("NewsAnalyzer")

# Tushare path
TUSHARE_BIN = "/var/www/familystock/api/venv/bin/python3"
NEWS_DB_PATH = "/var/www/familystock/api/data/family_stock.db"


@dataclass
class NewsItem:
    """单条新闻"""
    title: str
    content: str
    source: str
    url: str
    published_at: datetime
    sentiment: float = 0.0  # -1 ~ 1
    keywords: List[str] = None
    relevance_score: float = 0.0  # 与市场相关性

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


class NewsFetcher:
    """新闻获取器 - 从现有MySQL数据库读取"""

    MYSQL_CONFIG = {
        'host': 'localhost',
        'user': 'familystock',
        'password': 'Familystock@2026',
        'database': 'familystock',
        'charset': 'utf8mb4'
    }

    def __init__(self):
        pass

    async def fetch_tushare_news(self, hours: int = 24) -> List[NewsItem]:
        """从已有MySQL数据库读取财经新闻（不重复请求Tushare）"""
        import pymysql
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

        try:
            conn = pymysql.connect(**self.MYSQL_CONFIG)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT title, content, source, url, published_at
                FROM news
                WHERE published_at > %s
                ORDER BY published_at DESC
                LIMIT 200
            """, (cutoff,))
            rows = cursor.fetchall()
            cursor.close()
            conn.close()

            results = []
            for row in rows:
                try:
                    pub_time = datetime.strptime(str(row[4]), '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    pub_time = datetime.now()

                results.append(NewsItem(
                    title=str(row[0] or '')[:200],
                    content=str(row[1] or '')[:2000],
                    source=str(row[2] or '新浪财经'),
                    url=str(row[3] or ''),
                    published_at=pub_time
                ))
            logger.info(f"从MySQL读取{len(results)}条新闻")
            return results
        except Exception as e:
            logger.error(f"MySQL读取新闻失败: {e}")
            return []

    async def fetch_eastmoney_news(self, hours: int = 24) -> List[NewsItem]:
        """东方财富新闻（已包含在MySQL中，跳过）"""
        return []

    def _parse_news(self, raw: Dict) -> NewsItem:
        """解析原始新闻数据"""
        dt_str = raw.get("datetime", "")
        try:
            pub_time = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            pub_time = datetime.now()

        return NewsItem(
            title=raw.get("title", raw.get("content", "")[:100]),
            content=raw.get("content", ""),
            source=raw.get("source", "Unknown"),
            url=raw.get("url", ""),
            published_at=pub_time
        )


class SentimentAnalyzer:
    """情感分析器 - 关键词驱动"""

    # 利好关键词（正面情感）
    BULLISH_KEYWORDS = [
        "涨", "上涨", "大涨", "拉升", "突破", "创新高", "利好",
        "业绩增长", "利润增加", "订单爆满", "需求旺盛", "出口增长",
        "政策支持", "科技", "AI", "新能源", "政策利好", "护盘",
        "买入", "增持", "超预期", "景气", "复苏", "牛市"
    ]

    # 利空关键词（负面情感）
    BEARISH_KEYWORDS = [
        "跌", "下跌", "大跌", "暴跌", "利空", "亏损", "业绩下滑",
        "债务危机", "减持", "预警", "暴雷", "造假", "调查",
        "制裁", "禁令", "失信", "破产", "裁员", "违约", "熊市",
        "外资出逃", "恐慌", "割肉", "踩踏", "做空"
    ]

    # 市场情绪关键词
    MARKET_KEYWORDS = [
        "上证", "深证", "创业板", "科创板", "沪指", "深成",
        "A股", "大盘", "指数", "北向资金", "主力资金",
        "股吧", "散户", "庄家", "机构", "外资", "融资", "融券",
        "印花税", "降准", "加息", "缩表", "IPO", "减持", "回购"
    ]

    # 股票代码模式
    STOCK_CODE_PATTERN = re.compile(r"\b\d{6}\.?(SZ|SH|hk)?\b", re.IGNORECASE)

    def analyze(self, news: NewsItem) -> NewsItem:
        """分析单条新闻情感"""
        text = (news.title + news.content).lower()

        # 计算情感分数
        bullish_count = sum(1 for kw in self.BULLISH_KEYWORDS if kw in text)
        bearish_count = sum(1 for kw in self.BEARISH_KEYWORDS if kw in text)

        total = bullish_count + bearish_count
        if total > 0:
            sentiment = (bullish_count - bearish_count) / total
        else:
            sentiment = 0.0

        news.sentiment = max(-1.0, min(1.0, sentiment))

        # 提取关键词
        news.keywords = [
            kw for kw in self.BULLISH_KEYWORDS + self.BEARISH_KEYWORDS
            if kw in text
        ]

        # 计算市场相关性
        market_hits = sum(1 for kw in self.MARKET_KEYWORDS if kw in text)
        news.relevance_score = min(1.0, market_hits / 3)

        # 提取提及的股票代码
        news.stock_codes = self.STOCK_CODE_PATTERN.findall(news.title + news.content)

        return news

    def batch_analyze(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """批量分析"""
        return [self.analyze(n) for n in news_list]


class NewsDB:
    """新闻持久化存储"""

    def __init__(self, db_path: str = NEWS_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT,
                source TEXT,
                url TEXT,
                published_at TEXT,
                sentiment REAL DEFAULT 0,
                keywords TEXT,
                relevance REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_published ON news(published_at)
        """)
        conn.commit()
        conn.close()

    def save(self, news_list: List[NewsItem]) -> int:
        """保存新闻列表，返回新增数量"""
        if not news_list:
            return 0

        conn = sqlite3.connect(self.db_path)
        count = 0
        for n in news_list:
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO news (title, content, source, url, published_at, sentiment, keywords, relevance)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    n.title, n.content, n.source, n.url,
                    n.published_at.strftime("%Y-%m-%d %H:%M:%S"),
                    n.sentiment, ",".join(n.keywords), n.relevance_score
                ))
                count += 1
            except Exception:
                pass
        conn.commit()
        conn.close()
        return count

    def get_recent(self, hours: int = 24, min_relevance: float = 0.3) -> List[NewsItem]:
        """获取最近N小时的相关新闻"""
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT title, content, source, url, published_at, sentiment, keywords, relevance
            FROM news WHERE published_at > ? AND relevance >= ?
            ORDER BY published_at DESC, relevance DESC
            LIMIT 100
        """, (cutoff, min_relevance)).fetchall()
        conn.close()

        results = []
        for r in rows:
            pub_at_str = r[4]
            try:
                pub_at = datetime.strptime(pub_at_str, "%Y-%m-%d %H:%M:%S") if pub_at_str else datetime.now()
            except:
                pub_at = datetime.now()
            sent = r[5]
            try:
                sent = float(sent) if sent is not None else 0.0
            except:
                sent = 0.0
            results.append(NewsItem(
                title=r[0], content=r[1], source=r[2], url=r[3],
                published_at=pub_at,
                sentiment=sent,
                keywords=r[6].split(",") if r[6] else [],
                relevance_score=r[7]
            ))
        return results

    def get_news_for_stock(self, stock_name: str, hours: int = 720, min_relevance: float = 0.0) -> List[NewsItem]:
        """获取与某只股票相关的新闻（默认30天窗口）"""
        import re
        cutoff = (datetime.now() - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S")

        # 股票名称关键词（去掉"股份有限公司"等后缀）
        name_keywords = re.sub(r'有限公司|股份有限公司|A股指数|ETF|\d+', '', stock_name).strip()
        main_kw = name_keywords[:4] if len(name_keywords) >= 4 else name_keywords
        codes = re.findall(r'\d{6}', stock_name)

        conn = sqlite3.connect(self.db_path)
        like_pat = f"%{main_kw}%"

        rows = conn.execute("""
            SELECT title, content, source, url, published_at, sentiment, keywords, relevance
            FROM news
            WHERE published_at > ? AND (title LIKE ? OR content LIKE ?)
            ORDER BY published_at DESC
            LIMIT 30
        """, (cutoff, like_pat, like_pat)).fetchall()

        # 额外匹配股票代码
        if codes:
            code_pat = f"%{codes[0]}%"
            code_rows = conn.execute("""
                SELECT title, content, source, url, published_at, sentiment, keywords, relevance
                FROM news
                WHERE published_at > ? AND (title LIKE ? OR content LIKE ?)
                ORDER BY published_at DESC
                LIMIT 10
            """, (cutoff, code_pat, code_pat)).fetchall()
            seen = {r[0] for r in rows}
            for r in code_rows:
                if r[0] not in seen:
                    rows.append(r)
                    seen.add(r[0])

        conn.close()

        out = []
        for r in rows:
            pub_at_str = r[4]
            try:
                pub_at = datetime.strptime(pub_at_str, "%Y-%m-%d %H:%M:%S") if pub_at_str else datetime.now()
            except:
                pub_at = datetime.now()
            sent = r[5]
            try:
                sent = float(sent) if sent is not None else 0.0
            except:
                sent = 0.0
            out.append(NewsItem(
                title=r[0], content=r[1], source=r[2], url=r[3],
                published_at=pub_at,
                sentiment=sent,
                keywords=r[6].split(",") if r[6] else [],
                relevance_score=r[7]
            ))
        return out


class NewsSentimentScorer:
    """新闻情感评分器 - 将新闻情感转换为0-100的评分，注入算法决策"""

    def score_for_stock(self, stock_name: str, hours: int = 48) -> dict:
        """
        获取某只股票的新闻情感评分
        返回: {
            sentiment_score: int(0-100),  综合情绪评分
            sentiment_label: str,           "利好"/"利空"/"中性"
            news_count: int,               相关新闻数量
            avg_sentiment: float,           平均情感值(-1~1)
            confidence: float,              置信度(0~1)
        }
        """
        db = NewsDB()
        news_list = db.get_news_for_stock(stock_name, hours=hours, min_relevance=0.15)

        if not news_list:
            return {
                "sentiment_score": 50,
                "sentiment_label": "中性",
                "news_count": 0,
                "avg_sentiment": 0.0,
                "confidence": 0.0,
            }

        sentiments = [n.sentiment for n in news_list]
        avg_sentiment = sum(sentiments) / len(sentiments)

        # 情感分数转0-100: -1→0, 0→50, 1→100
        sentiment_score = max(0, min(100, int((avg_sentiment + 1) * 50)))

        if avg_sentiment > 0.15:
            label = "利好"
        elif avg_sentiment < -0.15:
            label = "利空"
        else:
            label = "中性"

        confidence = min(1.0, len(news_list) / 20)

        return {
            "sentiment_score": sentiment_score,
            "sentiment_label": label,
            "news_count": len(news_list),
            "avg_sentiment": round(avg_sentiment, 3),
            "confidence": round(confidence, 2),
        }


class NewsAnalyzer:
    """
    新闻分析器 - AI的信息获取入口
    用法:
        analyzer = NewsAnalyzer()
        context = await analyzer.get_market_context()
        # context 包含最近市场相关新闻 + 情感摘要
    """

    def __init__(self):
        self.fetcher = NewsFetcher()
        self.sentiment = SentimentAnalyzer()
        self.db = NewsDB()

    async def refresh(self, hours: int = 24) -> int:
        """刷新新闻数据（去重 + 情感分析 + 存储）"""
        # 并行获取多个来源
        tushare_task = self.fetcher.fetch_tushare_news(hours)
        eastmoney_task = self.fetcher.fetch_eastmoney_news(hours)

        results = await asyncio.gather(tushare_task, eastmoney_task, return_exceptions=True)

        all_news = []
        for r in results:
            if isinstance(r, Exception):
                logger.error(f"Fetch error: {r}")
                continue
            all_news.extend(r)

        # 去重
        seen = set()
        unique = []
        for n in all_news:
            key = n.title[:50]
            if key and key not in seen:
                seen.add(key)
                unique.append(n)

        # 情感分析
        analyzed = self.sentiment.batch_analyze(unique)

        # 持久化
        count = self.db.save(analyzed)
        logger.info(f"刷新新闻: 获取{len(all_news)}条, 去重{len(unique)}条, 新增{count}条")
        return count

    async def get_market_context(self, hours: int = 24) -> Dict[str, Any]:
        """
        获取市场情绪上下文（供AI决策使用）
        返回结构化字典，注入到AI的LLM prompt中
        """
        news_list = self.db.get_recent(hours)

        if not news_list:
            return {
                "has_news": False,
                "summary": "暂无最新财经新闻",
                "bullish_count": 0,
                "bearish_count": 0,
                "top_news": [],
                "sentiment": "neutral"
            }

        # 统计情感
        bullish = [n for n in news_list if n.sentiment > 0.2]
        bearish = [n for n in news_list if n.sentiment < -0.2]
        neutral = [n for n in news_list if abs(n.sentiment) <= 0.2]

        # 按相关性排序取TOP
        top = sorted(news_list, key=lambda x: x.relevance_score, reverse=True)[:5]

        # 整体情绪判断
        if len(bullish) > len(bearish) * 1.5:
            overall = "偏多"
        elif len(bearish) > len(bullish) * 1.5:
            overall = "偏空"
        elif len(bullish) > len(bearish):
            overall = "略偏多"
        elif len(bearish) > len(bullish):
            overall = "略偏空"
        else:
            overall = "中性"

        return {
            "has_news": True,
            "summary": f"最近{hours}小时共{len(news_list)}条财经新闻，整体情绪{overall}",
            "total_count": len(news_list),
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "neutral_count": len(neutral),
            "overall_sentiment": overall,
            "top_news": [
                {
                    "title": n.title[:80],
                    "sentiment": "利好" if n.sentiment > 0.2 else ("利空" if n.sentiment < -0.2 else "中性"),
                    "sentiment_score": round(n.sentiment, 2),
                    "keywords": n.keywords[:5],
                    "source": n.source,
                    "time": n.published_at.strftime("%H:%M")
                }
                for n in top
            ],
            "recent_highlight": self._extract_highlights(news_list)
        }

    def _extract_highlights(self, news_list: List[NewsItem]) -> str:
        """提取关键信息摘要"""
        lines = []
        for n in sorted(news_list, key=lambda x: abs(x.sentiment), reverse=True)[:3]:
            s = "利好" if n.sentiment > 0.2 else ("利空" if n.sentiment < -0.2 else "中性")
            lines.append(f"[{n.published_at.strftime('%H:%M')}]{n.title[:60]}（{s}）")
        return "\n".join(lines)


# 独立运行测试
if __name__ == "__main__":
    import asyncio

    async def test():
        analyzer = NewsAnalyzer()
        print("刷新新闻数据...")
        count = await analyzer.refresh(hours=24)
        print(f"新增 {count} 条")

        print("\n获取市场情绪上下文...")
        ctx = await analyzer.get_market_context(hours=24)
        print(f"整体情绪: {ctx['overall_sentiment']}")
        print(f"利好/利空/中性: {ctx['bullish_count']}/{ctx['bearish_count']}/{ctx['neutral_count']}")
        print("\nTOP新闻:")
        for n in ctx["top_news"]:
            print(f"  [{n['time']}][{n['sentiment']}] {n['title']}")

    asyncio.run(test())
