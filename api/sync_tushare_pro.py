import tushare as ts
import pymysql
import time

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'familystock',
    'password': 'Familystock@2026',
    'database': 'familystock',
    'charset': 'utf8mb4'
}

def sync_stock_basic():
    """同步股票基础信息（包含行业、上市日期等）"""
    print("正在从Tushare Pro获取股票基础信息...")
    
    # 获取A股列表
    df = pro.stock_basic(
        exchange='',
        list_status='L',
        fields='ts_code,symbol,name,area,industry,market,list_date'
    )
    
    print(f"获取到 {len(df)} 只股票基础信息")
    
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # 先添加industry字段（如果不存在）
    try:
        cursor.execute("ALTER TABLE stocks ADD COLUMN industry VARCHAR(100) DEFAULT '' AFTER name")
        print("已添加industry字段")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("industry字段已存在")
        else:
            print(f"添加字段失败: {e}")
    
    # 批量更新
    success_count = 0
    for _, row in df.iterrows():
        try:
            sql = """
                UPDATE stocks 
                SET industry = %s
                WHERE code = %s
            """
            symbol = row['symbol']
            industry = row['industry'] if row['industry'] else ''
            
            cursor.execute(sql, (industry, symbol))
            success_count += 1
            
            if success_count % 1000 == 0:
                print(f"已更新 {success_count} 只股票行业信息...")
                conn.commit()
                
            # 限制调用频率
            time.sleep(0.01)
        except Exception as e:
            print(f"更新失败 {symbol} {row['name']}: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"同步完成，成功更新 {success_count} 只股票行业信息")
    return success_count

if __name__ == "__main__":
    count = sync_stock_basic()
    print(f"✅ Tushare Pro数据同步完成，共 {count} 只股票信息已更新")
