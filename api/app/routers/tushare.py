"""
Tushare API路由
从本地SQLite数据库读取股票数据
"""

import sqlite3
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta

router_tushare = APIRouter(prefix="/tushare", tags=["Tushare数据"])

# SQLite数据库路径
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
        search_term = q if q else keyword
        if not search_term:
            return {"results": [], "count": 0}
        
        search_term = search_term.upper()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 搜索股票代码或名称
        cursor.execute("""
            SELECT ts_code, symbol, name, area, industry, market 
            FROM stocks 
            WHERE symbol LIKE ? OR name LIKE ?
            LIMIT 10
        """, (f"%{search_term}%", f"%{search_term}%"))
        
        rows = cursor.fetchall()
        conn.close()
        
        # 格式化返回结果
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
    """获取股票最新行情（从Tushare实时获取）"""
    try:
        import requests
        
        # 处理代码格式
        if "." not in ts_code:
            if ts_code.startswith("6"):
                ts_code = f"{ts_code}.SH"
            else:
                ts_code = f"{ts_code}.SZ"
        
        # 调用Tushare API
        token = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"
        url = "http://api.tushare.pro"
        
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        
        payload = {
            "api_name": "daily",
            "token": token,
            "params": {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date
            }
        }
        
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        
        if result.get("code") != 0 or not result.get("data"):
            raise HTTPException(status_code=404, detail="股票数据不存在")
        
        # 获取最新一天的数据
        fields = result["data"]["fields"]
        items = result["data"]["items"]
        
        if not items:
            raise HTTPException(status_code=404, detail="暂无数据")
        
        latest = items[-1]  # 最新一天
        
        # 构建返回数据
        field_map = {field: i for i, field in enumerate(fields)}
        
        return {
            "symbol": ts_code.split(".")[0],
            "ts_code": ts_code,
            "trade_date": latest[field_map["trade_date"]],
            "open": latest[field_map["open"]],
            "high": latest[field_map["high"]],
            "low": latest[field_map["low"]],
            "close": latest[field_map["close"]],
            "pre_close": latest[field_map["pre_close"]],
            "change": latest[field_map["change"]],
            "pct_chg": latest[field_map["pct_chg"]],
            "vol": latest[field_map["vol"]],
            "amount": latest[field_map["amount"]]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"获取行情失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"获取行情失败: {e}")
