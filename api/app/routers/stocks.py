"""
股票数据API路由
提供实时股票数据接口
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import aiohttp
import asyncio
from datetime import datetime

router = APIRouter()

# 腾讯财经API - 实时股票数据
TENCENT_STOCK_API = "https://qt.gtimg.cn/q={codes}"

# 股票代码映射
STOCK_CODES = {
    # A股 - 消费
    "600519": "sh600519",  # 贵州茅台
    "000858": "sz000858",  # 五粮液
    "000568": "sz000568",  # 泸州老窖
    "600887": "sh600887",  # 伊利股份
    "002714": "sz002714",  # 牧原股份
    
    # A股 - 科技
    "002594": "sz002594",  # 比亚迪
    "002415": "sz002415",  # 海康威视
    "000725": "sz000725",  # 京东方A
    "002230": "sz002230",  # 科大讯飞
    "603501": "sh603501",  # 韦尔股份
    
    # A股 - 金融
    "600036": "sh600036",  # 招商银行
    "000001": "sz000001",  # 平安银行
    "601318": "sh601318",  # 中国平安
    "600030": "sh600030",  # 中信证券
    "601398": "sh601398",  # 工商银行
    
    # A股 - 医疗
    "600276": "sh600276",  # 恒瑞医药
    "300760": "sz300760",  # 迈瑞医疗
    "603259": "sh603259",  # 药明康德
    "300015": "sz300015",  # 爱尔眼科
    "000538": "sz000538",  # 云南白药
    
    # A股 - 能源
    "300750": "sz300750",  # 宁德时代
    "601012": "sh601012",  # 隆基绿能
    "002460": "sz002460",  # 赣锋锂业
    "600900": "sh600900",  # 长江电力
    "601857": "sh601857",  # 中国石油
    
    # 港股
    "00700": "hk00700",    # 腾讯控股
    "03690": "hk03690",    # 美团
    "09988": "hk09988",    # 阿里巴巴
    "01810": "hk01810",    # 小米集团
    "09618": "hk09618",    # 京东集团
}

# 板块映射
SECTOR_MAP = {
    "600519": "consumer", "000858": "consumer", "000568": "consumer", "600887": "consumer", "002714": "consumer",
    "002594": "tech", "002415": "tech", "000725": "tech", "002230": "tech", "603501": "tech",
    "600036": "finance", "000001": "finance", "601318": "finance", "600030": "finance", "601398": "finance",
    "600276": "healthcare", "300760": "healthcare", "603259": "healthcare", "300015": "healthcare", "000538": "healthcare",
    "300750": "energy", "601012": "energy", "002460": "energy", "600900": "energy", "601857": "energy",
    "00700": "tech", "03690": "tech", "09988": "tech", "01810": "tech", "09618": "tech",
}

SECTOR_NAMES = {
    "consumer": "消费",
    "tech": "科技", 
    "finance": "金融",
    "healthcare": "医疗",
    "energy": "能源"
}


async def fetch_tencent_stock_data(codes: str) -> dict:
    """从腾讯财经获取股票数据"""
    url = TENCENT_STOCK_API.format(codes=codes)
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    text = await response.text()
                    return parse_tencent_response(text)
                else:
                    return {}
        except Exception as e:
            print(f"获取股票数据失败: {e}")
            return {}


def parse_tencent_response(text: str) -> List[dict]:
    """解析腾讯财经返回的数据"""
    stocks = []
    lines = text.strip().split(';')
    
    for line in lines:
        if not line.strip():
            continue
            
        # 解析 v_code="data" 格式
        match = __import__('re').match(r'v_(\w+)="([^"]*)"', line.strip())
        if match:
            code = match.group(1)
            data_str = match.group(2)
            data_parts = data_str.split('~')
            
            if len(data_parts) > 45:
                try:
                    stock = {
                        "symbol": code.replace('sh', '').replace('sz', '').replace('hk', ''),
                        "name": data_parts[1],
                        "price": float(data_parts[3]) if data_parts[3] else 0,
                        "change": float(data_parts[4]) if data_parts[4] else 0,
                        "changePercent": float(data_parts[5]) if data_parts[5] else 0,
                        "volume": int(data_parts[6]) if data_parts[6] else 0,
                        "turnover": float(data_parts[37]) if len(data_parts) > 37 and data_parts[37] else 0,
                        "marketCap": float(data_parts[45]) if len(data_parts) > 45 and data_parts[45] else 0,
                        "pe": float(data_parts[39]) if len(data_parts) > 39 and data_parts[39] else 0,
                        "pb": float(data_parts[46]) if len(data_parts) > 46 and data_parts[46] else 0,
                        "high": float(data_parts[33]) if len(data_parts) > 33 and data_parts[33] else 0,
                        "low": float(data_parts[34]) if len(data_parts) > 34 and data_parts[34] else 0,
                        "open": float(data_parts[5]) if len(data_parts) > 5 and data_parts[5] else 0,
                        "prevClose": float(data_parts[4]) if len(data_parts) > 4 and data_parts[4] else 0,
                        "sector": SECTOR_MAP.get(code.replace('sh', '').replace('sz', '').replace('hk', ''), 'other'),
                        "sectorName": SECTOR_NAMES.get(SECTOR_MAP.get(code.replace('sh', '').replace('sz', '').replace('hk', ''), 'other'), '其他'),
                        "updateTime": datetime.now().isoformat()
                    }
                    # 计算AI评分 (模拟算法)
                    stock["aiScore"] = calculate_ai_score(stock)
                    stocks.append(stock)
                except (ValueError, IndexError) as e:
                    continue
    
    return stocks


def calculate_ai_score(stock: dict) -> int:
    """计算AI评分 (0-100)"""
    score = 50  # 基础分
    
    # 根据涨跌幅调整
    change_pct = stock.get("changePercent", 0)
    if change_pct > 5:
        score += 20
    elif change_pct > 2:
        score += 10
    elif change_pct > 0:
        score += 5
    elif change_pct < -5:
        score -= 15
    elif change_pct < -2:
        score -= 8
    
    # 根据市盈率调整
    pe = stock.get("pe", 0)
    if 10 < pe < 30:
        score += 10
    elif pe > 100 or pe < 0:
        score -= 10
    
    # 根据市净率调整
    pb = stock.get("pb", 0)
    if 1 < pb < 5:
        score += 5
    elif pb > 10:
        score -= 5
    
    # 确保在0-100范围内
    return max(0, min(100, score))


@router.get("/list")
async def get_stock_list(
    sector: Optional[str] = Query(None, description="板块筛选: consumer/tech/finance/healthcare/energy"),
    limit: int = Query(50, ge=1, le=100)
):
    """获取股票列表"""
    codes = ','.join(STOCK_CODES.values())
    stocks = await fetch_tencent_stock_data(codes)
    
    if sector:
        stocks = [s for s in stocks if s.get("sector") == sector]
    
    return {
        "code": 0,
        "message": "success",
        "data": stocks[:limit],
        "total": len(stocks),
        "updateTime": datetime.now().isoformat()
    }


@router.get("/search")
async def search_stock(
    keyword: str = Query(..., min_length=1, description="股票代码或名称")
):
    """搜索股票"""
    codes = ','.join(STOCK_CODES.values())
    stocks = await fetch_tencent_stock_data(codes)
    
    # 模糊匹配
    keyword = keyword.lower()
    results = [
        s for s in stocks 
        if keyword in s.get("symbol", "").lower() 
        or keyword in s.get("name", "").lower()
    ]
    
    return {
        "code": 0,
        "message": "success",
        "data": results,
        "total": len(results)
    }


@router.get("/detail/{symbol}")
async def get_stock_detail(symbol: str):
    """获取股票详情"""
    code = STOCK_CODES.get(symbol)
    if not code:
        raise HTTPException(status_code=404, detail="股票代码不存在")
    
    stocks = await fetch_tencent_stock_data(code)
    
    if not stocks:
        raise HTTPException(status_code=404, detail="获取股票数据失败")
    
    return {
        "code": 0,
        "message": "success",
        "data": stocks[0]
    }


@router.get("/realtime/{symbols}")
async def get_realtime_quotes(symbols: str):
    """获取实时行情 (支持多股票，用逗号分隔)"""
    symbol_list = symbols.split(',')
    codes = []
    
    for s in symbol_list:
        code = STOCK_CODES.get(s.strip())
        if code:
            codes.append(code)
    
    if not codes:
        raise HTTPException(status_code=400, detail="无效的股票代码")
    
    stocks = await fetch_tencent_stock_data(','.join(codes))
    
    return {
        "code": 0,
        "message": "success",
        "data": stocks,
        "updateTime": datetime.now().isoformat()
    }
