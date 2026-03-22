#!/usr/bin/env python3
"""
修复导入上市交易型基金（ETF/LOF/债券）
问题：之前从fund_basic导入时，所有基金都是.OF后缀，但实际上上市交易的ETF/LOF在交易所也有代码，后缀是.SZ/.SH
需要修正code，去掉前缀0，保证用户搜索能搜到
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

def fix_listed_etf_lof(mysql_conn):
    """修复ETF/LOF导入"""
    cursor = mysql_conn.cursor()
    
    # 先删除之前导入的所有基金，重新导入正确格式
    print("🧹 删除之前导入的基金数据...")
    # 删除市场类型为ETF/LOF/基金/bond
    cursor.execute("DELETE FROM stocks WHERE market_type IN ('ETF', 'LOF', '基金', '债券');")
    mysql_conn.commit()
    print("✅ 已清空旧数据")
    
    # 重新获取ETF (交易所交易型)
    print("\n🚀 重新获取ETF...")
    df_etf = pro.fund_basic(exchange='', list_status='L', fund_type='ETF')
    print(f"📊 获取到 {len(df_etf)} 只ETF")
    
    inserted = 0
    failed = 0
    
    for _, row in df_etf.iterrows():
        try:
            ts_code = row['ts_code']  # e.g. 510050.OF
            name = row['name']
            
            # 提取纯代码
            code_with_suffix = ts_code.split('.')[0]  # e.g. 510050
            
            # 去掉前面的0，如果长度大于6
            code = code_with_suffix.lstrip('0')
            if len(code) == 0:
                code = code_with_suffix
            
            # 判断交易所，一般ETF:
            # 5xxxxx 上交所 SH
            # 1xxxxx/15xxxx 深交所 SZ
            if code.startswith('5') or code.startswith('51') or code.startswith('58'):
                market = 'sh'
            elif code.startswith('1') or code.startswith('15') or code.startswith('16'):
                market = 'sz'
            else:
                # 默认猜测
                market = 'sz'
            
            market_type = 'ETF'
            industry = None
            
            sql = """
                INSERT INTO stocks 
                (code, name, industry, price, change_percent, market, market_type)
                VALUES (%s, %s, %s, 0, 0, %s, %s)
            """
            
            cursor.execute(sql, (code, name, industry, market, market_type))
            inserted += 1
            
            if inserted % 500 == 0:
                mysql_conn.commit()
                print(f"  已插入 {inserted}...")
                
        except Exception as e:
            failed += 1
            if failed <= 10:
                print(f"  ❌ 插入失败 {ts_code}: {e}")
            continue
    
    # 获取LOF (上市开放式)
    print("\n🚀 重新获取LOF...")
    df_lof = pro.fund_basic(exchange='', list_status='L', fund_type='LOF')
    print(f"📊 获取到 {len(df_lof)} 只LOF")
    
    for _, row in df_lof.iterrows():
        try:
            ts_code = row['ts_code']
            name = row['name']
            code_with_suffix = ts_code.split('.')[0]
            code = code_with_suffix.lstrip('0')
            if len(code) == 0:
                code = code_with_suffix
            
            # LOF大多在深交所
            if code.startswith('16') or code.startswith('50'):
                market = 'sz'
            elif code.startswith('5'):
                market = 'sh'
            else:
                market = 'sz'
            
            market_type = 'LOF'
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
                
        except Exception as e:
            failed += 1
            if failed <= 10:
                print(f"  ❌ 插入失败 {ts_code}: {e}")
            continue
    
    # 获取债券基金
    print("\n🚀 重新获取债券基金...")
    df_bond = pro.fund_basic(exchange='', list_status='L', fund_type='bond')
    print(f"📊 获取到 {len(df_bond)} 只债券基金")
    
    for _, row in df_bond.iterrows():
        try:
            ts_code = row['ts_code']
            name = row['name']
            code_with_suffix = ts_code.split('.')[0]
            code = code_with_suffix.lstrip('0')
            if len(code) == 0:
                code = code_with_suffix
            
            # 债券ETF大多在上交所
            if code.startswith('5'):
                market = 'sh'
            else:
                market = 'sz'
            
            market_type = '债券'
            industry = '债券'
            
            sql = """
                INSERT INTO stocks 
                (code, name, industry, price, change_percent, market, market_type)
                VALUES (%s, %s, %s, 0, 0, %s, %s)
            """
            
            cursor.execute(sql, (code, name, industry, market, market_type))
            inserted += 1
            
        except Exception as e:
            failed += 1
            if failed <= 10:
                print(f"  ❌ 插入失败 {ts_code}: {e}")
            continue
    
    mysql_conn.commit()
    
    # 验证结果
    print("\n📊 验证结果:")
    cursor.execute("SELECT COUNT(*) FROM stocks;")
    total = cursor.fetchone()[0]
    print(f"  总计: {total} 条")
    
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE market_type='ETF';")
    cnt_etf = cursor.fetchone()[0]
    print(f"  ETF: {cnt_etf} 条")
    
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE market_type='LOF';")
    cnt_lof = cursor.fetchone()[0]
    print(f"  LOF: {cnt_lof} 条")
    
    cursor.execute("SELECT COUNT(*) FROM stocks WHERE market_type='债券';")
    cnt_bond = cursor.fetchone()[0]
    print(f"  债券: {cnt_bond} 条")
    
    # 检查中欧强债 166008
    cursor.execute("SELECT * FROM stocks WHERE code='166008';")
    result = cursor.fetchone()
    if result:
        print(f"\n✅ 找到 166008: code={result[0]}, name={result[1]}, market={result[5]}, market_type={result[6]}")
    else:
        print(f"\n⚠️  未找到 166008，尝试搜索...")
        cursor.execute("SELECT * FROM stocks WHERE name LIKE '%中欧强债%';")
        result = cursor.fetchall()
        print(f"找到 {len(result)} 条:")
        for r in result:
            print(f"  code={r[0]}, name={r[1]}")
    
    return inserted, failed

def main():
    print("=" * 70)
    print("🔧 修复上市基金(ETF/LOF/债券)导入问题")
    print(f"🕐 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    mysql_conn = connect_mysql()
    if not mysql_conn:
        return
    
    inserted, failed = fix_listed_etf_lof(mysql_conn)
    
    mysql_conn.close()
    
    print("\n" + "=" * 70)
    print(f"🎉 修复完成！成功 {inserted}, 失败 {failed}")
    print("现在 166008 (中欧强债LOF) 应该可以找到了")
    print(f"🕐 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
