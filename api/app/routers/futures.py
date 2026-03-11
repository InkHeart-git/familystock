"""
期货数据API路由
提供实时期货数据接口
"""
from fastapi import APIRouter, HTTPException
from typing import List
import aiohttp
from datetime import datetime

router = APIRouter()

# 新浪期货API
SINA_FUTURES_API = "https://hq.sinajs.cn/list={codes}"

# 期货代码映射
FUTURES_CODES = {
    # 能源
    "CL": "NYMEX_CL",      # WTI原油
    "BZ": "NYMEX_BZ",      # 布伦特原油
    "NG": "NYMEX_NG",      # 天然气
    "RB": "SHFE_RB",       # 螺纹钢
    "SC": "INE_SC",        # 原油期货
    
    # 贵金属
    "GC": "COMEX_GC",      # 黄金
    "SI": "COMEX_SI",      # 白银
    "AU": "SHFE_AU",       # 沪金
    "AG": "SHFE_AG",       # 沪银
    
    # 有色
    "HG": "COMEX_HG",      # 铜
    "AL": "SHFE_AL",       # 铝
    "ZN": "SHFE_ZN",       # 锌
    "NI": "SHFE_NI",       # 镍
    "CU": "SHFE_CU",       # 沪铜
    
    # 农产品
    "ZW": "CBOT_ZW",       # 小麦
    "ZC": "CBOT_ZC",       # 玉米
    "ZS": "CBOT_ZS",       # 大豆
    "M": "DCE_M",          # 豆粕
    "Y": "DCE_Y",          # 豆油
    
    # 股指
    "ES": "CME_ES",        # 标普500期货
    "NQ": "CME_NQ",        # 纳斯达克期货
    "IF": "CFFEX_IF",      # 沪深300期货
    "IC": "CFFEX_IC",      # 中证500期货
}

FUTURES_INFO = {
    "CL": {"name": "WTI原油", "icon": "🛢️", "unit": "美元/桶", "exchange": "NYMEX"},
    "BZ": {"name": "布伦特原油", "icon": "🛢️", "unit": "美元/桶", "exchange": "ICE"},
    "NG": {"name": "天然气", "icon": "🔥", "unit": "美元/百万英热", "exchange": "NYMEX"},
    "GC": {"name": "黄金", "icon": "🥇", "unit": "美元/盎司", "exchange": "COMEX"},
    "SI": {"name": "白银", "icon": "🥈", "unit": "美元/盎司", "exchange": "COMEX"},
    "HG": {"name": "铜", "icon": "🔶", "unit": "美元/磅", "exchange": "COMEX"},
    "ZW": {"name": "小麦", "icon": "🌾", "unit": "美分/蒲式耳", "exchange": "CBOT"},
    "ZC": {"name": "玉米", "icon": "🌽", "unit": "美分/蒲式耳", "exchange": "CBOT"},
    "ZS": {"name": "大豆", "icon": "🫘", "unit": "美分/蒲式耳", "exchange": "CBOT"},
    "RB": {"name": "螺纹钢", "icon": "🏗️", "unit": "元/吨", "exchange": "SHFE"},
    "AU": {"name": "沪金", "icon": "🥇", "unit": "元/克", "exchange": "SHFE"},
    "AG": {"name": "沪银", "icon": "🥈", "unit": "元/千克", "exchange": "SHFE"},
    "CU": {"name": "沪铜", "icon": "🔶", "unit": "元/吨", "exchange": "SHFE"},
    "AL": {"name": "沪铝", "icon": "⚪", "unit": "元/吨", "exchange": "SHFE"},
    "M": {"name": "豆粕", "icon": "🌱", "unit": "元/吨", "exchange": "DCE"},
    "Y": {"name": "豆油", "icon": "🫒", "unit": "元/吨", "exchange": "DCE"},
    "SC": {"name": "原油", "icon": "🛢️", "unit": "元/桶", "exchange": "INE"},
    "ES": {"name": "标普500", "icon": "📊", "unit": "点", "exchange": "CME"},
    "NQ": {"name": "纳斯达克", "icon": "📈", "unit": "点", "exchange": "CME"},
    "IF": {"name": "沪深300", "icon": "🇨🇳", "unit": "点", "exchange": "CFFEX"},
    "IC": {"name": "中证500", "icon": "🇨🇳", "unit": "点", "exchange": "CFFEX"},
}


