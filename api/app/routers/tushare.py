"""
Tushare API路由
从本地SQLite数据库读取股票数据
"""

import sqlite3
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime

router_tushare = APIRouter(prefix="/tushare", tags=["Tushare数据"])

# SQLite数据库路径 (测试环境)
DB_PATH = "/var/www/familystock/api/data/family_stock.db"


def get_db_connection():
    """获取SQLite数据库连接"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        raise HTTPException(status_code=500, detail="数据库连接失败")


@router_tushare.get("/search")
async def search_tushare_stocks(q: str = Query(None, description="搜索关键词"), keyword: str = Query(None, description="搜索关键词(别名)")):
    """搜索股票（从本地SQLite数据库读取）"""
    try:
        search_term = q or keyword
        if not search_term:
            return {"results": [], "count": 0}
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 搜索股票
        cursor.execute("""
            SELECT ts_code, symbol, name, area, industry, market 
            FROM stocks 
            WHERE symbol LIKE ? OR name LIKE ?
            LIMIT 10
        """, (f"%{search_term}%", f"%{search_term}%"))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        results = []
        for row in rows:
            results.append({
                "ts_code": row["ts_code"],
                "symbol": row["symbol"],
                "name": row["name"],
                "area": row["area"],
                "industry": row["industry"],
                "market": row["market"]
            })
        
        return {"results": results, "count": len(results)}
        
    except Exception as e:
        print(f"搜索失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"搜索失败: {e}")


@router_tushare.get("/quote/{ts_code}")
async def get_stock_quote(ts_code: str):
    """获取股票最新行情（从本地SQLite数据库读取）"""
    try:
        # 处理代码格式
        original_code = ts_code
        if "." not in ts_code:
            if ts_code.startswith("6"):
                ts_code = f"{ts_code}.SH"
            else:
                ts_code = f"{ts_code}.SZ"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 查询最新行情
        cursor.execute("""
            SELECT * FROM stock_quotes 
            WHERE ts_code = ? 
            ORDER BY trade_date DESC 
            LIMIT 1
        """, (ts_code,))
        
        result = cursor.fetchone()
        
        if not result:
            # 如果没有找到，尝试用不带后缀的代码搜索
            cursor.execute("""
                SELECT q.* FROM stock_quotes q
                JOIN stocks s ON q.ts_code = s.ts_code
                WHERE s.symbol = ?
                ORDER BY q.trade_date DESC
                LIMIT 1
            """, (original_code,))
            result = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="股票数据不存在")
        
        # 格式化返回结果
        return {
            "symbol": original_code,
            "ts_code": result["ts_code"],
            "trade_date": result["trade_date"],
            "open": float(result["open"] or 0),
            "high": float(result["high"] or 0),
            "low": float(result["low"] or 0),
            "close": float(result["close"] or 0),
            "pre_close": float(result["pre_close"] or 0),
            "change": float(result["change"] or 0),
            "pct_chg": float(result["pct_chg"] or 0),
            "vol": float(result["vol"] or 0),
            "amount": float(result["amount"] or 0),
            "market": "A股",
            "currency": "CNY",
            "source": "Local Database"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取行情失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取行情失败: {e}")


@router_tushare.get("/batch")
async def get_batch_quotes(symbols: str = Query(..., description="逗号分隔的股票代码")):
    """批量获取股票行情"""
    try:
        symbol_list = [s.strip() for s in symbols.split(",")]
        results = []
        
        for symbol in symbol_list:
            try:
                quote = await get_stock_quote(symbol)
                results.append(quote)
            except Exception as e:
                print(f"获取{symbol}行情失败: {e}")
                continue
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量获取行情失败: {str(e)}")


@router_tushare.get("/index")
async def get_index_quotes():
    """Get index quotes from index_quotes table"""
    try:
        import sqlite3
        
        indices = [
            {"ts_code": "000001.SH", "name": "上证指数"},
            {"ts_code": "399001.SZ", "name": "深证成指"},
            {"ts_code": "399006.SZ", "name": "创业板指"},
        ]
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        results = []
        for idx in indices:
            cursor.execute("SELECT * FROM index_quotes WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1", (idx["ts_code"],))
            row = cursor.fetchone()
            
            if row and row["close"]:
                results.append({
                    "name": idx["name"],
                    "ts_code": idx["ts_code"],
                    "close": float(row["close"]),
                    "pct_chg": float(row["pct_chg"] or 0),
                    "source": "local_db"
                })
            else:
                results.append({
                    "name": idx["name"],
                    "ts_code": idx["ts_code"],
                    "close": 0,
                    "pct_chg": 0,
                    "source": "unavailable"
                })
        
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def get_news_list(limit: int = 10):
    """获取最新新闻列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, title, content, summary, source, url, category, sentiment, published_at 
            FROM news 
            ORDER BY published_at DESC 
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            result.append({
                'id': row['id'],
                'title': row['title'],
                'content': row['content'],
                'summary': row['summary'],
                'source': row['source'],
                'url': row['url'],
                'category': row['category'],
                'sentiment': row['sentiment'],
                'published_at': row['published_at']
            })
        
        return result
    except Exception as e:
        print(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))
