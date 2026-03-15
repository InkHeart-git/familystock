#!/usr/bin/env python3
"""
Tushare 数据同步脚本
用于定时同步股票基础数据到本地数据库
"""

import requests
import sqlite3
from datetime import datetime
import os

# Tushare配置
TUSHARE_API_URL = "http://api.tushare.pro"
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/family_stock.db")


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
            print(f"Tushare API Error: {result.get('msg')}")
            return None
        
        data = result.get("data", {})
        fields_list = data.get("fields", [])
        items = data.get("items", [])
        
        return [dict(zip(fields_list, item)) for item in items]
    except Exception as e:
        print(f"Tushare API调用失败: {e}")
        return None


def init_stocks_table():
    """初始化股票基础信息表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT UNIQUE NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT NOT NULL,
            area TEXT,
            industry TEXT,
            market TEXT,
            list_date TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_symbol ON stocks(symbol)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stocks_industry ON stocks(industry)")
    
    conn.commit()
    conn.close()
    print("✅ 股票表初始化完成")


def sync_stock_basic():
    """同步股票基础信息"""
    print("📊 开始同步股票基础信息...")
    
    # 获取A股基础信息
    stocks = call_tushare_api("stock_basic", {
        "list_status": "L"
    }, "ts_code,name,area,industry,market,list_date")
    
    if not stocks:
        print("❌ 获取股票数据失败")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    updated_count = 0
    inserted_count = 0
    
    for stock in stocks:
        ts_code = stock.get("ts_code")
        symbol = ts_code.split(".")[0] if "." in ts_code else ts_code
        name = stock.get("name")
        area = stock.get("area")
        industry = stock.get("industry")
        market = stock.get("market")
        list_date = stock.get("list_date")
        
        # 检查是否已存在
        cursor.execute("SELECT id FROM stocks WHERE ts_code = ?", (ts_code,))
        existing = cursor.fetchone()
        
        if existing:
            # 更新
            cursor.execute("""
                UPDATE stocks SET 
                    name = ?, area = ?, industry = ?, market = ?, 
                    list_date = ?, is_active = 1, updated_at = ?
                WHERE ts_code = ?
            """, (name, area, industry, market, list_date, datetime.now(), ts_code))
            updated_count += 1
        else:
            # 插入
            cursor.execute("""
                INSERT INTO stocks (ts_code, symbol, name, area, industry, market, list_date)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ts_code, symbol, name, area, industry, market, list_date))
            inserted_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ 股票基础信息同步完成:")
    print(f"   - 新增: {inserted_count} 只")
    print(f"   - 更新: {updated_count} 只")
    print(f"   - 总计: {len(stocks)} 只")
    return True


def sync_daily_quotes():
    """同步今日行情数据"""
    print("📈 开始同步今日行情...")
    
    today = datetime.now().strftime("%Y%m%d")
    
    # 获取日线数据
    quotes = call_tushare_api("daily", {
        "trade_date": today
    }, "ts_code,open,high,low,close,pre_close,change,pct_chg,vol,amount")
    
    if not quotes:
        print("⚠️ 今日行情数据暂未更新或获取失败")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建行情表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code TEXT NOT NULL,
            trade_date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            pre_close REAL,
            change REAL,
            pct_chg REAL,
            volume REAL,
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ts_code, trade_date)
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_date ON daily_quotes(trade_date)")
    
    count = 0
    for quote in quotes:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO daily_quotes 
                (ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quote.get("ts_code"),
                quote.get("trade_date"),
                quote.get("open"),
                quote.get("high"),
                quote.get("low"),
                quote.get("close"),
                quote.get("pre_close"),
                quote.get("change"),
                quote.get("pct_chg"),
                quote.get("vol"),
                quote.get("amount")
            ))
            count += 1
        except Exception as e:
            print(f"插入数据失败: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ 今日行情同步完成: {count} 条记录")
    return True


def get_sync_stats():
    """获取同步统计信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 股票总数
    cursor.execute("SELECT COUNT(*) FROM stocks")
    stock_count = cursor.fetchone()[0]
    
    # 今日行情记录数
    today = datetime.now().strftime("%Y%m%d")
    try:
        cursor.execute("SELECT COUNT(*) FROM daily_quotes WHERE trade_date = ?", (today,))
        quote_count = cursor.fetchone()[0]
    except:
        quote_count = 0
    
    # 行业分布
    cursor.execute("SELECT industry, COUNT(*) FROM stocks WHERE is_active = 1 GROUP BY industry ORDER BY COUNT(*) DESC LIMIT 10")
    industries = cursor.fetchall()
    
    conn.close()
    
    print("\n📊 同步统计:")
    print(f"   - 股票总数: {stock_count}")
    print(f"   - 今日行情: {quote_count}")
    print(f"   - 前10行业:")
    for industry, count in industries:
        print(f"     • {industry}: {count}只")


def main():
    """主函数"""
    print("="*50)
    print(f"Tushare数据同步 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*50)
    
    # 初始化表
    init_stocks_table()
    
    # 同步股票基础信息
    sync_stock_basic()
    
    # 同步今日行情
    sync_daily_quotes()
    
    # 显示统计
    get_sync_stats()
    
    print("\n✅ 数据同步任务完成!")
    print("="*50)


if __name__ == "__main__":
    main()
