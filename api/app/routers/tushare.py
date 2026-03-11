"""
Tushare API路由扩展
添加对Tushare Pro数据的支持
"""

import requests
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Query

router_tushare = APIRouter(prefix="/tushare", tags=["Tushare数据"])

TUSHARE_API_URL = "http://api.tushare.pro"
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"


def call_tushare_api(api_name: str, params: dict = None, fields: str = ""):
    """调用Tushare API"""
    payload = {
        "api_name": api_name,
        "token": TUSHARE_TOKEN,
        "params": params or {},
        "fields": fields
    }
    
    try:
        response = requests.post(TUSHARE_API_URL, json=payload, timeout=30)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"Tushare API Error: {result.get('msg')}")
        
        data = result.get("data", {})
        fields_list = data.get("fields", [])
        items = data.get("items", [])
        
        return [dict(zip(fields_list, item)) for item in items]
    except Exception as e:
        print(f"Tushare API调用失败: {e}")
        return None


@router_tushare.get("/quote/{ts_code}")
async def get_tushare_stock_quote(ts_code: str):
    """通过Tushare获取股票最新行情"""
    # 确保代码格式正确（添加后缀）
    if "." not in ts_code:
        if ts_code.startswith("6"):
            ts_code = f"{ts_code}.SH"
        else:
            ts_code = f"{ts_code}.SZ"
    
    # 获取最近7天的数据
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    
    data = call_tushare_api("daily", {
        "ts_code": ts_code,
        "start_date": start_date,
        "end_date": end_date
    })
    
    if not data:
        raise HTTPException(status_code=404, detail="股票数据不存在")
    
    # 返回最新一天的数据
    latest = data[-1]
    
    return {
        "symbol": ts_code.split(".")[0],
        "ts_code": latest.get("ts_code"),
        "trade_date": latest.get("trade_date"),
        "open": float(latest.get("open", 0)),
        "high": float(latest.get("high", 0)),
        "low": float(latest.get("low", 0)),
        "close": float(latest.get("close", 0)),
        "pre_close": float(latest.get("pre_close", 0)),
        "change": float(latest.get("change", 0)),
        "pct_chg": float(latest.get("pct_chg", 0)),
        "volume": float(latest.get("vol", 0)),
        "amount": float(latest.get("amount", 0)),
        "market": "A股",
        "currency": "CNY",
        "source": "Tushare"
    }


@router_tushare.get("/batch")
async def get_tushare_batch_quotes(symbols: str = Query(..., description="逗号分隔的股票代码")):
    """批量获取股票行情"""
    symbol_list = [s.strip() for s in symbols.split(",")]
    results = []
    
    for symbol in symbol_list:
        try:
            # 调用Tushare API
            if "." not in symbol:
                if symbol.startswith("6"):
                    ts_code = f"{symbol}.SH"
                else:
                    ts_code = f"{symbol}.SZ"
            else:
                ts_code = symbol
            
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
            
            data = call_tushare_api("daily", {
                "ts_code": ts_code,
                "start_date": start_date,
                "end_date": end_date
            })
            
            if data and len(data) > 0:
                latest = data[-1]
                results.append({
                    "symbol": symbol,
                    "ts_code": latest.get("ts_code"),
                    "trade_date": latest.get("trade_date"),
                    "close": float(latest.get("close", 0)),
                    "open": float(latest.get("open", 0)),
                    "high": float(latest.get("high", 0)),
                    "low": float(latest.get("low", 0)),
                    "pct_chg": float(latest.get("pct_chg", 0)),
                    "volume": float(latest.get("vol", 0)),
                    "market": "A股",
                    "currency": "CNY"
                })
        except Exception as e:
            print(f"获取{symbol}失败: {e}")
    
    return {"stocks": results, "count": len(results)}


@router_tushare.get("/history/{ts_code}")
async def get_tushare_stock_history(ts_code: str, days: int = 30):
    """获取股票历史数据"""
    if "." not in ts_code:
        if ts_code.startswith("6"):
            ts_code = f"{ts_code}.SH"
        else:
            ts_code = f"{ts_code}.SZ"
    
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
    
    data = call_tushare_api("daily", {
        "ts_code": ts_code,
        "start_date": start_date,
        "end_date": end_date
    })
    
    if not data:
        raise HTTPException(status_code=404, detail="历史数据不存在")
    
    return {
        "symbol": ts_code.split(".")[0],
        "ts_code": ts_code,
        "count": len(data),
        "data": [
            {
                "trade_date": item.get("trade_date"),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "pct_chg": float(item.get("pct_chg", 0)),
                "volume": float(item.get("vol", 0)),
                "amount": float(item.get("amount", 0))
            }
            for item in data
        ]
    }


@router_tushare.get("/search")
async def search_tushare_stocks(keyword: str):
    """搜索股票"""
    # 获取股票基础信息
    data = call_tushare_api("stock_basic", {
        "list_status": "L"
    }, "ts_code,name,area,industry")
    
    if not data:
        return {"results": [], "count": 0}
    
    keyword = keyword.upper()
    results = [
        {
            "ts_code": item.get("ts_code"),
            "symbol": item.get("ts_code").split(".")[0],
            "name": item.get("name"),
            "area": item.get("area"),
            "industry": item.get("industry"),
            "market": "A股"
        }
        for item in data
        if keyword in item.get("ts_code", "").upper() or 
           keyword in item.get("name", "").upper()
    ]
    
    return {"results": results[:10], "count": len(results[:10])}
