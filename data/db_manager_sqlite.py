"""
AI 股神争霸赛 - SQLite数据库管理器
使用主数据库 /var/www/familystock-test/data/ai_stock_competition.db
"""

import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, date
import logging
import asyncio

from engine.trading import Portfolio, Holding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 主数据库路径
MAIN_DB_PATH = "/var/www/familystock-test/data/ai_stock_competition.db"

# AI ID映射（字符ID -> 数字ID）
CHAR_TO_NUM = {
    "trend_chaser": 1, "quant_queen": 2, "value_veteran": 3,
    "scalper_fairy": 4, "macro_master": 5,
    "tech_whiz": 6, "dividend_hunter": 7, "turnaround_pro": 8,
    "momentum_kid": 9, "event_driven": 10
}

NUM_TO_CHAR = {v: k for k, v in CHAR_TO_NUM.items()}


class DatabaseManager:
    """数据库管理器 - 使用SQLite主数据库"""
    
    def __init__(self, db_path: str = MAIN_DB_PATH):
        self.db_path = db_path
    
    def _get_connection(self):
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    # ============ 投资组合操作 ============
    
    async def get_portfolio(self, ai_id: str) -> Optional[Portfolio]:
        """从数据库加载投资组合"""
        ai_num_id = CHAR_TO_NUM.get(ai_id, 0)
        if ai_num_id == 0:
            logger.warning(f"未知的AI ID: {ai_id}")
            return Portfolio(ai_id=ai_id, cash=1000000.0, holdings=[], total_value=1000000.0)
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取AI基本信息
            cursor.execute(
                "SELECT initial_capital, current_capital FROM ai_characters WHERE id = ?",
                (ai_num_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                logger.warning(f"AI {ai_id} (ID={ai_num_id}) 不存在")
                conn.close()
                return Portfolio(ai_id=ai_id, cash=1000000.0, holdings=[], total_value=1000000.0)
            
            initial_capital, current_capital = row
            
            # 获取持仓
            holdings = await self._get_holdings(ai_id, cursor)
            
            # 计算现金（总资产 - 持仓市值）
            stock_value = sum(h.market_value for h in holdings)
            cash = current_capital - stock_value
            
            portfolio = Portfolio(
                ai_id=ai_id,
                cash=cash,
                holdings=holdings,
                total_value=current_capital
            )
            
            conn.close()
            return portfolio
            
        except Exception as e:
            logger.error(f"加载投资组合失败 {ai_id}: {e}")
            conn.close()
            return Portfolio(ai_id=ai_id, cash=1000000.0, holdings=[], total_value=1000000.0)
    
    async def _get_holdings(self, ai_id: str, cursor) -> List[Holding]:
        """获取持仓列表"""
        ai_num_id = CHAR_TO_NUM.get(ai_id, 0)
        if ai_num_id == 0:
            return []
        
        cursor.execute(
            """
            SELECT stock_code, stock_name, quantity, cost_price, current_price, 
                   market_value, profit_loss, return_pct
            FROM ai_positions 
            WHERE ai_id = ? AND quantity > 0
            """,
            (ai_num_id,)
        )
        
        holdings = []
        for row in cursor.fetchall():
            symbol, name, quantity, cost_price, current_price, market_value, profit_loss, return_pct = row
            
            # 计算盈亏百分比
            unrealized_pnl_pct = (return_pct / 100) if return_pct else 0
            
            holdings.append(Holding(
                symbol=symbol,
                name=name or symbol,
                quantity=quantity,
                buy_price=cost_price,
                current_price=current_price,
                market_value=market_value,
                unrealized_pnl=profit_loss or 0,
                unrealized_pnl_pct=unrealized_pnl_pct
            ))
        
        return holdings
    
    async def save_portfolio(self, portfolio: Portfolio):
        """保存投资组合到数据库"""
        ai_num_id = CHAR_TO_NUM.get(portfolio.ai_id, 0)
        if ai_num_id == 0:
            logger.warning(f"无法保存未知AI的投资组合: {portfolio.ai_id}")
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 获取初始资金
            cursor.execute(
                "SELECT initial_capital FROM ai_characters WHERE id = ?",
                (ai_num_id,)
            )
            row = cursor.fetchone()
            initial_capital = row[0] if row else 1000000.0
            
            # 计算总收益
            total_return_pct = ((portfolio.total_value - initial_capital) / initial_capital) * 100
            
            # 更新AI角色表
            cursor.execute(
                """
                UPDATE ai_characters 
                SET current_capital = ?, total_return = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (portfolio.total_value, total_return_pct, ai_num_id)
            )
            
            # 保存持仓明细
            for holding in portfolio.holdings:
                await self._save_holding(cursor, ai_num_id, holding)
            
            conn.commit()
            logger.info(f"投资组合已保存: {portfolio.ai_id}, 总资产={portfolio.total_value:,.0f}, 持仓={len(portfolio.holdings)}只")
            
        except Exception as e:
            logger.error(f"保存投资组合失败 {portfolio.ai_id}: {e}")
        finally:
            conn.close()
    
    async def _save_holding(self, cursor, ai_num_id: int, holding):
        """保存单个持仓"""
        try:
            symbol = holding.symbol
            name = holding.name
            quantity = holding.quantity
            avg_cost = holding.buy_price
            current_price = holding.current_price
            market_value = quantity * current_price
            profit_loss = (current_price - avg_cost) * quantity
            return_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
            
            # 检查是否已有持仓
            cursor.execute(
                "SELECT id FROM ai_positions WHERE ai_id = ? AND stock_code = ?",
                (ai_num_id, symbol)
            )
            
            if cursor.fetchone():
                # 更新现有持仓
                cursor.execute(
                    """
                    UPDATE ai_positions 
                    SET quantity = ?, cost_price = ?, current_price = ?, 
                        market_value = ?, profit_loss = ?, return_pct = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ai_id = ? AND stock_code = ?
                    """,
                    (quantity, avg_cost, current_price, market_value, profit_loss, return_pct,
                     ai_num_id, symbol)
                )
            else:
                # 插入新持仓
                cursor.execute(
                    """
                    INSERT INTO ai_positions 
                    (ai_id, stock_code, stock_name, quantity, cost_price, current_price,
                     market_value, profit_loss, return_pct, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (ai_num_id, symbol, name, quantity, avg_cost, current_price,
                     market_value, profit_loss, return_pct)
                )
        except Exception as e:
            logger.error(f"保存持仓失败 {ai_num_id} {holding.symbol}: {e}")
    
    async def save_trade(self, ai_id: str, ai_name: str, decision, success: bool):
        """保存交易记录"""
        # 主数据库没有交易记录表，这里仅作日志记录
        action_str = "买入" if decision.action.value == "buy" else "卖出"
        logger.info(f"交易记录: {ai_name} {action_str} {decision.name} {decision.quantity}股 @ {decision.price:.2f}")
    
    async def update_position(self, ai_id: str, symbol: str, name: str, quantity: int, 
                              avg_cost: float, current_price: float):
        """更新持仓"""
        ai_num_id = CHAR_TO_NUM.get(ai_id, 0)
        if ai_num_id == 0:
            return
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            market_value = quantity * current_price
            profit_loss = (current_price - avg_cost) * quantity
            return_pct = ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0
            
            # 检查是否已有持仓
            cursor.execute(
                "SELECT id FROM ai_positions WHERE ai_id = ? AND stock_code = ?",
                (ai_num_id, symbol)
            )
            
            if cursor.fetchone():
                # 更新现有持仓
                cursor.execute(
                    """
                    UPDATE ai_positions 
                    SET quantity = ?, cost_price = ?, current_price = ?, 
                        market_value = ?, profit_loss = ?, return_pct = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE ai_id = ? AND stock_code = ?
                    """,
                    (quantity, avg_cost, current_price, market_value, profit_loss, return_pct,
                     ai_num_id, symbol)
                )
            else:
                # 插入新持仓
                cursor.execute(
                    """
                    INSERT INTO ai_positions 
                    (ai_id, stock_code, stock_name, quantity, cost_price, current_price,
                     market_value, profit_loss, return_pct, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (ai_num_id, symbol, name, quantity, avg_cost, current_price,
                     market_value, profit_loss, return_pct)
                )
            
            conn.commit()
            logger.info(f"持仓已更新: {ai_id} {symbol} {quantity}股")
            
        except Exception as e:
            logger.error(f"更新持仓失败 {ai_id} {symbol}: {e}")
        finally:
            conn.close()
    
    async def connect(self):
        """兼容性方法 - SQLite不需要显式连接"""
        pass
    
    async def close(self):
        """兼容性方法 - SQLite不需要显式关闭连接池"""
        pass
