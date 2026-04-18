"""
AI 股神争霸赛 - 持仓价格更新器
使用腾讯证券实时数据更新AI持仓股票价格
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from data.realtime import get_quotes
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PortfolioPriceUpdater:
    """持仓价格更新器"""
    
    # 股票代码前缀映射
    PREFIX_MAP = {
        '0': 'sz',  # 深圳主板
        '3': 'sz',  # 创业板
        '6': 'sh',  # 上海主板
        '8': 'bj',  # 北京
        '4': 'bj',   # 北京
    }
    
    @classmethod
    def convert_symbol(cls, symbol: str) -> str:
        """转换代码格式为腾讯格式"""
        symbol = symbol.strip()
        
        # 已经是腾讯格式
        if symbol.startswith(('sh', 'sz', 'hk', 'us', 'bj')):
            return symbol
        
        # 转换纯数字代码
        if len(symbol) == 6 and symbol.isdigit():
            prefix = cls.PREFIX_MAP.get(symbol[0], 'sz')
            return f"{prefix}{symbol}"
        
        return symbol
    
    @classmethod
    async def update_portfolio_prices(cls, holdings: list) -> list:
        """
        更新持仓股票价格
        
        Args:
            holdings: 持仓列表 [{symbol: '000001', quantity: 100, ...}, ...]
        
        Returns:
            更新后的持仓列表
        """
        if not holdings:
            return []
        
        # 转换代码格式
        symbols = [cls.convert_symbol(h.get('symbol', '')) for h in holdings]
        symbols = [s for s in symbols if s]
        
        if not symbols:
            return holdings
        
        # 获取实时行情
        quotes = await get_quotes(symbols)
        
        # 更新持仓数据
        updated_count = 0
        for holding in holdings:
            original_symbol = holding.get('symbol', '')
            converted = cls.convert_symbol(original_symbol)
            
            if converted in quotes:
                quote = quotes[converted]
                holding['current_price'] = quote['price']
                holding['prev_close'] = quote['prev_close']
                holding['pct_chg'] = quote['pct_chg']
                holding['update_time'] = quote['update_time']
                updated_count += 1
            else:
                # 尝试原始格式
                if original_symbol in quotes:
                    quote = quotes[original_symbol]
                    holding['current_price'] = quote['price']
                    holding['prev_close'] = quote['prev_close']
                    holding['pct_chg'] = quote['pct_chg']
                    holding['update_time'] = quote['update_time']
                    updated_count += 1
        
        logger.info(f"更新了 {updated_count}/{len(holdings)} 只持仓股票的价格")
        
        return holdings
    
    @classmethod
    async def get_portfolio_value(cls, holdings: list) -> dict:
        """
        计算持仓组合市值
        
        Returns:
            {total_value, total_cost, profit, profit_pct}
        """
        if not holdings:
            return {
                'total_value': 0,
                'total_cost': 0,
                'profit': 0,
                'profit_pct': 0,
            }
        
        total_value = 0
        total_cost = 0
        
        updated = await cls.update_portfolio_prices(holdings)
        
        for h in updated:
            quantity = h.get('quantity', 0)
            current_price = h.get('current_price', 0)
            cost_price = h.get('cost_price', 0)
            
            total_value += quantity * current_price
            total_cost += quantity * cost_price
        
        profit = total_value - total_cost
        profit_pct = (profit / total_cost * 100) if total_cost > 0 else 0
        
        return {
            'total_value': total_value,
            'total_cost': total_cost,
            'profit': profit,
            'profit_pct': profit_pct,
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        }


# 测试
if __name__ == '__main__':
    async def test():
        print("=== 测试持仓价格更新 ===\n")
        
        # 模拟持仓
        holdings = [
            {'symbol': '000001', 'name': '平安银行', 'quantity': 1000, 'cost_price': 11.5},
            {'symbol': '600000', 'name': '浦发银行', 'quantity': 500, 'cost_price': 10.2},
            {'symbol': '300750', 'name': '宁德时代', 'quantity': 100, 'cost_price': 420.0},
        ]
        
        result = await PortfolioPriceUpdater.get_portfolio_value(holdings)
        
        print(f"总市值: {result['total_value']:.2f}")
        print(f"总成本: {result['total_cost']:.2f}")
        print(f"盈亏: {result['profit']:.2f} ({result['profit_pct']:.2f}%)")
        
        print("\n持仓明细:")
        for h in holdings:
            print(f"  {h['name']}: 现价={h.get('current_price', 'N/A')}, 涨跌={h.get('pct_chg', 'N/A')}%")
    
    asyncio.run(test())
