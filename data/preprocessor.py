"""
AI 股神争霸赛 - 数据预处理模块
获取市场数据并生成自然语言摘要
"""

import asyncio
import asyncpg
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class MarketData:
    """市场数据结构"""
    date: str
    index_data: Dict[str, Any]
    stock_quotes: List[Dict]
    fund_flow: List[Dict]
    dragon_tiger: List[Dict]
    hot_sectors: List[Dict]
    market_summary: str

class DataPreprocessor:
    """数据预处理器"""
    
    def __init__(self, db_url: str = "postgresql://minirock:minirock123@localhost:5432/minirock"):
        self.db_url = db_url
        self.db = None
    
    async def connect(self):
        """连接数据库"""
        if not self.db:
            self.db = await asyncpg.connect(self.db_url)
            logger.info("数据库连接成功")
    
    async def close(self):
        """关闭数据库连接"""
        if self.db:
            await self.db.close()
            self.db = None
    
    async def prepare_market_data(self, date: Optional[str] = None) -> MarketData:
        """
        准备市场数据，供 AI 决策使用
        
        1. 获取原始数据
        2. 计算技术指标
        3. 生成自然语言描述
        4. 构建结构化输入
        """
        await self.connect()
        
        if not date:
            # 使用数据库最新日期格式 YYYYMMDD
            date = datetime.now().strftime("%Y%m%d")
        else:
            # 转换 YYYY-MM-DD 到 YYYYMMDD
            date = date.replace("-", "")
        
        logger.info(f"准备市场数据: {date}")
        
        # 1. 获取各类数据
        index_data = await self._fetch_index_data(date)
        stock_quotes = await self._fetch_stock_quotes(date)
        fund_flow = await self._fetch_fund_flow(date)
        dragon_tiger = await self._fetch_dragon_tiger(date)
        hot_sectors = await self._identify_hot_sectors(stock_quotes)
        
        # 2. 生成自然语言摘要
        # 转换回 YYYY-MM-DD 格式用于显示
        display_date = f"{date[:4]}-{date[4:6]}-{date[6:]}"
        market_summary = self._generate_summary(
            display_date, index_data, stock_quotes, hot_sectors
        )
        
        return MarketData(
            date=display_date,
            index_data=index_data,
            stock_quotes=stock_quotes,
            fund_flow=fund_flow,
            dragon_tiger=dragon_tiger,
            hot_sectors=hot_sectors,
            market_summary=market_summary
        )
    
    async def get_market_data(self, date: Optional[str] = None) -> MarketData:
        """获取市场数据（供外部调用）"""
        return await self.prepare_market_data(date)
    
    async def _fetch_index_data(self, date: str) -> Dict[str, Any]:
        """获取大盘指数数据"""
        query = """
        SELECT ts_code, name, close, open, high, low, 
               prev_close, change, pct_chg, volume, amount
        FROM index_cache
        WHERE trade_date = $1
        ORDER BY ts_code
        """
        
        rows = await self.db.fetch(query, int(date))
        
        index_data = {}
        for row in rows:
            code = row['ts_code']
            index_data[code] = {
                'name': row['name'],
                'close': float(row['close']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'pre_close': float(row['prev_close']),
                'change': float(row['change']) if row['change'] else 0,
                'pct_chg': float(row['pct_chg']),
                'volume': int(row['volume']),
                'amount': float(row['amount'])
            }
        
        return index_data
    
    async def _fetch_stock_quotes(self, date: str, limit: int = 200) -> List[Dict]:
        """获取个股行情数据（涨幅前200）"""
        query = """
        SELECT 
            symbol, name, market,
            close, open, high, low, prev_close,
            change, pct_chg, volume, amount
        FROM stock_cache
        WHERE pct_chg BETWEEN -5.0 AND 10.0
          AND (market IN ('A股', '港股') OR market IN ('SZ', 'SH'))
        ORDER BY pct_chg DESC
        LIMIT $1
        """
        
        rows = await self.db.fetch(query, limit)
        
        stocks = []
        for row in rows:
            stocks.append({
                'symbol': row['symbol'],
                'name': row['name'],
                'industry': row['market'],
                'close': float(row['close']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'pre_close': float(row['prev_close']) if row['prev_close'] else float(row['close']),
                'change': float(row['change']) if row['change'] else 0,
                'pct_chg': float(row['pct_chg']),
                'volume': int(row['volume']),
                'amount': float(row['amount']),
                'turnover_rate': 0  # stock_cache 没有换手率字段
            })
        
        return stocks
    
    async def _fetch_fund_flow(self, date: str, limit: int = 50) -> List[Dict]:
        """获取资金流向数据"""
        query = """
        SELECT 
            symbol, name,
            pct_chg, close,
            COALESCE(amount, 0) as amount
        FROM stock_cache
        WHERE pct_chg > 0
        ORDER BY amount DESC
        LIMIT $1
        """
        
        rows = await self.db.fetch(query, limit)
        
        fund_flow = []
        for row in rows:
            fund_flow.append({
                'symbol': row['symbol'],
                'name': row['name'],
                'pct_chg': float(row['pct_chg']),
                'close': float(row['close']),
                'amount': float(row['amount'])
            })
        
        return fund_flow
    
    async def _fetch_dragon_tiger(self, date: str) -> List[Dict]:
        """获取龙虎榜数据"""
        # stock_cache 中没有龙虎榜数据，返回空列表
        return []
    
    async def _identify_hot_sectors(self, stocks: List[Dict], top_n: int = 5) -> List[Dict]:
        """识别热点板块"""
        from collections import defaultdict
        
        sector_stocks = defaultdict(list)
        for stock in stocks:
            if stock['industry']:
                sector_stocks[stock['industry']].append(stock)
        
        sectors = []
        for industry, stocks_list in sector_stocks.items():
            if len(stocks_list) >= 3:  # 至少3只股票
                avg_chg = sum(s['pct_chg'] for s in stocks_list) / len(stocks_list)
                sectors.append({
                    'name': industry,
                    'stock_count': len(stocks_list),
                    'avg_change': avg_chg,
                    'top_stocks': [s['name'] for s in stocks_list[:3]]
                })
        
        # 按平均涨幅排序
        sectors.sort(key=lambda x: x['avg_change'], reverse=True)
        return sectors[:top_n]
    
    def _generate_summary(
        self, 
        date: str, 
        index_data: Dict, 
        stocks: List[Dict],
        hot_sectors: List[Dict]
    ) -> str:
        """生成市场自然语言摘要"""
        
        summary_parts = []
        
        # 1. 大盘概况
        sh_index = index_data.get('sh000001', {})
        if sh_index:
            change_word = "上涨" if sh_index['change'] >= 0 else "下跌"
            summary_parts.append(
                f"上证指数{change_word}{abs(sh_index['pct_chg']):.2f}%，"
                f"收于{sh_index['close']:.2f}点，"
                f"成交额{sh_index['amount']/1e8:.0f}亿元。"
            )
        
        sz_index = index_data.get('sz399001', {})
        if sz_index:
            change_word = "上涨" if sz_index['change'] >= 0 else "下跌"
            summary_parts.append(
                f"深证成指{change_word}{abs(sz_index['pct_chg']):.2f}%。"
            )
        
        # 2. 涨跌分布
        up_count = len([s for s in stocks if s['pct_chg'] > 0])
        down_count = len([s for s in stocks if s['pct_chg'] < 0])
        limit_up = len([s for s in stocks if s['pct_chg'] >= 9.5])
        
        summary_parts.append(
            f"全市场{up_count}只股票上涨，{down_count}只下跌，"
            f"涨停{limit_up}只。"
        )
        
        # 3. 热点板块
        if hot_sectors:
            sector_names = [s['name'] for s in hot_sectors[:3]]
            summary_parts.append(
                f"热点板块：{', '.join(sector_names)}。"
            )
        
        # 4. 领涨个股
        top_gainers = sorted(stocks, key=lambda x: x['pct_chg'], reverse=True)[:3]
        if top_gainers:
            gainer_strs = [
                f"{s['name']}({s['pct_chg']:.1f}%)" 
                for s in top_gainers
            ]
            summary_parts.append(
                f"领涨个股：{', '.join(gainer_strs)}。"
            )
        
        return " ".join(summary_parts)
    
    def format_for_llm(self, market_data: MarketData, character_id: str = None) -> str:
        """格式化为LLM可读的文本"""
        
        lines = [
            f"=== 市场数据 ({market_data.date}) ===",
            "",
            "【大盘指数】",
        ]
        
        for code, data in market_data.index_data.items():
            lines.append(
                f"  {data['name']}: {data['close']:.2f} "
                f"({data['pct_chg']:+.2f}%)"
            )
        
        lines.extend([
            "",
            "【市场概况】",
            f"  {market_data.market_summary}",
            "",
            "【热点板块】",
        ])
        
        for sector in market_data.hot_sectors[:5]:
            lines.append(
                f"  {sector['name']}: 均涨幅{sector['avg_change']:.2f}%，"
                f"代表股: {', '.join(sector['top_stocks'])}"
            )
        
        lines.extend([
            "",
            "【候选股票池】",
        ])
        
        # 根据角色筛选候选股
        candidates = self._filter_candidates(market_data, character_id)
        for stock in candidates[:10]:
            lines.append(
                f"  {stock['symbol']} {stock['name']} | "
                f"涨幅{stock['pct_chg']:.2f}% | "
                f"换手{stock['turnover_rate']:.1f}% | "
                f"行业: {stock['industry']}"
            )
        
        return "\n".join(lines)
    
    def _filter_candidates(
        self, 
        market_data: MarketData, 
        character_id: str
    ) -> List[Dict]:
        """根据角色风格筛选候选股票"""
        
        candidates = market_data.stock_quotes
        
        if character_id == "scalper_fairy":
            # 短线精灵：偏好涨停股、高换手
            candidates = [
                s for s in candidates 
                if s['pct_chg'] >= 9.0 and s['turnover_rate'] >= 5
            ]
        elif character_id == "quant_queen":
            # 量化女王：偏好波动适中的
            candidates = [
                s for s in candidates 
                if 2 <= s['pct_chg'] <= 7 and s['turnover_rate'] >= 3
            ]
        elif character_id == "value_veteran":
            # 价值老炮：偏好涨幅适中、有基本面的
            candidates = [
                s for s in candidates 
                if 2 <= s['pct_chg'] <= 5
            ]
        
        return candidates


# 测试代码
async def test():
    """测试数据预处理"""
    preprocessor = DataPreprocessor()
    
    try:
        # 获取最新交易日数据
        market_data = await preprocessor.prepare_market_data()
        
        print(f"日期: {market_data.date}")
        print(f"\n市场摘要:\n{market_data.market_summary}")
        print(f"\n热点板块: {len(market_data.hot_sectors)}个")
        print(f"候选股票: {len(market_data.stock_quotes)}只")
        print(f"龙虎榜: {len(market_data.dragon_tiger)}条")
        
        # 格式化输出
        print("\n" + "="*50)
        print(preprocessor.format_for_llm(market_data, "trend_chaser"))
        
    finally:
        await preprocessor.close()

if __name__ == "__main__":
    asyncio.run(test())
