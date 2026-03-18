"""
股票基础信息API路由
提供 /stock/basic/{code} 接口供前端 stock-detail.html 使用
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
import requests
import sqlite3
import os

router_stock = APIRouter(prefix="/stock", tags=["股票信息"])

# Tushare配置
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"
TUSHARE_API_URL = "http://api.tushare.pro"

# 数据库路径
SQLITE_DB_PATH = "/var/www/familystock/api/data/family_stock.db"


def get_stock_name_from_db(symbol: str) -> str:
    """从数据库获取股票名称"""
    try:
        if not os.path.exists(SQLITE_DB_PATH):
            return symbol
        
        conn = sqlite3.connect(SQLITE_DB_PATH)
        cursor = conn.cursor()
        
        # 检查stocks表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='stocks'")
        if not cursor.fetchone():
            conn.close()
            return symbol
        
        # 查询股票名称
        cursor.execute("SELECT name FROM stocks WHERE symbol=? LIMIT 1", (symbol,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return result[0]
    except Exception as e:
        print(f"获取股票名称失败: {e}")
    
    return symbol


def get_tushare_quote(symbol: str):
    """从Tushare获取实时行情"""
    try:
        if "." not in symbol:
            ts_code = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"
        else:
            ts_code = symbol
        
        payload = {
            "api_name": "daily",
            "token": TUSHARE_TOKEN,
            "params": {"ts_code": ts_code, "limit": 1}
        }
        
        response = requests.post(TUSHARE_API_URL, json=payload, timeout=10)
        data = response.json()
        
        if data.get("code") != 0 or not data.get("data"):
            # 尝试使用 quote 接口
            payload = {
                "api_name": "daily",
                "token": TUSHARE_TOKEN,
                "params": {"ts_code": ts_code, "trade_date": datetime.now().strftime("%Y%m%d")}
            }
            response = requests.post(TUSHARE_API_URL, json=payload, timeout=10)
            data = response.json()
        
        if data.get("code") == 0 and data.get("data"):
            items = data["data"]["items"]
            if items:
                item = items[0]
                return {
                    "price": float(item[5]),      # close
                    "open": float(item[2]),       # open
                    "high": float(item[3]),       # high
                    "low": float(item[4]),        # low
                    "change": float(item[7]),     # change
                    "change_percent": float(item[8]),  # pct_chg
                    "volume": float(item[9]),     # vol
                    "amount": float(item[10])     # amount
                }
        return None
    except Exception as e:
        print(f"Tushare API error: {e}")
        return None


@router_stock.get("/basic/{code}")
async def get_stock_basic(code: str):
    """获取股票基础信息和行情（适配前端stock-detail.html）"""
    try:
        # 处理代码格式（移除.SZ/.SH后缀）
        pure_code = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "").replace(".sz", "").replace(".sh", "").replace(".bj", "")
        
        # 从Tushare获取行情
        quote = get_tushare_quote(pure_code)
        
        if not quote:
            raise HTTPException(status_code=404, detail="股票不存在")
        
        # 从数据库获取正确的股票名称
        stock_name = get_stock_name_from_db(pure_code)
        
        # 构造兼容前端的数据格式
        return {
            "basic_info": {
                "ts_code": code,
                "symbol": pure_code,
                "name": stock_name  # 使用数据库中的正确名称
            },
            "quote_info": {
                "close": quote.get("price", 0),
                "open": quote.get("open", 0),
                "high": quote.get("high", 0),
                "low": quote.get("low", 0),
                "pre_close": quote.get("price", 0) - quote.get("change", 0),
                "change": quote.get("change", 0),
                "pct_chg": quote.get("change_percent", 0),
                "vol": quote.get("volume", 0),
                "amount": quote.get("amount", 0)
            },
            "finance_info": None
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取股票信息失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取股票信息失败: {str(e)}")


@router_stock.get("/news/{code}")
async def get_stock_news(code: str, limit: int = 5):
    """获取股票相关新闻"""
    try:
        # 从数据库获取新闻
        news_list = []
        if os.path.exists(SQLITE_DB_PATH):
            conn = sqlite3.connect(SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取股票名称用于搜索
            pure_code = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "")
            stock_name = get_stock_name_from_db(pure_code)
            
            # 搜索相关新闻
            cursor.execute("""
                SELECT title, content, source, published_at 
                FROM news 
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY published_at DESC
                LIMIT ?
            """, (f"%{stock_name}%", f"%{stock_name}%", limit))
            
            for row in cursor.fetchall():
                news_list.append({
                    "title": row["title"],
                    "summary": row["content"][:100] + "..." if row["content"] else "",
                    "source": row["source"],
                    "time": row["published_at"]
                })
            
            conn.close()
        
        return {"news": news_list, "count": len(news_list)}
    except Exception as e:
        print(f"获取新闻失败: {e}")
        return {"news": [], "count": 0}


@router_stock.get("/finance/{code}")
async def get_stock_finance(code: str, limit: int = 4):
    """获取股票财务数据（简化版）"""
    return {
        "finance_info": None,
        "message": "财务数据功能开发中"
    }


@router_stock.get("/capital/{code}")
async def get_stock_capital(code: str):
    """获取资金流向（简化版）"""
    return {
        "capital_info": None,
        "message": "资金流向功能开发中"
    }
