#!/usr/bin/env python3
"""
从Tushare Pro获取全量股票基础信息
包含: 股票、ETF、LOF、债券等所有品种
然后导入到MySQL familystock.stocks表
"""

import tushare as ts
import mysql.connector
from mysql.connector import Error
import time
from datetime import datetime

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# MySQL配置
MYSQL_CONFIG = {
    'host': 'localhost',
    'database': 'familystock',
    'user': 'debian-sys-maint',
    'password': 'Bc9aUe8l2wO4iQmq'
}

def connect_mysql():
    """连接MySQL"""
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        if conn.is_connected():
            print("✅ MySQL连接成功")
            return conn
    except Error as e:
        print(f"❌ MySQL连接失败: {e}")
        return None

def get_all_stock_basic():
    """获取全量股票基础信息"""
    print("🚀 从Tushare获取全量股票基础信息...")
    
    # 获取所有上市股票
    # list_status: L上市 D退市 P暂停上市，默认L
    # exchange: 交易所 SSE上交所 SZSE深交所 HKEX港交所
    all_stocks = []
    
    # A股 上交所
    try:
        df_sse = pro.stock_basic(exchange='SSE', list_status='L')
        print(f"📊 上交所: {len(df_sse)} 只")
        all_stocks.append(df_sse)
        time.sleep(0.5)
    except Exception as e:
        print(f"❌ 获取上交所数据失败: {e}")
    
    # A股 深交所
    try:
        df_szse = pro.stock_basic(exchange='SZSE', list_status='L')
        print(f"📊 深交所: {len(df_szse)} 只")
        all_stocks.append(df_szse)
        time.sleep(0.5)
    except Exception as e:
        print(f"❌ 获取深交所数据失败: {e}")
    
    # 港股
    try:
        df_hkex = pro.stock_basic(exchange='HKEX', list_status='L')
        print(f"📊 港交所: {len(df_hkex)} 只")
        all_stocks.append(df_hkex)
        time.sleep(0.5)
    except Exception as e:
        print(f"❌ 获取港交所数据失败: {e}")
    
    # 合并
    import pandas as pd
    if len(all_stocks) == 0:
        return None
    df_all = pd.concat(all_stocks, ignore_index=True)
    print(f"\n📊 总共获取 {len(df_all)} 只上市股票")
    
    # 统计各类型
    # ETF 通常名称包含ETF
    etf_count = df_all[df_all['name'].str.contains('ETF', na=False)].shape[0]
    # LOF 
    lof_count = df_all[df_all['name'].str.contains('LOF', na=False)].shape[0]
    # 债券
    bond_count = df_all[df_all['name'].str.contains('债|Bond', na=False)].shape[0]
    
    print(f"📊 其中: ETF {etf_count}只, LOF {lof_count}只, 债券 {bond_count}只")
    
    return df_all

def import_to_mysql(df_all, mysql_conn):
    """导入数据到MySQL"""
    print("\n🚀 开始导入到MySQL...")
    
    cursor = mysql_conn.cursor()
    
    # 清空原有数据
    cursor.execute("DELETE FROM stocks;")
    mysql_conn.commit()
    print(f"🧹 已清空原有数据")
    
    inserted = 0
    failed = 0
    
    for _, row in df_all.iterrows():
        try:
            ts_code = row['ts_code']
            # 提取code (不带后缀)
            code = ts_code.split('.')[0]
            name = row['name'] if row['name'] else ''
            industry = row['industry'] if 'industry' in row and row['industry'] else None
            market_type = 'A股'
            if '.SH' in ts_code:
                market = 'sh'
                if 'HK' in ts_code:
                    market_type = '港股'
            elif '.SZ' in ts_code:
                market = 'sz'
            elif '.HK' in ts_code:
                market = 'hk'
                market_type = '港股'
            else:
                market = ts_code.split('.')[-1].lower()
                market_type = market
            
            sql = """
                INSERT INTO stocks 
                (code, name, industry, price, change_percent, market, market_type)
                VALUES (%s, %s, %s, 0, 0, %s, %s)
            """
            
            cursor.execute(sql, (code, name, industry, market, market_type))
            inserted += 1
            
            if inserted % 500 == 0:
                mysql_conn.commit()
                print(f"  已插入 {inserted}/{len(df_all)} ...")
                
        except Exception as e:
            failed += 1
            if failed <= 10:
                print(f"  ❌ 插入失败 {ts_code}: {e}")
            continue
    
    mysql_conn.commit()
    print(f"\n✅ 导入完成: 成功 {inserted}, 失败 {failed}")
    
    # 查询最终计数
    cursor.execute("SELECT COUNT(*) FROM stocks;")
    count = cursor.fetchone()[0]
    print(f"📊 验证: stocks 表现在有 {count} 条记录")
    
    # 统计ETF
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE name LIKE '%ETF%';")
    etf_count = cursor.fetchone()[0]
    print(f"📊 ETF: {etf_count} 条")
    
    # 统计LOF
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE name LIKE '%LOF%';")
    lof_count = cursor.fetchone()[0]
    print(f"📊 LOF: {lof_count} 条")
    
    # 统计债券
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE name LIKE '%债%' OR name LIKE '%Bond%';")
    bond_count = cursor.fetchone()[0]
    print(f"📊 债券: {bond_count} 条")
    
    return inserted

def main():
    print("=" * 70)
    print("📥 Tushare Pro 全量股票基础信息获取 & 导入MySQL")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    mysql_conn = connect_mysql()
    if not mysql_conn:
        return
    
    df_all = get_all_stock_basic()
    if df_all is None or len(df_all) == 0:
        print("❌ 获取数据失败")
        mysql_conn.close()
        return
    
    total = import_to_mysql(df_all, mysql_conn)
    
    mysql_conn.close()
    
    print("\n" + "=" * 70)
    print(f"🎉 完成！总共导入 {total} 只股票基础信息")
    print("现在包含了所有ETF、LOF、债券等品种")
    print(f"🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
