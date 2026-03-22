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

# 数据库路径 - 通过环境变量配置，区分测试/生产环境
# 测试环境(KimiClaw): /var/www/familystock/api/data/stock_data.db
# 生产环境(TenClaw): /var/www/familystock/api/data/family_stock.db
DB_PATH = '/var/www/familystock/api/data/family_stock.db'


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Tushare配置
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"
TUSHARE_API_URL = "http://api.tushare.pro"


def get_tushare_quote(symbol: str):
    """从Tushare获取最新日K线数据，返回完整数据包含trade_date"""
    try:
        if "." not in symbol:
            ts_code = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"
        else:
            ts_code = symbol
            symbol = ts_code.split(".")[0]
        
        payload = {
            "api_name": "daily",
            "token": TUSHARE_TOKEN,
            "params": {"ts_code": ts_code, "limit": 1}
        }
        
        response = requests.post(TUSHARE_API_URL, json=payload, timeout=10)
        result = response.json()
        
        if result.get("code") != 0 or not result.get("data", {}).get("items"):
            return None
        
        fields = result["data"]["fields"]
        item = result["data"]["items"][0]
        data = dict(zip(fields, item))
        
        return {
            "ts_code": ts_code,
            "symbol": symbol,
            "trade_date": str(data.get("trade_date", "")),
            "open": float(data.get("open", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0)),
            "close": float(data.get("close", 0)),
            "pre_close": float(data.get("pre_close", 0)),
            "change": float(data.get("change", 0)),
            "pct_chg": float(data.get("pct_chg", 0)),
            "vol": float(data.get("vol", 0)),
            "amount": float(data.get("amount", 0)),
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"获取行情失败 {symbol}: {e}")
        return None


