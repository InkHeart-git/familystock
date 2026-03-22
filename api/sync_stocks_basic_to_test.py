#!/usr/bin/env python3
"""
同步MySQL stocks基础数据到测试环境SQLite
适配测试环境现有stock_basic表结构
"""

import mysql.connector
import sqlite3
from mysql.connector import Error

# MySQL配置 - 使用debian-sys-maint
MYSQL_CONFIG = {
    'host': 'localhost',
    'database': 'familystock',
    'user': 'debian-sys-maint',
    'password': 'Bc9aUe8l2wO4iQmq'
}

# 测试环境SQLite路径
TEST_DB_PATH = '/var/www/familystock-test/api/data/family_stock.db'

def connect_mysql():
    """连接MySQL"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"❌ MySQL连接失败: {e}")
        return None

def connect_test():
    """连接测试环境SQLite"""
    conn = sqlite3.connect(TEST_DB_PATH)
    return conn

def sync_stocks_basic():
    """同步stocks基础数据"""
    print("🚀 开始同步MySQL stocks -> 测试SQLite stock_basic...")
    
    mysql_conn = connect_mysql()
    if not mysql_conn:
        return 0
    
    test_conn = connect_test()
    test_cur = test_conn.cursor()
    
    try:
        # 读取所有stocks
        cursor = mysql_conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT code, name, industry, price, change_percent, market, market_type 
            FROM stocks
        """)
        rows = cursor.fetchall()
        print(f"📊 从MySQL读取 {len(rows)} 条股票基础数据")
        
        # 统计ETF/LOF/债券
        etf_count = sum(1 for r in rows if r['name'] and 'ETF' in r['name'])
        lof_count = sum(1 for r in rows if r['name'] and 'LOF' in r['name'])
        bond_count = sum(1 for r in rows if r['name'] and ('债' in r['name'] or 'Bond' in r['name'].upper()))
        print(f"📊 统计结果:")
        print(f"   ETF: {etf_count} 只")
        print(f"   LOF: {lof_count} 只")
        print(f"   债券相关: {bond_count} 只")
        
        # 清空测试环境stock_basic
        test_cur.execute("DELETE FROM stock_basic;")
        test_conn.commit()
        print(f"🧹 已清空原有数据")
        
        # 插入数据 - 适配测试环境表结构:
        # ts_code, symbol, name, area, industry, market, list_date
        # 我们这里: symbol = code, ts_code = code + .SH/.SZ 根据market
        inserted = 0
        failed = 0
        for row in rows:
            try:
                code = row['code']
                market = row['market'] if row['market'] else 'sh'
                if market == 'sh':
                    ts_code = f"{code}.SH"
                elif market == 'sz':
                    ts_code = f"{code}.SZ"
                else:
                    ts_code = f"{code}.{market.upper()}"
                
                test_cur.execute("""
                    INSERT INTO stock_basic 
                    (ts_code, symbol, name, industry, market)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    ts_code, code, row['name'], row['industry'], market
                ))
                inserted += 1
            except Exception as e:
                failed += 1
                if failed <= 10:
                    print(f"  ❌ 插入失败 {row['code']}: {e}")
                continue
        
        test_conn.commit()
        print(f"✅ 同步完成: 成功 {inserted}, 失败 {failed}")
        
        # 验证结果
        test_cur.execute("SELECT COUNT(*) FROM stock_basic;")
        count = test_cur.fetchone()[0]
        print(f"📊 验证: stock_basic 现在有 {count} 条记录")
        
        # 再验证一下ETF
        test_cur.execute("SELECT COUNT(*) FROM stock_basic WHERE name LIKE '%ETF%';")
        etf_count_after = test_cur.fetchone()[0]
        print(f"📊 ETF: {etf_count_after} 条")
        
        return inserted
        
    finally:
        if mysql_conn.is_connected():
            mysql_conn.close()
        test_conn.close()

def main():
    print("=" * 60)
    print("🔄 MySQL stocks 基础数据 -> 测试SQLite stock_basic 同步")
    print(f"🧪 目标: {TEST_DB_PATH}")
    print("=" * 60)
    
    total = sync_stocks_basic()
    
    print("\n" + "=" * 60)
    print(f"🎉 完成，共同步 {total} 只股票基础信息")
    print("现在测试环境应该包含所有ETF/LOF/债券数据了，可以搜索添加")
    print("=" * 60)

if __name__ == "__main__":
    main()
