"""
AI 股神争霸赛 - 数据库模型
使用PostgreSQL持久化投资组合、持仓和交易记录
"""

import asyncpg
from typing import Dict, List, Optional
from datetime import datetime, date
import logging
import asyncio

from engine.trading import Portfolio, Holding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理器 - 使用连接池"""
    
    def __init__(self, db_url: str = "postgresql://minirock:minirock123@localhost:5432/minirock"):
        self.db_url = db_url
        self.pool = None
    
    async def connect(self):
        """连接数据库 - 创建连接池"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=5,
                max_size=20
            )
            logger.info("数据库连接池创建成功")
    
    async def close(self):
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()
            self.pool = None
    
    # ============ 投资组合操作 ============
    
    async def get_portfolio(self, ai_id: str) -> Optional[Portfolio]:
        """从数据库加载投资组合"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            # 获取投资组合基本信息
            row = await conn.fetchrow(
                """
                SELECT initial_capital, cash, total_value, 
                       total_return_pct, daily_return_pct, win_streak
                FROM ai_portfolios 
                WHERE ai_id = $1
                """,
                ai_id
            )
            
            if not row:
                # 如果没有记录，创建新的
                await self._init_portfolio(ai_id, conn)
                return Portfolio(ai_id=ai_id, cash=1000000.0, holdings=[], total_value=1000000.0)
            
            # 获取持仓
            holdings = await self._get_holdings(ai_id, conn)
            
            portfolio = Portfolio(
                ai_id=ai_id,
                cash=float(row['cash']),
                holdings=holdings,
                total_value=float(row['total_value'])
            )
            
            return portfolio
    
    async def save_portfolio(self, portfolio: Portfolio):
        """保存投资组合到数据库"""
        await self.connect()
        
        initial_capital = 1000000.0
        total_return_pct = ((portfolio.total_value - initial_capital) / initial_capital) * 100
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO ai_portfolios 
                    (ai_id, cash, total_value, total_return_pct, updated_at)
                VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
                ON CONFLICT (ai_id) 
                DO UPDATE SET 
                    cash = EXCLUDED.cash,
                    total_value = EXCLUDED.total_value,
                    total_return_pct = EXCLUDED.total_return_pct,
                    updated_at = CURRENT_TIMESTAMP
                """,
                portfolio.ai_id,
                portfolio.cash,
                portfolio.total_value,
                total_return_pct
            )
            
            # 保存持仓
            await self._save_holdings(portfolio, conn)
    
    async def _init_portfolio(self, ai_id: str, conn):
        """初始化投资组合记录"""
        from core.characters import get_character
        character = get_character(ai_id)
        
        await conn.execute(
            """
            INSERT INTO ai_portfolios (ai_id, ai_name, initial_capital, cash, total_value)
            VALUES ($1, $2, 1000000.00, 1000000.00, 1000000.00)
            ON CONFLICT (ai_id) DO NOTHING
            """,
            ai_id,
            character.name if character else ai_id
        )
    
    # ============ 持仓操作 ============
    
    async def _get_holdings(self, ai_id: str, conn) -> List[Holding]:
        """获取AI的持仓列表"""
        rows = await conn.fetch(
            """
            SELECT symbol, name, quantity, buy_price, buy_date, 
                   current_price, market_value
            FROM ai_holdings 
            WHERE ai_id = $1
            """,
            ai_id
        )
        
        holdings = []
        for row in rows:
            holding = Holding(
                symbol=row['symbol'],
                name=row['name'],
                quantity=row['quantity'],
                buy_price=float(row['buy_price']),
                buy_date=row['buy_date'],
                current_price=float(row['current_price']) if row['current_price'] else float(row['buy_price'])
            )
            holdings.append(holding)
        
        return holdings
    
    async def _save_holdings(self, portfolio: Portfolio, conn):
        """保存持仓到数据库"""
        # 先删除旧持仓
        await conn.execute(
            "DELETE FROM ai_holdings WHERE ai_id = $1",
            portfolio.ai_id
        )
        
        # 插入新持仓
        for holding in portfolio.holdings:
            await conn.execute(
                """
                INSERT INTO ai_holdings 
                    (ai_id, symbol, name, quantity, buy_price, buy_date, 
                     current_price, market_value, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP)
                """,
                portfolio.ai_id,
                holding.symbol,
                holding.name,
                holding.quantity,
                holding.buy_price,
                holding.buy_date,
                holding.current_price,
                holding.market_value
            )
    
    # ============ 交易记录操作 ============
    
    async def save_trade(self, ai_id: str, ai_name: str, trade, success: bool) -> int:
        """保存交易记录"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ai_trades 
                    (ai_id, ai_name, action, symbol, name, quantity, 
                     price, amount, reason, confidence, trade_date, success)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, CURRENT_DATE, $11)
                RETURNING id
                """,
                ai_id,
                ai_name,
                trade.action.value,
                trade.symbol,
                trade.name,
                trade.quantity,
                trade.price,
                trade.amount,
                trade.reason,
                trade.confidence,
                success
            )
            return row['id']
    
    async def get_recent_trades(self, ai_id: str, limit: int = 10) -> List[Dict]:
        """获取指定AI的最近交易记录"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ai_id, ai_name, action, symbol, name, quantity, price, 
                       amount, reason, trade_time, trade_date
                FROM ai_trades 
                WHERE ai_id = $1
                ORDER BY trade_time DESC
                LIMIT $2
                """,
                ai_id,
                limit
            )
            
            return [dict(row) for row in rows]
    
    async def get_recent_trades_all(self, limit: int = 50) -> List[Dict]:
        """获取所有AI的最近交易记录"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ai_id, ai_name, action, symbol, name, quantity, price, 
                       amount, reason, trade_time, trade_date
                FROM ai_trades 
                ORDER BY trade_time DESC
                LIMIT $1
                """,
                limit
            )
            
            return [dict(row) for row in rows]
    
    # ============ 发帖记录操作 ============
    
    async def save_post(self, ai_id: str, ai_name: str, ai_avatar: str, 
                        post_type: str, content: str, trade_id: Optional[int] = None) -> int:
        """保存发帖记录"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO ai_posts 
                    (ai_id, ai_name, ai_avatar, post_type, content, trade_id)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                ai_id,
                ai_name,
                ai_avatar,
                post_type,
                content,
                trade_id
            )
            return row['id']
    
    async def get_recent_posts(self, limit: int = 20) -> List[Dict]:
        """获取最近的发帖记录"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, ai_id, ai_name, ai_avatar, post_type, 
                       content, likes, comments, created_at
                FROM ai_posts 
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit
            )
            
            return [dict(row) for row in rows]
    
    # ============ 股票价格更新 ============
    
    async def update_holding_prices(self, symbol: str, current_price: float):
        """更新持仓股票当前价格"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            # 更新所有持有该股票的AI的持仓价格
            await conn.execute(
                """
                UPDATE ai_holdings 
                SET current_price = $1::numeric,
                    market_value = quantity * $1::numeric,
                    unrealized_pnl = (quantity * $1::numeric) - (quantity * buy_price::numeric),
                    unrealized_pnl_pct = (($1::numeric - buy_price::numeric) / buy_price::numeric) * 100,
                    updated_at = CURRENT_TIMESTAMP
                WHERE symbol = $2
                """,
                float(current_price),
                str(symbol)
            )
    
    async def get_all_holding_symbols(self) -> List[str]:
        """获取所有持仓的股票代码"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT DISTINCT symbol FROM ai_holdings"
            )
            return [row['symbol'] for row in rows]
    
    async def update_portfolio_values(self):
        """更新所有AI的投资组合市值"""
        await self.connect()
        
        async with self.pool.acquire() as conn:
            # 获取所有AI
            ai_rows = await conn.fetch("SELECT ai_id FROM ai_portfolios")
            
            for ai_row in ai_rows:
                ai_id = ai_row['ai_id']
                
                # 计算该AI的总持仓市值
                holdings_row = await conn.fetchrow(
                    """
                    SELECT COALESCE(SUM(market_value), 0) as total_stock_value
                    FROM ai_holdings
                    WHERE ai_id = $1
                    """,
                    ai_id
                )
                
                total_stock_value = float(holdings_row['total_stock_value'])
                
                # 获取现金
                portfolio_row = await conn.fetchrow(
                    "SELECT cash FROM ai_portfolios WHERE ai_id = $1",
                    ai_id
                )
                cash = float(portfolio_row['cash'])
                
                # 计算总资产
                total_value = cash + total_stock_value
                
                # 计算总收益
                initial_capital = 1000000.0
                total_return_pct = ((total_value - initial_capital) / initial_capital) * 100
                
                # 更新投资组合
                await conn.execute(
                    """
                    UPDATE ai_portfolios 
                    SET total_value = $1,
                        total_return_pct = $2,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ai_id = $3
                    """,
                    total_value,
                    total_return_pct,
                    ai_id
                )