def save_quote_to_db(quote_data: dict):
    """将行情数据保存到本地数据库"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO stock_quotes 
            (ts_code, symbol, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            quote_data['ts_code'],
            quote_data['symbol'],
            quote_data['trade_date'],
            quote_data['open'],
            quote_data['high'],
            quote_data['low'],
            quote_data['close'],
            quote_data['pre_close'],
            quote_data['change'],
            quote_data['pct_chg'],
            quote_data['vol'],
            quote_data['amount']
        ))
        conn.commit()
        conn.close()
        print(f"✅ 已缓存行情数据: {quote_data['ts_code']} @ {quote_data['trade_date']}")
        return True
    except Exception as e:
        print(f"❌ 缓存行情数据失败: {e}")
        return False


@router_stock.get("/basic/{code}")
async def get_stock_basic(code: str):
    """获取股票基础信息和行情（适配前端stock-detail.html）"""
    try:
        # 处理代码格式（移除.SZ/.SH后缀）
        pure_code = code.replace(".SZ", "").replace(".SH", "").replace(".BJ", "").replace(".sz", "").replace(".sh", "").replace(".bj", "")
        
        # 1. 先从本地数据库查询股票基础信息（兼容stock_basic和stocks两个表名）
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查哪个表存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('stock_basic', 'stocks')")
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        stock_row = None
        if 'stock_basic' in existing_tables:
            cursor.execute(
                "SELECT ts_code, symbol, name, area, industry, market, list_date FROM stock_basic WHERE symbol = ?",
                (pure_code,)
            )
            stock_row = cursor.fetchone()
        
        # 如果stock_basic没有数据，尝试stocks表
        if not stock_row and 'stocks' in existing_tables:
            cursor.execute(
                "SELECT ts_code, symbol, name, area, industry, market, list_date FROM stocks WHERE symbol = ?",
                (pure_code,)
            )
            stock_row = cursor.fetchone()
        
        conn.close()
        
        if not stock_row:
            raise HTTPException(status_code=404, detail=f"股票 {pure_code} 不存在，请检查代码是否正确")
        
        # 2. 从本地查询最新行情（stock_quotes表）
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT close, open, high, low, pre_close, change, pct_chg, vol, amount FROM stock_quotes WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1",
            (stock_row['ts_code'],)
        )
        quote_row = cursor.fetchone()
        conn.close()
        
        # 如果本地没有行情数据，尝试从Tushare获取并缓存
        if not quote_row:
            print(f"本地无行情数据，从Tushare获取: {pure_code}")
            quote = get_tushare_quote(pure_code)
            if quote:
                # 保存到本地数据库
                save_quote_to_db(quote)
                quote_row = {
                    'close': quote['close'],
                    'open': quote['open'],
                    'high': quote['high'],
                    'low': quote['low'],
                    'pre_close': quote['pre_close'],
                    'change': quote['change'],
                    'pct_chg': quote['pct_chg'],
                    'vol': quote['vol'],
                    'amount': quote['amount']
                }
            else:
                print(f"⚠️ 从Tushare获取行情失败: {pure_code}")
        
        # 构造兼容前端的数据格式
        return {
            "basic_info": {
                "ts_code": stock_row['ts_code'],
                "symbol": stock_row['symbol'],
                "name": stock_row['name'],
                "area": stock_row['area'],
                "industry": stock_row['industry'],
                "market": stock_row['market'],
                "list_date": stock_row['list_date']
            },
            "quote_info": {
                "close": quote_row['close'] if quote_row else 0,
                "open": quote_row['open'] if quote_row else 0,
                "high": quote_row['high'] if quote_row else 0,
                "low": quote_row['low'] if quote_row else 0,
                "pre_close": quote_row['pre_close'] if quote_row else 0,
                "change": quote_row['change'] if quote_row else 0,
                "pct_chg": quote_row['pct_chg'] if quote_row else 0,
                "vol": quote_row['vol'] if quote_row else 0,
                "amount": quote_row['amount'] if quote_row else 0
            },
            "finance_info": None
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取股票基础信息失败 {code}: {e}")
        raise HTTPException(status_code=500, detail=f"获取股票信息失败: {e}")


# 其他股票相关API
@router_stock.get("/news/{code}")
async def get_stock_news(code: str, limit: int = 5):
    """获取股票相关新闻（模拟数据）"""
    import random
    from datetime import timedelta
    
    sentiments = ["positive", "neutral", "negative"]
    news_list = []
    
    for i in range(limit):
        sentiment = random.choice(sentiments)
        news_list.append({
            "title": f"{code}相关新闻标题{i+1}",
            "summary": f"这是关于{code}的新闻摘要内容...",
            "source": "财经媒体",
            "published_at": (datetime.now() - timedelta(hours=i*2)).isoformat(),
            "sentiment": sentiment,
            "impact": "high" if sentiment == "positive" else "medium"
        })
    
    return {"news": news_list, "count": len(news_list)}


@router_stock.get("/finance/{code}")
async def get_stock_finance(code: str, limit: int = 4):
    """获取股票财务历史（模拟数据）"""
    import random
    
    finance_history = []
    base_pe = 15 + random.random() * 10
    
    for i in range(limit):
        finance_history.append({
            "end_date": (datetime.now() - timedelta(days=i*90)).strftime("%Y-%m-%d"),
            "pe": round(base_pe + random.random() * 2, 1),
            "pb": round(2 + random.random(), 1),
            "roe": round(12 + random.random() * 2, 1),
            "gross_margin": round(35 + random.random(), 1),
            "net_margin": round(18 + random.random(), 1),
            "revenue_growth": round(8 + random.random() * 2, 1),
            "profit_growth": round(10 + random.random() * 2, 1)
        })
    
    return {
        "ts_code": code,
        "finance_history": finance_history,
        "count": len(finance_history)
    }


@router_stock.get("/capital/{code}")
async def get_stock_capital(code: str):
    """获取股票资金面信息（模拟数据）"""
    return {
        "hsgt_hold": {
            "hold_amount": 1234567.89,
            "hold_ratio": 2.35,
            "trade_date": datetime.now().strftime("%Y%m%d")
        },
        "top_list": [
            {
                "trade_date": datetime.now().strftime("%Y%m%d"),
                "name": "机构买入",
                "close": 10.76,
                "pct_change": -0.55,
                "turnover_rate": 2.35,
                "amount": 50000000,
                "buy_amount": 30000000,
                "sell_amount": 20000000,
                "net_amount": 10000000,
                "reason": "机构买入"
            }
        ],
        "top_list_count": 1
    }
