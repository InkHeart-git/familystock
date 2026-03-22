#!/usr/bin/env python3
"""
将生产环境PostgreSQL数据同步到测试环境SQLite
同步内容：
- stock_cache (PostgreSQL) -> stock_quotes (SQLite)
- index_cache (PostgreSQL) -> index_quotes (SQLite)
"""

import psycopg2
import sqlite3
from psycopg2.extras import RealDictCursor
import time

# 生产环境PostgreSQL配置
PROD_CONFIG = {
    'host': 'localhost',
    'dbname': 'minirock',
    'user': 'minirock',
    'password': 'minirock123',
    'port': 5432
}

# 测试环境SQLite路径
TEST_DB_PATH = '/var/www/familystock-test/api/data/family_stock.db'

def connect_prod():
    """连接生产环境PostgreSQL"""
    conn = psycopg2.connect(**PROD_CONFIG)
    return conn

def connect_test():
    """连接测试环境SQLite"""
    conn = sqlite3.connect(TEST_DB_PATH)
    return conn

def sync_stock_cache(prod_conn, test_conn):
    """同步股票行情数据"""
    print("🚀 开始同步 stock_cache -> stock_quotes ...")
    
    with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT symbol, ts_code, open, high, low, close, pct_chg, 
                   volume, amount, market, currency, cached_at 
            FROM stock_cache
        """)
        rows = cur.fetchall()
        print(f"📊 从生产环境读取 {len(rows)} 只股票")
    
    # 清空测试环境stock_quotes
    test_cur = test_conn.cursor()
    test_cur.execute("DELETE FROM stock_quotes")
    test_conn.commit()
    
    # 插入数据
    inserted = 0
    failed = 0
    for row in rows:
        try:
            trade_date = row['cached_at'].strftime('%Y%m%d') if row['cached_at'] else None
            test_cur.execute("""
                INSERT OR REPLACE INTO stock_quotes 
                (symbol, ts_code, trade_date, open, high, low, close, pct_chg, vol, amount, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                row['symbol'], row['ts_code'], trade_date,
                float(row['open']) if row['open'] is not None else 0,
                float(row['high']) if row['high'] is not None else 0,
                float(row['low']) if row['low'] is not None else 0,
                float(row['close']) if row['close'] is not None else 0,
                float(row['pct_chg']) if row['pct_chg'] is not None else 0,
                float(row['volume']) if row['volume'] is not None else 0,
                float(row['amount']) if row['amount'] is not None else 0
            ))
            inserted += 1
            
            if inserted % 500 == 0:
                test_conn.commit()
                print(f"  已插入 {inserted}/{len(rows)} ...")
                
        except Exception as e:
            failed += 1
            if failed <= 10:  # 只打印前10个错误避免刷屏
                print(f"  ❌ 插入失败 {row['symbol']}: {e}")
            continue
    
    test_conn.commit()
    print(f"✅ 股票行情同步完成，成功插入 {inserted} 只，失败 {failed} 只")
    return inserted

def sync_index_cache(prod_conn, test_conn):
    """同步大盘指数数据"""
    print("\n🚀 开始同步 index_cache -> index_quotes ...")
    
    with prod_conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT symbol, ts_code, name, open, high, low, close, pct_chg, 
                   volume, amount, market, trade_date, cached_at 
            FROM index_cache
        """)
        rows = cur.fetchall()
        print(f"📊 从生产环境读取 {len(rows)} 只指数")
    
    # 清空测试环境index_quotes
    test_cur = test_conn.cursor()
    test_cur.execute("DELETE FROM index_quotes")
    test_conn.commit()
    
    # 插入数据
    inserted = 0
    failed = 0
    for row in rows:
        try:
            # 测试环境表结构:
            # 0:id, 1:ts_code, 2:symbol, 3:name, 4:market, 5:trade_date
            # 6:open, 7:high, 8:low, 9:close, 10:pre_close, 11:change, 12:pct_chg
            # 13:vol, 14:amount, 15:updated_at
            #
            # SQL 参数占位符数量 = 列数 - 1 (id自增) = 15
            test_cur.execute("""
                INSERT OR REPLACE INTO index_quotes 
                (ts_code, symbol, name, market, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                row['ts_code'], row['symbol'], row['name'], row['market'], str(row['trade_date']),
                float(row['open']) if row['open'] is not None else 0,
                float(row['high']) if row['high'] is not None else 0,
                float(row['low']) if row['low'] is not None else 0,
                float(row['close']) if row['close'] is not None else 0,
                float(row['pct_chg']) if row['pct_chg'] is not None else 0,
                float(row['volume']) if row['volume'] is not None else 0,
                float(row['amount']) if row['amount'] is not None else 0
            ))
            inserted += 1
            
        except Exception as e:
            failed += 1
            print(f"  ❌ 插入失败 {row['symbol']}: {e}")
            continue
    
    test_conn.commit()
    print(f"✅ 指数同步完成，成功插入 {inserted} 只，失败 {failed} 只")
    return inserted

def main():
    """主函数"""
    print("=" * 60)
    print("🔄 生产环境 → 测试环境 数据同步")
    print(f"📦 生产: PostgreSQL minirock (stock_cache + index_cache)")
    print(f"🧪 测试: SQLite {TEST_DB_PATH} (stock_quotes + index_quotes)")
    print("=" * 60)
    
    start_time = time.time()
    
    prod_conn = connect_prod()
    test_conn = connect_test()
    
    try:
        stocks_count = sync_stock_cache(prod_conn, test_conn)
        index_count = sync_index_cache(prod_conn, test_conn)
        
        elapsed = time.time() - start_time
        print("\n" + "=" * 60)
        print("🎉 同步完成!")
        print(f"📊 股票行情: {stocks_count} 只")
        print(f"📊 大盘指数: {index_count} 只")
        print(f"⏱️  耗时: {elapsed:.2f} 秒")
        print("=" * 60)
        
    finally:
        prod_conn.close()
        test_conn.close()

if __name__ == "__main__":
    main()
