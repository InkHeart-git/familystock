"""
MiniRock股票缓存服务
定时更新股票数据到缓存表
"""

import threading
import time
from datetime import datetime, timedelta
from database import cache_stock_data, get_cached_stock
from tushare_helper import call_tushare_api

# 默认关注的股票列表
DEFAULT_STOCKS = [
    '600519',  # 贵州茅台
    '000858',  # 五粮液
    '000568',  # 泸州老窖
    '000651',  # 格力电器
    '000725',  # 京东方A
    '002230',  # 科大讯飞
    '002415',  # 海康威视
    '002594',  # 比亚迪
    '300750',  # 宁德时代
    '601318',  # 中国平安
    '600036',  # 招商银行
]

# 缓存线程
_cache_thread = None
_stop_cache = False


def calculate_ai_score(pct_chg):
    """计算AI评分"""
    score = 50
    
    if pct_chg > 5:
        score += 15
    elif pct_chg > 2:
        score += 10
    elif pct_chg > 0:
        score += 5
    elif pct_chg < -5:
        score -= 15
    elif pct_chg < -2:
        score -= 10
    elif pct_chg < 0:
        score -= 5
    
    return max(0, min(100, score))


def update_single_stock(symbol):
    """更新单只股票缓存"""
    try:
        # 添加后缀
        if '.' not in symbol:
            if symbol.startswith('6'):
                ts_code = f"{symbol}.SH"
            else:
                ts_code = f"{symbol}.SZ"
        else:
            ts_code = symbol
            symbol = symbol.split('.')[0]
        
        # 获取最新数据
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
        
        data = call_tushare_api("daily", {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date
        })
        
        if not data or len(data) == 0:
            print(f"未获取到{symbol}的数据")
            return False
        
        latest = data[-1]
        pct_chg = float(latest.get("pct_chg", 0))
        
        # 准备缓存数据
        stock_data = {
            'symbol': symbol,
            'ts_code': ts_code,
            'name': symbol,  # 可以从stock_basic获取完整名称
            'close': float(latest.get("close", 0)),
            'open': float(latest.get("open", 0)),
            'high': float(latest.get("high", 0)),
            'low': float(latest.get("low", 0)),
            'pct_chg': pct_chg,
            'volume': float(latest.get("vol", 0)),
            'amount': float(latest.get("amount", 0)),
            'market': 'A股',
            'currency': 'CNY',
            'ai_score': calculate_ai_score(pct_chg)
        }
        
        # 缓存到数据库
        success = cache_stock_data(stock_data)
        if success:
            print(f"✅ {symbol} 缓存更新成功: ¥{stock_data['close']} ({pct_chg:+.2f}%)")
        return success
        
    except Exception as e:
        print(f"❌ 更新{symbol}失败: {e}")
        return False


def update_all_stocks(symbols=None):
    """更新所有股票缓存"""
    if symbols is None:
        symbols = DEFAULT_STOCKS
    
    print(f"开始更新{len(symbols)}只股票缓存...")
    success_count = 0
    
    for symbol in symbols:
        if update_single_stock(symbol):
            success_count += 1
        time.sleep(0.5)  # 避免请求过快
    
    print(f"缓存更新完成: {success_count}/{len(symbols)}")
    return success_count


def cache_worker(interval_minutes=5):
    """缓存工作线程"""
    global _stop_cache
    
    print(f"股票缓存服务启动，更新间隔: {interval_minutes}分钟")
    
    # 首次立即更新
    update_all_stocks()
    
    while not _stop_cache:
        # 等待指定时间
        for _ in range(interval_minutes * 60):
            if _stop_cache:
                break
            time.sleep(1)
        
        if not _stop_cache:
            update_all_stocks()


def start_cache_service(interval_minutes=5):
    """启动缓存服务"""
    global _cache_thread, _stop_cache
    
    if _cache_thread and _cache_thread.is_alive():
        print("缓存服务已在运行")
        return False
    
    _stop_cache = False
    _cache_thread = threading.Thread(target=cache_worker, args=(interval_minutes,))
    _cache_thread.daemon = True
    _cache_thread.start()
    
    print(f"✅ 缓存服务已启动")
    return True


def stop_cache_service():
    """停止缓存服务"""
    global _stop_cache
    _stop_cache = True
    print("缓存服务停止信号已发送")


def get_stock_with_cache(symbol, force_update=False):
    """获取股票数据（带缓存）"""
    # 检查缓存
    if not force_update:
        cached = get_cached_stock(symbol)
        if cached:
            # 检查缓存时间（5分钟内有效）
            cached_at = cached.get('cached_at')
            if cached_at and (datetime.now() - cached_at).seconds < 300:
                return dict(cached)
    
    # 更新缓存
    if update_single_stock(symbol):
        return get_cached_stock(symbol)
    
    return None


# ==================== 测试 ====================

if __name__ == '__main__':
    print("测试股票缓存服务...")
    
    # 测试单只股票更新
    update_single_stock('600519')
    
    # 测试批量更新
    # update_all_stocks(['600519', '000858'])
    
    # 测试带缓存获取
    # data = get_stock_with_cache('600519')
    # print(f"缓存数据: {data}")
