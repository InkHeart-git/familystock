import os
import tushare as ts
import pymysql
import time
import requests
import json
import subprocess
from datetime import datetime, timedelta
from bs4 import BeautifulSoup

# Tushare Pro配置
ts.set_token('f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735')
pro = ts.pro_api()

# QVeris配置
QVERIS_API_KEY = "sk-3JgIUg70yvI2zvedHKUqWy4BRNRN_XCsPsMqhiWQjiw"
QVERIS_CLI_PATH = "/root/.openclaw/skills/qveris-official/scripts/qveris_tool.mjs"

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'familystock',
    'password': 'Familystock@2026',
    'database': 'familystock',
    'charset': 'utf8mb4'
}

def get_qveris_news():
    """从QVeris获取最新财经新闻"""
    print("正在从QVeris获取财经新闻...")
    try:
        # 使用之前测试成功的工具ID和固定的discovery ID
        # 之前测试成功的工具：finnhub.market.news.list.v1
        discovery_id = "5f4c4b41-589f-49aa-b312-33f06211d39f"
        tool_id = "finnhub.market.news.list.v1"
        
        env = os.environ.copy()
        env['QVERIS_API_KEY'] = QVERIS_API_KEY
        
        # 直接调用工具获取新闻
        call_cmd = [
            "node", QVERIS_CLI_PATH,
            "call", tool_id,
            "--discovery-id", discovery_id,
            "--params", '{"category":"general"}',
            "--json"
        ]
        
        result = subprocess.run(call_cmd, capture_output=True, text=True, env=env, timeout=60)
        if result.returncode != 0:
            print(f"QVeris调用失败: {result.stderr}")
            return []
            
        call_data = json.loads(result.stdout)
        
        # 下载完整新闻数据
        print(f"QVeris返回数据: {json.dumps(call_data, indent=2, ensure_ascii=False)[:500]}...")
        # 优先获取result字段
        result_data = call_data.get('result', call_data)
        if result_data.get('full_content_file_url'):
            news_response = requests.get(result_data['full_content_file_url'], timeout=10)
            print(f"下载新闻数据状态码: {news_response.status_code}")
            news_data = news_response.json()
            print(f"获取到新闻条数: {len(news_data)}")
        else:
            news_data = result_data.get('content', [])
            print(f"直接获取新闻条数: {len(news_data)}")
            
        # 转换格式
        formatted_news = []
        for item in news_data[:200]:  # 最多取200条
            try:
                pub_time = datetime.fromtimestamp(item.get('datetime', time.time()))
                formatted_news.append({
                    'title': item.get('headline', ''),
                    'content': item.get('summary', item.get('headline', '')),
                    'src': item.get('source', 'QVeris'),
                    'url': item.get('url', ''),
                    'datetime': pub_time.strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception as e:
                continue
                
        print(f"QVeris返回 {len(formatted_news)} 条新闻")
        return formatted_news
        
    except Exception as e:
        print(f"QVeris获取失败: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_eastmoney_news():
    """从东方财富网抓取最新财经新闻"""
    print("正在从东方财富网获取财经新闻...")
    url = "https://finance.eastmoney.com/news/cgjxw.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_list = []
        items = soup.select('#newsListContent li')[:50]
        
        for item in items:
            try:
                title = item.select_one('.title a').get_text(strip=True)
                href = item.select_one('.title a')['href']
                time_str = item.select_one('.time').get_text(strip=True)
                today = datetime.now().strftime('%Y-%m-%d')
                pub_time = datetime.strptime(f"{today} {time_str}", '%Y-%m-%d %H:%M')
                
                news_list.append({
                    'title': title,
                    'content': title,
                    'src': '东方财富网',
                    'url': href,
                    'datetime': pub_time.strftime('%Y-%m-%d %H:%M:%S')
                })
            except Exception as e:
                continue
        
        print(f"获取到 {len(news_list)} 条东方财富新闻")
        return news_list
    except Exception as e:
        print(f"东方财富网抓取失败: {e}")
        return []

def init_news_table():
    """初始化新闻表"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # 创建新闻表
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS news (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(500) NOT NULL COMMENT '新闻标题',
        content TEXT COMMENT '新闻内容',
        source VARCHAR(100) COMMENT '来源',
        url VARCHAR(500) COMMENT '原文链接',
        category VARCHAR(50) COMMENT '分类',
        sentiment_score DECIMAL(5,2) DEFAULT 0.00 COMMENT '情感分数',
        keywords VARCHAR(500) COMMENT '关键词',
        published_at DATETIME COMMENT '发布时间',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY idx_title (title(255))
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财经新闻表';
    """
    
    try:
        cursor.execute(create_table_sql)
        print("✅ 新闻表初始化完成")
    except Exception as e:
        print(f"❌ 表创建失败: {e}")
    finally:
        cursor.close()
        conn.close()

def sync_news():
    """同步财经快讯"""
    all_news = []
    
    # 1. 从QVeris获取新闻
    qveris_news = get_qveris_news()
    all_news.extend(qveris_news)
    
    # 2. 从Tushare获取新闻
    print("正在从Tushare Pro获取财经快讯...")
    today = datetime.now().strftime('%Y-%m-%d')
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        df = pro.news(
            start_time=f'{yesterday} 00:00:00',
            end_time=f'{today} 23:59:59',
            limit=1000
        )
        print(f"Tushare返回 {len(df)} 条新闻")
        
        # 转换Tushare数据格式
        for _, row in df.iterrows():
            all_news.append({
                'title': str(row.get('title', row.get('content', '无标题')[:100])) if row.get('title') is not None else str(row.get('content', '无标题')[:100]),
                'content': str(row.get('content', '')) if row.get('content') is not None else '',
                'src': 'Tushare',
                'url': str(row.get('url', '')) if row.get('url') is not None else '',
                'datetime': str(row.get('datetime', row.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))))
            })
    except Exception as e:
        print(f"Tushare接口调用失败: {e}")
    
    # 3. 从东方财富网获取新闻（备用）
    if len(all_news) < 50:
        print("新闻数量不足，尝试从东方财富网补充...")
        eastmoney_news = get_eastmoney_news()
        all_news.extend(eastmoney_news)
    
    # 4. 去重（根据标题）
    seen_titles = set()
    unique_news = []
    for news in all_news:
        title = news['title'].strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_news.append(news)
    
    print(f"总获取 {len(all_news)} 条新闻，去重后剩余 {len(unique_news)} 条")
    
    if len(unique_news) == 0:
        print("❌ 所有数据源都未获取到有效数据")
        return 0
    
    # 转换为DataFrame格式
    import pandas as pd
    df = pd.DataFrame(unique_news)
    
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # 批量插入
    success_count = 0
    for _, row in df.iterrows():
        try:
            sql = """
                INSERT IGNORE INTO news 
                (title, content, source, url, category, published_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            # 处理时间格式
            pub_time = row.get('datetime', row.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
            try:
                if len(str(pub_time)) == 14:
                    published_at = datetime.strptime(str(pub_time), '%Y%m%d%H%M%S')
                else:
                    published_at = datetime.strptime(str(pub_time), '%Y-%m-%d %H:%M:%S')
            except:
                published_at = datetime.now()
            
            cursor.execute(sql, (
                str(row.get('title', row.get('content', '无标题')[:100])) if row.get('title') is not None else str(row.get('content', '无标题')[:100]),
                str(row.get('content', '')) if row.get('content') is not None else '',
                str(row.get('src', 'Tushare')) if row.get('src') is not None else 'Tushare',
                str(row.get('url', '')) if row.get('url') is not None else '',
                '财经',
                published_at
            ))
            
            if cursor.rowcount > 0:
                success_count += 1
            
            # 限制调用频率
            time.sleep(0.01)
        except Exception as e:
            print(f"插入失败 {str(row.get('title', ''))[:30]}...: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ 同步完成，成功插入 {success_count} 条新新闻")
    return success_count

if __name__ == "__main__":
    init_news_table()
    count = sync_news()
    print(f"🎉 新闻数据同步完成，共新增 {count} 条新闻")
