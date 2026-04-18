#!/usr/bin/env python3
"""
AI股神争霸赛 - 股价更新服务
更新所有持仓的当前价格，计算实时盈亏
"""

import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

import akshare as ak
import asyncpg
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def update_prices():
    """更新股价并计算盈亏"""
    logger.info("=" * 60)
    logger.info("开始更新股价...")
    logger.info("=" * 60)
    
    try:
        conn = await asyncpg.connect("postgresql://minirock:minirock123@localhost:5432/minirock")
        
        # 1. 获取所有持仓股票
        rows = await conn.fetch("SELECT DISTINCT symbol FROM ai_holdings")
        symbols = [r['symbol'] for r in rows]
        logger.info(f"需要更新 {len(symbols)} 只股票")
        
        if not symbols:
            logger.info("无持仓，跳过")
            await conn.close()
            return
        
        # 2. 获取实时行情（一次性获取所有股票）
        logger.info("获取实时行情...")
        try:
            df = ak.stock_zh_a_spot_em()
            logger.info(f"获取到 {len(df)} 只股票行情")
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            await conn.close()
            return
        
        # 3. 更新每只股票的价格
        updated_count = 0
        for symbol in symbols:
            try:
                # 查找股票行情
                row = df[df['代码'] == symbol]
                if row.empty:
                    logger.warning(f"[{symbol}] 未找到行情数据")
                    continue
                
                # 获取最新价
                current_price = float(row.iloc[0]['最新价'])
                if current_price <= 0:
                    logger.warning(f"[{symbol}] 价格异常: {current_price}")
                    continue
                
                # 更新持仓表的current_price
                result = await conn.execute(
                    "UPDATE ai_holdings SET current_price = $1 WHERE symbol = $2",
                    current_price, symbol
                )
                
                # 计算并更新每只持仓的盈亏
                holdings = await conn.fetch(
                    "SELECT id, ai_id, quantity, buy_price FROM ai_holdings WHERE symbol = $1",
                    symbol
                )
                
                for h in holdings:
                    quantity = h['quantity']
                    buy_price = h['buy_price']
                    unrealized_pnl = (current_price - buy_price) * quantity
                    unrealized_pnl_pct = ((current_price - buy_price) / buy_price * 100) if buy_price > 0 else 0
                    market_value = current_price * quantity
                    
                    await conn.execute(
                        """UPDATE ai_holdings 
                           SET current_price = $1, 
                               unrealized_pnl = $2, 
                               unrealized_pnl_pct = $3,
                               market_value = $4,
                               updated_at = $5
                           WHERE id = $6""",
                        current_price, unrealized_pnl, unrealized_pnl_pct, market_value, 
                        datetime.now(), h['id']
                    )
                
                updated_count += 1
                logger.info(f"[{symbol}] 更新为 ¥{current_price:.2f}")
                
            except Exception as e:
                logger.error(f"[{symbol}] 更新失败: {e}")
        
        logger.info(f"成功更新 {updated_count} 只股票")
        
        # 4. 更新每个AI的投资组合市值和盈亏
        logger.info("更新投资组合...")
        portfolios = await conn.fetch("""
            SELECT p.ai_id, p.cash, p.initial_capital,
                   COALESCE(SUM(h.market_value), 0) as stock_value,
                   COALESCE(SUM(h.unrealized_pnl), 0) as total_unrealized_pnl
            FROM ai_portfolios p
            LEFT JOIN ai_holdings h ON p.ai_id = h.ai_id
            GROUP BY p.ai_id, p.cash, p.initial_capital
        """)
        
        for p in portfolios:
            ai_id = p['ai_id']
            cash = p['cash']
            stock_value = p['stock_value']
            total_value = cash + stock_value
            total_unrealized_pnl = p['total_unrealized_pnl']
            total_return_pct = ((total_value - p['initial_capital']) / p['initial_capital'] * 100) if p['initial_capital'] > 0 else 0
            
            await conn.execute(
                """UPDATE ai_portfolios 
                   SET total_value = $1,
                       total_return_pct = $2,
                       updated_at = $3
                   WHERE ai_id = $4""",
                total_value, total_return_pct, datetime.now(), ai_id
            )
            
            logger.info(f"{ai_id}: 股票¥{stock_value:.0f} + 现金¥{cash:.0f} = 总¥{total_value:.0f}, 盈亏¥{total_unrealized_pnl:.0f}")
        
        await conn.close()
        logger.info("=" * 60)
        logger.info("股价更新完成")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"更新失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(update_prices())
