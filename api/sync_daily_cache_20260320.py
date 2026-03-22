#!/usr/bin/env python3
"""
同步每日行情到PostgreSQL缓存 - 指定日期版
同步2026年3月20日数据
"""

import tushare as ts
import psycopg2
from psycopg2.extras import RealDictCursor
import time
from datetime import datetime
import numpy as np

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# PostgreSQL配置
DB_CONFIG = {
    'host': 'localhost',
    'dbname': 'minirock',
    'user': 'minirock',
    'password': 'minirock123',
    'port': 5432
}

# 主要指数列表
MAJOR_INDICES = [
    ('000001.SH', '上证指数'),
    ('399001.SZ', '深证成指'),
    ('399006.SZ', '创业板指'),
    ('000016.SH', '上证50'),
    ('000300.SH', '沪深300'),
    ('000905.SH', '中证500'),
    ('513100.SH', '纳指ETF'),
    ('513050.SH', '中概互联'),
]

def connect_db():
    """连接数据库"""
    conn = psycopg2.connect(**DB_CONFIG)
    return conn

def sync_daily_quote(conn, trade_date):
    """同步每日行情到stock_cache"""
    print(f"🚀 开始同步 {trade_date} 行情数据...")
    
    # 获取今日所有交易股票的日线数据
    try:
        df = pro.daily(trade_date=trade_date)
        print(f"📊 获取到 {len(df)} 条行情记录")
    except Exception as e:
        print(f"❌ 获取行情失败: {e}")
        return 0
    
    success_count = 0
    for _, row in df.iterrows():
        try:
            ts_code = row['ts_code']
            # 转换numpy类型到Python原生类型，处理空值情况
            try:
                open_p = float(row['open']) if not np.isnan(float(row['open'])) else 0
            except:
                open_p = 0
            try:
                high_p = float(row['high']) if not np.isnan(float(row['high'])) else 0
            except:
                high_p = 0
            try:
                low_p = float(row['low']) if not np.isnan(float(row['low'])) else 0
            except:
                low_p = 0
            try:
                close_p = float(row['close']) if not np.isnan(float(row['close'])) else 0
            except:
                close_p = 0
            try:
                pct_chg = float(row['pct_chg']) if not np.isnan(float(row['pct_chg'])) else 0
            except:
                pct_chg = 0
            try:
                vol = float(row['vol']) if not np.isnan(float(row['vol'])) else 0
            except:
                vol = 0
            try:
                amount = float(row['amount']) if not np.isnan(float(row['amount'])) else 0
            except:
                amount = 0
            
            # 提取symbol (不带后缀)
            symbol = ts_code.split('.')[0]
            market = 'SH' if ts_code.endswith('.SH') else 'SZ'
            
            sql = """
                INSERT INTO stock_cache 
                (symbol, ts_code, open, high, low, close, pct_chg, volume, amount, market, currency, cached_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (symbol) DO UPDATE SET
                    ts_code = EXCLUDED.ts_code,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    pct_chg = EXCLUDED.pct_chg,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    market = EXCLUDED.market,
                    currency = EXCLUDED.currency,
                    cached_at = CURRENT_TIMESTAMP
            """
            
            with conn.cursor() as cur:
                cur.execute(sql, (
                    symbol, ts_code, open_p, high_p, low_p, close_p, 
                    pct_chg, vol, amount, market, 'CNY'
                ))
                conn.commit()
            
            success_count += 1
            if success_count % 500 == 0:
                print(f"  已同步 {success_count}/{len(df)} 只...")
            
            # 控制调用频率
            time.sleep(0.01)
            
        except Exception as e:
            print(f"  ❌ 同步失败 {ts_code}: {e}")
            conn.rollback()
            continue
    
    print(f"✅ 行情同步完成，成功 {success_count} 只")
    return success_count

def sync_indices(conn, trade_date):
    """同步大盘指数"""
    print(f"\n🚀 开始同步大盘指数...")
    
    success_count = 0
    for ts_code, name in MAJOR_INDICES:
        try:
            # 获取指数日线
            df = pro.index_daily(ts_code=ts_code, trade_date=trade_date)
            
            if len(df) == 0:
                print(f"  ⚠️ {name} ({ts_code}) 今日无数据")
                continue
            
            row = df.iloc[0]
            open_p = float(row['open']) if not np.isnan(row['open']) else 0
            high_p = float(row['high']) if not np.isnan(row['high']) else 0
            low_p = float(row['low']) if not np.isnan(row['low']) else 0
            close_p = float(row['close']) if not np.isnan(row['close']) else 0
            pct_chg = float(row['pct_chg']) if not np.isnan(row['pct_chg']) else 0
            vol = float(row['vol']) if not np.isnan(row['vol']) else 0
            amount = float(row['amount']) if not np.isnan(row['amount']) else 0
            
            symbol = ts_code.split('.')[0]
            
            symbol = ts_code.split('.')[0]
            market = 'SH' if ts_code.endswith('.SH') else 'SZ'
            
            sql = """
                INSERT INTO index_cache 
                (symbol, ts_code, name, open, high, low, close, pct_chg, volume, amount, market, trade_date, cached_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (symbol) DO UPDATE SET
                    ts_code = EXCLUDED.ts_code,
                    name = EXCLUDED.name,
                    open = EXCLUDED.open,
                    high = EXCLUDED.high,
                    low = EXCLUDED.low,
                    close = EXCLUDED.close,
                    pct_chg = EXCLUDED.pct_chg,
                    volume = EXCLUDED.volume,
                    amount = EXCLUDED.amount,
                    market = EXCLUDED.market,
                    trade_date = EXCLUDED.trade_date,
                    cached_at = CURRENT_TIMESTAMP
            """
            
            with conn.cursor() as cur:
                cur.execute(sql, (
                    symbol, ts_code, name, open_p, high_p, low_p, close_p,
                    pct_chg, vol, amount, market, trade_date
                ))
                conn.commit()
            
            success_count += 1
            print(f"  ✅ {name}: 收盘 {close_p:.2f}, 涨跌幅 {pct_chg:.2f}%")
            
            time.sleep(0.1)
            
        except Exception as e:
            print(f"  ❌ {name} ({ts_code}) 同步失败: {e}")
            conn.rollback()
            continue
    
    print(f"✅ 指数同步完成，成功 {success_count} 只")
    return success_count

def main():
    """主函数"""
    print("=" * 60)
    print("📈 FamilyStock 每日行情同步脚本")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 指定日期: 2026年3月20日
    trade_date = '20260320'
    print(f"📅 同步日期: {trade_date}")
    
    conn = connect_db()
    
    try:
        # 1. 同步今日行情到stock_cache
        success_stocks = sync_daily_quote(conn, trade_date)
        
        # 2. 同步大盘指数
        success_indices = sync_indices(conn, trade_date)
        
        print("\n" + "=" * 60)
        print("🎉 同步完成!")
        print(f"📊 股票行情: {success_stocks} 只")
        print(f"📊 大盘指数: {success_indices} 只")
        print(f"🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)
        
    finally:
        conn.close()

if __name__ == "__main__":
    main()
