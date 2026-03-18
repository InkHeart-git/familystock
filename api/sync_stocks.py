import akshare as ak
import pymysql

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'familystock',
    'password': 'Familystock@2026',
    'database': 'familystock',
    'charset': 'utf8mb4'
}

def sync_stock_list():
    # 使用东方财富接口获取A股列表
    print("正在获取A股股票列表...")
    df = ak.stock_zh_a_spot_em()
    print(f"获取到 {len(df)} 只股票")
    
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # 清空表
    cursor.execute("TRUNCATE TABLE stocks")
    
    # 批量插入 - 匹配实际表结构
    success_count = 0
    for _, row in df.iterrows():
        try:
            sql = """
                INSERT INTO stocks (code, name, price, change_percent, market, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """
            # 处理数据
            code = str(row['代码'])
            name = str(row['名称'])
            market = 'SH' if code.startswith('6') else 'SZ'
            
            # 处理数值类型，避免NaN
            price = float(row['最新价']) if row['最新价'] and not str(row['最新价']).lower() == 'nan' else 0
            change_percent = float(row['涨跌幅']) if row['涨跌幅'] and not str(row['涨跌幅']).lower() == 'nan' else 0
            
            cursor.execute(sql, (code, name, price, change_percent, market))
            success_count += 1
            
            if success_count % 1000 == 0:
                print(f"已插入 {success_count} 只股票...")
                conn.commit()  # 每1000条提交一次
        except Exception as e:
            print(f"插入失败 {code} {name}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"同步完成，成功插入 {success_count} 只股票")
    return success_count

if __name__ == "__main__":
    count = sync_stock_list()
    print(f"✅ 数据同步完成，共 {count} 只股票已入库")
