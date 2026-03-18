import tushare as ts
import pymysql
import time
from datetime import datetime

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

def add_market_field():
    """添加market_type字段区分市场类型"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE stocks ADD COLUMN market_type VARCHAR(20) DEFAULT 'A股' AFTER market")
        print("✅ 已添加market_type字段")
    except Exception as e:
        if "Duplicate column name" in str(e):
            print("ℹ️ market_type字段已存在")
        else:
            print(f"❌ 添加字段失败: {e}")
    
    cursor.close()
    conn.close()

def sync_us_stocks():
    """同步美股列表"""
    print("\n🚀 开始同步美股数据...")
    
    try:
        # 获取美股列表
        df = pro.us_basic()
        print(f"获取到 {len(df)} 只美股")
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        success_count = 0
        for _, row in df.iterrows():
            try:
                sql = """
                    INSERT IGNORE INTO stocks 
                    (code, name, market, market_type, list_date)
                    VALUES (%s, %s, %s, '美股', %s)
                    ON DUPLICATE KEY UPDATE 
                    name = VALUES(name),
                    market = VALUES(market),
                    market_type = VALUES(market_type),
                    list_date = VALUES(list_date)
                """
                
                cursor.execute(sql, (
                    row['ts_code'],
                    row['name'],
                    'US',
                    row['list_date']
                ))
                
                if cursor.rowcount > 0:
                    success_count += 1
                
                time.sleep(0.01)
            except Exception as e:
                print(f"插入失败 {row['ts_code']} {row['name']}: {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ 美股同步完成，新增 {success_count} 只")
        return success_count
    except Exception as e:
        print(f"❌ 美股同步失败: {e}")
        return 0

def sync_etf():
    """同步ETF基金"""
    print("\n🚀 开始同步ETF数据...")
    
    try:
        # 获取场内ETF列表
        df = pro.fund_basic(market='E')
        print(f"获取到 {len(df)} 只ETF")
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        success_count = 0
        for _, row in df.iterrows():
            try:
                sql = """
                    INSERT IGNORE INTO stocks 
                    (code, name, market, market_type, list_date)
                    VALUES (%s, %s, %s, 'ETF', %s)
                    ON DUPLICATE KEY UPDATE 
                    name = VALUES(name),
                    market = VALUES(market),
                    market_type = VALUES(market_type),
                    list_date = VALUES(list_date)
                """
                
                code = row['ts_code'].split('.')[0]
                market = 'SH' if row['ts_code'].endswith('SH') else 'SZ'
                
                cursor.execute(sql, (
                    code,
                    row['name'],
                    market,
                    row['list_date']
                ))
                
                if cursor.rowcount > 0:
                    success_count += 1
                
                time.sleep(0.01)
            except Exception as e:
                print(f"插入失败 {row['ts_code']} {row['name']}: {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ ETF同步完成，新增 {success_count} 只")
        return success_count
    except Exception as e:
        print(f"❌ ETF同步失败: {e}")
        return 0

def sync_latest_news():
    """同步最新财经新闻"""
    print("\n🚀 开始同步最新新闻...")
    
    try:
        # 获取最近24小时新闻
        end_date = datetime.now().strftime('%Y%m%d%H%M%S')
        start_date = (datetime.now().replace(hour=0, minute=0, second=0)).strftime('%Y%m%d%H%M%S')
        
        df = pro.news(
            start_time=start_date,
            end_time=end_date,
            limit=500
        )
        
        print(f"获取到 {len(df)} 条新闻")
        
        if len(df) == 0:
            print("ℹ️ 暂无新新闻")
            return 0
        
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        success_count = 0
        for _, row in df.iterrows():
            try:
                sql = """
                    INSERT IGNORE INTO news 
                    (title, content, source, category, published_at)
                    VALUES (%s, %s, %s, '财经', %s)
                """
                
                # 处理时间
                pub_time = row.get('datetime', end_date)
                try:
                    if len(str(pub_time)) == 14:
                        published_at = datetime.strptime(str(pub_time), '%Y%m%d%H%M%S')
                    else:
                        published_at = datetime.now()
                except:
                    published_at = datetime.now()
                
                cursor.execute(sql, (
                    row.get('title', ''),
                    row.get('content', ''),
                    row.get('src', 'Tushare'),
                    published_at
                ))
                
                if cursor.rowcount > 0:
                    success_count += 1
                
                time.sleep(0.01)
            except Exception as e:
                print(f"插入新闻失败 {str(row.get('title', ''))[:30]}...: {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ 新闻同步完成，新增 {success_count} 条")
        return success_count
    except Exception as e:
        print(f"❌ 新闻同步失败: {e}")
        return 0

if __name__ == "__main__":
    print("🌐 开始全市场数据同步...")
    print("=" * 50)
    
    # 添加市场类型字段
    add_market_field()
    
    # 同步各类数据
    us_count = sync_us_stocks()
    etf_count = sync_etf()
    news_count = sync_latest_news()
    
    print("\n" + "=" * 50)
    print("🎉 全市场同步完成!")
    print(f"📊 美股新增: {us_count} 只")
    print(f"📊 ETF新增: {etf_count} 只")
    print(f"📰 新闻新增: {news_count} 条")
    print(f"🕐 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
