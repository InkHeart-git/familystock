"""
Tushare API扩展模块
添加到server_v3.py中使用
"""

import requests
from datetime import datetime, timedelta

TUSHARE_API_URL = "http://api.tushare.pro"
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"


def call_tushare_api(api_name, params=None, fields=""):
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


def get_tushare_stock_quote(ts_code):
    """获取股票最新行情"""
    if "." not in ts_code:
        if ts_code.startswith("6"):
            ts_code = f"{ts_code}.SH"
        else:
            ts_code = f"{ts_code}.SZ"
    
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
    
    data = call_tushare_api("daily", {
        "ts_code": ts_code,
        "start_date": start_date,
        "end_date": end_date
    })
    
    if not data:
        return None
    
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
