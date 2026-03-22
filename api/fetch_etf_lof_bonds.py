#!/usr/bin/env python3
"""
获取ETF、LOF、债券基金等品种，并追加到MySQL stocks表中
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

def get_fund_basic():
    """获取基金基础信息 (ETF/LOF/债券)"""
    print("🚀 从Tushare获取基金基础信息...")
    
    all_funds = []
    
    # 获取ETF
    try:
        # 交易所  E交易型 O开放式 L封闭式
        df_etf = pro.fund_basic(exchange='', list_status='L', fund_type='ETF')
        print(f"📊 ETF: {len(df_etf)} 只")
        all_funds.append(df_etf)
        time.sleep(0.5)
    except Exception as e:
        print(f"❌ 获取ETF失败: {e}")
    
    # 获取LOF
    try:
        df_lof = pro.fund_basic(exchange='', list_status='L', fund_type='LOF')
        print(f"📊 LOF: {len(df_lof)} 只")
        all_funds.append(df_lof)
        time.sleep(0.5)
    except Exception as e:
        print(f"❌ 获取LOF失败: {e}")
    
    # 获取债券基金
    try:
        df_bond = pro.fund_basic(exchange='', list_status='L', fund_type='bond')
        print(f"📊 债券基金: {len(df_bond)} 只")
        all_funds.append(df_bond)
        time.sleep(0.5)
    except Exception as e:
        print(f"❌ 获取债券基金失败: {e}")
    
    # 合并
    import pandas as pd
    if len(all_funds) == 0:
        return None
    df_all = pd.concat(all_funds, ignore_index=True)
    print(f"\n📊 总共获取 {len(df_all)} 只基金")
    
    return df_all

def import_to_mysql(df_all, mysql_conn):
    """导入基金数据到MySQL stocks表"""
    print("\n🚀 开始导入基金数据到MySQL...")
    
    cursor = mysql_conn.cursor()
    
    inserted = 0
    failed = 0
    
    for _, row in df_all.iterrows():
        try:
            ts_code = row['ts_code']
            # 提取code (不带后缀)
            code = ts_code.split('.')[0]
            name = row['name'] if row['name'] else ''
            
            # 判断市场
            if '.SH' in ts_code:
                market = 'sh'
                market_type = 'ETF' if 'ETF' in name else 'LOF' if 'LOF' in name else '基金'
            elif '.SZ' in ts_code:
                market = 'sz'
                market_type = 'ETF' if 'ETF' in name else 'LOF' if 'LOF' in name else '基金'
            elif '.HK' in ts_code:
                market = 'hk'
                market_type = '基金'
            else:
                market = ts_code.split('.')[-1].lower()
                market_type = '基金'
            
            industry = None
            
            sql = """
                INSERT INTO stocks 
                (code, name, industry, price, change_percent, market, market_type)
                VALUES (%s, %s, %s, 0, 0, %s, %s)
            """
            
            cursor.execute(sql, (code, name, industry, market, market_type))
            inserted += 1
            
            if inserted % 100 == 0:
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
    print(f"📊 验证: stocks 表总共 {count} 条记录")
    
    # 统计各类型
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE name LIKE '%ETF%';")
    etf_count = cursor.fetchone()[0]
    print(f"📊 ETF: {etf_count} 条")
    
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE name LIKE '%LOF%';")
    lof_count = cursor.fetchone()[0]
    print(f"📊 LOF: {lof_count} 条")
    
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE name LIKE '%债%' OR market_type='bond';")
    bond_count = cursor.fetchone()[0]
    print(f"📊 债券/债券基金: {bond_count} 条")
    
    return inserted

def main():
    print("=" * 70)
    print("📥 获取ETF/LOF/债券基金基础信息 & 追加导入MySQL")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    mysql_conn = connect_mysql()
    if not mysql_conn:
        return
    
    df_all = get_fund_basic()
    if df_all is None or len(df_all) == 0:
        print("❌ 获取数据失败")
        mysql_conn.close()
        return
    
    total = import_to_mysql(df_all, mysql_conn)
    
    mysql_conn.close()
    
    print("\n" + "=" * 70)
    print(f"🎉 完成！总共追加导入 {total} 只基金")
    print("现在系统包含ETF、LOF、债券基金等所有品种了")
    print(f"🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