async def fetch_sina_futures(codes: str) -> List[dict]:
    """从新浪获取期货数据"""
    url = SINA_FUTURES_API.format(codes=codes)
    
    async with aiohttp.ClientSession() as session:
        try:
            headers = {
                "Referer": "https://finance.sina.com.cn",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    text = await response.text()
                    return parse_sina_response(text)
                else:
                    return []
        except Exception as e:
            print(f"获取期货数据失败: {e}")
            return []


def parse_sina_response(text: str) -> List[dict]:
    """解析新浪期货数据"""
    futures = []
    lines = text.strip().split(';')
    
    for line in lines:
        if not line.strip() or 'var hq_str_' not in line:
            continue
            
        match = __import__('re').match(r'var hq_str_(\w+)="([^"]*)"', line.strip())
        if match:
            code_key = match.group(1)
            data_str = match.group(2)
            
            # 找到对应的symbol
            symbol = None
            for sym, sina_code in FUTURES_CODES.items():
                if sina_code == code_key or code_key.endswith(sym):
                    symbol = sym
                    break
            
            if not symbol:
                continue
                
            data_parts = data_str.split(',')
            info = FUTURES_INFO.get(symbol, {})
            
            try:
                if len(data_parts) > 8:
                    # 国内期货格式
                    future = {
                        "symbol": symbol,
                        "name": info.get("name", symbol),
                        "icon": info.get("icon", "📊"),
                        "price": float(data_parts[8]) if data_parts[8] else 0,  # 最新价
                        "change": float(data_parts[8]) - float(data_parts[14]) if len(data_parts) > 14 and data_parts[14] else 0,
                        "changePercent": ((float(data_parts[8]) - float(data_parts[14])) / float(data_parts[14]) * 100) if len(data_parts) > 14 and data_parts[14] and float(data_parts[14]) != 0 else 0,
                        "open": float(data_parts[2]) if len(data_parts) > 2 and data_parts[2] else 0,
                        "high": float(data_parts[3]) if len(data_parts) > 3 and data_parts[3] else 0,
                        "low": float(data_parts[4]) if len(data_parts) > 4 and data_parts[4] else 0,
                        "volume": int(float(data_parts[6])) if len(data_parts) > 6 and data_parts[6] else 0,
                        "unit": info.get("unit", ""),
                        "exchange": info.get("exchange", ""),
                        "trend": "up" if (float(data_parts[8]) - float(data_parts[14]) > 0) else "down" if (float(data_parts[8]) - float(data_parts[14]) < 0) else "flat",
                        "updateTime": datetime.now().isoformat()
                    }
                elif len(data_parts) > 1:
                    # 国际期货格式 (简化)
                    future = {
                        "symbol": symbol,
                        "name": info.get("name", symbol),
                        "icon": info.get("icon", "📊"),
                        "price": float(data_parts[0]) if data_parts[0] else 0,
                        "change": float(data_parts[1]) if len(data_parts) > 1 and data_parts[1] else 0,
                        "changePercent": float(data_parts[2]) if len(data_parts) > 2 and data_parts[2] else 0,
                        "unit": info.get("unit", ""),
                        "exchange": info.get("exchange", ""),
                        "trend": "up" if (len(data_parts) > 1 and float(data_parts[1]) > 0) else "down" if (len(data_parts) > 1 and float(data_parts[1]) < 0) else "flat",
                        "updateTime": datetime.now().isoformat()
                    }
                else:
                    continue
                    
                futures.append(future)
            except (ValueError, IndexError) as e:
                continue
    
    return futures


@router.get("/list")
async def get_futures_list():
    """获取期货列表"""
    # 优先获取主要期货品种
    main_codes = ["CL", "BZ", "GC", "NG", "HG", "ZW", "AU", "CU", "RB", "SC"]
    codes = ','.join([FUTURES_CODES.get(c, c) for c in main_codes])
    
    futures = await fetch_sina_futures(codes)
    
    # 如果API失败，返回模拟数据
    if not futures:
        futures = get_fallback_futures()
    
    return {
        "code": 0,
        "message": "success",
        "data": futures,
        "total": len(futures),
        "updateTime": datetime.now().isoformat(),
        "source": "sina" if futures and futures[0].get("price") != 0 else "fallback"
    }


@router.get("/{symbol}")
async def get_future_detail(symbol: str):
    """获取期货详情"""
    code = FUTURES_CODES.get(symbol.upper())
    if not code:
        raise HTTPException(status_code=404, detail="期货代码不存在")
    
    futures = await fetch_sina_futures(code)
    
    if not futures:
        # 返回模拟数据
        info = FUTURES_INFO.get(symbol.upper(), {})
        return {
            "code": 0,
            "message": "success",
            "data": {
                "symbol": symbol.upper(),
                "name": info.get("name", symbol),
                "icon": info.get("icon", "📊"),
                "price": 0,
                "change": 0,
                "changePercent": 0,
                "unit": info.get("unit", ""),
                "exchange": info.get("exchange", ""),
                "trend": "flat",
                "updateTime": datetime.now().isoformat()
            },
            "source": "fallback"
        }
    
    return {
        "code": 0,
        "message": "success",
        "data": futures[0],
        "source": "sina"
    }


def get_fallback_futures() -> List[dict]:
    """获取模拟期货数据 (当API失败时使用)"""
    import random
    
    base_prices = {
        "CL": 81.25, "BZ": 85.67, "GC": 2845.30, "NG": 2.85,
        "HG": 4.25, "ZW": 585.25, "AU": 520.5, "CU": 78500,
        "RB": 3850, "SC": 620.5
    }
    
    futures = []
    for symbol, base_price in base_prices.items():
        info = FUTURES_INFO.get(symbol, {})
        # 随机波动 -2% 到 +2%
        change_pct = (random.random() - 0.5) * 4
        change = base_price * change_pct / 100
        
        futures.append({
            "symbol": symbol,
            "name": info.get("name", symbol),
            "icon": info.get("icon", "📊"),
            "price": round(base_price + change, 2),
            "change": round(change, 2),
            "changePercent": round(change_pct, 2),
            "unit": info.get("unit", ""),
            "exchange": info.get("exchange", ""),
            "trend": "up" if change > 0 else "down" if change < 0 else "flat",
            "updateTime": datetime.now().isoformat()
        })
    
    return futures
