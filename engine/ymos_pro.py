"""
AI 股神争霸赛 - YMOS 专业分析引擎
整合腾讯证券实时数据 + YMOS分析
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')
sys.path.insert(0, '/var/www/familystock/api')

from data.realtime import get_quote, get_quotes, TencentRealTime
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class YMOSProAnalyzer:
    """YMOS专业分析器 - 整合实时数据"""

    def __init__(self):
        self.realtime = TencentRealTime()

    async def analyze_stock(self, symbol: str, name: str = "") -> dict:
        """
        使用实时数据分析股票
        优先从 PostgreSQL 缓存获取,失败则使用实时 API
        """
        # 1. 优先从 PostgreSQL 缓存获取
        quote = await self._get_pg_cache(symbol)

        # 2. 如果 PostgreSQL 没有,尝试实时 API
        if not quote or quote.get('price', 0) == 0:
            quote = await get_quote(symbol)

        if not quote or quote.get('price', 0) == 0:
            return {"error": f"无法获取{symbol}的数据"}

        # 3. 基于数据计算 technical/fund/valuation
        current_price = quote.get('price', 0)
        pct_chg = quote.get('pct_chg', 0)
        volume = quote.get('volume', 0)
        amount = quote.get('amount', 0)
        high = quote.get('high', 0)
        low = quote.get('low', 0)
        open_price = quote.get('open', 0)

        # 计算技术指标评分 (0-100)
        technical_score = self._calculate_technical_score(
            current_price, open_price, high, low, pct_chg, volume
        )

        # 计算资金评分 (基于成交额和涨跌)
        fund_score = self._calculate_fund_score(amount, pct_chg)

        # 计算估值评分
        valuation_score = self._calculate_valuation_score(
            current_price, high, low, open_price
        )

        # 计算新闻情感评分（Phase 4.2: 新闻×评分打通）
        news_sentiment_score = await self._calculate_news_sentiment_score(name or symbol)

        # 3. 从MiniRock API获取YMOS分析
        try:
            from app.services.ymos_brain import analyze_stock_brain

            result = await analyze_stock_brain(
                symbol=symbol,
                name=name or quote.get('name', ''),
                current_price=current_price,
                profit_percent=pct_chg,
                user_level="vip",
                technical={"score": technical_score, "trend": {"description": "上涨" if pct_chg > 0 else "下跌", "direction": "up" if pct_chg > 0 else "down"}},
                fund={"score": fund_score, "inflow": amount, "main_force": "流入" if pct_chg > 0 else "流出"},
                valuation={"score": valuation_score, "pe": 15, "pb": 2},
                use_cache=False
            )

            # 添加YMOS评分到结果
            base_score = result.get('judgement', {}).get('score', 50)
            # 四维融合: 技术(25%) + 资金(25%) + 估值(20%) + 新闻情感(30%)
            final_score = self._blend_final_score(technical_score, fund_score, valuation_score, news_sentiment_score, base_score)
            result['ymos_score'] = final_score
            result['news_sentiment_score'] = news_sentiment_score
            result['recommendation'] = result.get('judgement', {}).get('action', 'HOLD')
            result['sentiment'] = result.get('judgement', {}).get('rating', 'neutral')

            # 4. 整合实时数据
            result['realtime'] = {
                'price': quote.get('price'),
                'prev_close': quote.get('prev_close'),
                'open': quote.get('open'),
                'high': quote.get('high'),
                'low': quote.get('low'),
                'change': quote.get('change'),
                'pct_chg': quote.get('pct_chg'),
                'volume': quote.get('volume'),
                'amount': quote.get('amount'),
                'time': quote.get('time'),
                'update_time': quote.get('update_time'),
            }

            return result

        except Exception as e:
            # MiniRock API 不可用时的兜底路径
            logger.error(f"YMOS分析失败: {e}")
            # 返回简化版结果（含新闻情感）
            final_score = self._blend_final_score(
                technical_score, fund_score, valuation_score, news_sentiment_score
            )
            return {
                "symbol": symbol,
                "name": name or quote.get('name', symbol),
                "current_price": current_price,
                "pct_chg": pct_chg,
                "ymos_score": final_score,
                "recommendation": "BUY" if final_score > 65 else "SELL" if final_score < 40 else "HOLD",
                "sentiment": "bullish" if pct_chg > 1 else "bearish" if pct_chg < -1 else "neutral",
                "realtime": quote,
                "news_sentiment_score": news_sentiment_score,
                "error": str(e)
            }

    def _calculate_technical_score(self, price, open_p, high, low, pct_chg, volume) -> int:
        """计算技术面评分"""
        score = 50  # 基础分

        # 涨跌因素
        if pct_chg > 5:
            score += 20
        elif pct_chg > 2:
            score += 10
        elif pct_chg < -5:
            score -= 20
        elif pct_chg < -2:
            score -= 10

        # 价格位置因素
        if high > 0 and low > 0:
            position = (price - low) / (high - low) if high != low else 0.5
            if position > 0.7:
                score += 10
            elif position < 0.3:
                score -= 10

        # 成交量因素
        if volume > 1000000:  # 大于100万手
            score += 5

        return max(0, min(100, score))

    async def _get_pg_cache(self, symbol: str) -> dict:
        """从 PostgreSQL 缓存获取股票数据"""
        try:
            import asyncpg
            
            # 连接 PostgreSQL (使用正确的密码)
            conn = await asyncpg.connect(
                host='localhost',
                database='minirock',
                user='minirock',
                password='minirock123'
            )
            
            # 查询最新缓存数据
            row = await conn.fetchrow(
                """
                SELECT symbol, name, close as price, open, high, low, 
                       prev_close, change, pct_chg, volume, amount, cached_at
                FROM stock_cache 
                WHERE symbol = $1 
                ORDER BY cached_at DESC 
                LIMIT 1
                """,
                symbol.replace('.SZ', '').replace('.SH', '')
            )
            
            await conn.close()
            
            if row:
                return {
                    'symbol': row['symbol'],
                    'name': row['name'],
                    'price': float(row['price']) if row['price'] else 0,
                    'open': float(row['open']) if row['open'] else 0,
                    'high': float(row['high']) if row['high'] else 0,
                    'low': float(row['low']) if row['low'] else 0,
                    'prev_close': float(row['prev_close']) if row['prev_close'] else 0,
                    'change': float(row['change']) if row['change'] else 0,
                    'pct_chg': float(row['pct_chg']) if row['pct_chg'] else 0,
                    'volume': int(row['volume']) if row['volume'] else 0,
                    'amount': float(row['amount']) if row['amount'] else 0,
                    'time': row['cached_at'].strftime('%H:%M:%S') if row['cached_at'] else '',
                    'update_time': row['cached_at'].isoformat() if row['cached_at'] else '',
                }
            return None
        except Exception as e:
            logger.warning(f"PostgreSQL 缓存查询失败: {e}")
            return None

    def _calculate_fund_score(self, amount, pct_chg) -> int:
        """计算资金评分"""
        score = 50

        # 成交额因素
        if amount > 1000000000:  # 大于10亿
            score += 15
        elif amount > 500000000:  # 大于5亿
            score += 10
        elif amount > 100000000:  # 大于1亿
            score += 5

        # 量价配合
        if pct_chg > 3 and amount > 500000000:
            score += 10
        elif pct_chg < -3 and amount > 500000000:
            score -= 10

        return max(0, min(100, score))

    def _calculate_valuation_score(self, price, high, low, open_p) -> int:
        """计算估值评分"""
        score = 50

        # 日内涨幅
        if open_p > 0:
            intraday = (price - open_p) / open_p * 100
            if intraday > 5:
                score += 15
            elif intraday > 2:
                score += 5
            elif intraday < -5:
                score -= 15
            elif intraday < -2:
                score -= 5

        return max(0, min(100, score))

    async def analyze_multiple(self, symbols: list) -> dict:
        """批量分析多只股票"""
        results = {}
        for symbol in symbols:
            results[symbol] = await self.analyze_stock(symbol)
            await asyncio.sleep(0.1)  # 避免请求过快
        return results

    async def get_market_summary(self) -> dict:
        """获取市场摘要(主要指数+热门股票)"""
        # 获取主要指数
        indices = await get_quotes([
            'sh000001',  # 上证
            'sz399001',  # 深证
            'sz399006',  # 创业板
            'hkHSI',     # 恒生
        ])

        # 获取热门股票(模拟)
        hot_stocks = await get_quotes([
            'sh600519',  # 茅台
            'sz000858',  # 五粮液
            'sz000001',  # 平安
            'sh600000',  # 浦发
        ])

        return {
            'indices': indices,
            'hot_stocks': hot_stocks,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

    async def _calculate_news_sentiment_score(self, stock_name: str) -> int:
        """
        Phase 4.2: 根据新闻情感计算评分(0-100)
        优先级: 个股新闻 > 市场整体情绪(降级策略)
        """
        try:
            from engine.info.news_analyzer import NewsSentimentScorer, NewsAnalyzer
            scorer = NewsSentimentScorer()
            result = scorer.score_for_stock(stock_name, hours=48)

            if result["news_count"] >= 3:
                # 有足够个股新闻，用个股情感
                return result["sentiment_score"]

            # 个股新闻不足(<3条)，叠加市场整体情绪作为补充
            analyzer = NewsAnalyzer()
            ctx = await analyzer.get_market_context(hours=48)
            if ctx.get("has_news"):
                market_sentiment = ctx.get("overall_sentiment", "中性")
                # 市场情绪映射: 偏多→60, 略偏多→53, 中性→50, 略偏空→47, 偏空→40
                market_map = {"偏多": 60, "略偏多": 53, "中性": 50, "略偏空": 47, "偏空": 40}
                market_score = market_map.get(market_sentiment, 50)
                # 混合: 60%个股 + 40%市场
                blended = int(result["sentiment_score"] * 0.6 + market_score * 0.4)
                return blended

            return result["sentiment_score"]

        except Exception as e:
            logger.debug(f"新闻情感评分失败: {e}")
            return 50

    def _blend_final_score(
        self,
        technical: int,
        fund: int,
        valuation: int,
        news_sentiment: int,
        base: int = 50
    ) -> int:
        """
        四维融合: 技术(25%) + 资金(25%) + 估值(20%) + 新闻情感(30%)
        如果 news_sentiment = 50(无新闻)，则降权重新分配给前三项
        """
        if news_sentiment == 50:
            # 无新闻时: 技术30% + 资金30% + 估值40%
            return round(technical * 0.30 + fund * 0.30 + valuation * 0.40)
        else:
            # 有新闻时: 四维融合
            return round(
                technical * 0.25 +
                fund * 0.25 +
                valuation * 0.20 +
                news_sentiment * 0.30
            )


# 全局实例
ymos_analyzer = YMOSProAnalyzer()


# 便捷函数
async def analyze_stock_pro(symbol: str, name: str = "") -> dict:
    """专业分析单只股票"""
    return await ymos_analyzer.analyze_stock(symbol, name)

async def get_market_summary() -> dict:
    """获取市场摘要"""
    return await ymos_analyzer.get_market_summary()
