import requests
import pymysql
import time
from datetime import datetime
import json

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'familystock',
    'password': 'Familystock@2026',
    'database': 'familystock',
    'charset': 'utf8mb4'
}

def get_eastmoney_news():
    """从东方财富获取最新财经新闻"""
    print("正在从东方财富获取新闻...")
    url = "https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult.ashx"
    
    params = {
        'page': 1,
        'pagesize': 100,
        'type': 0,
        'show': 1,
        '_': int(time.time() * 1000)
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://kuaixun.eastmoney.com/'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=30)
        data = response.text.replace('ajaxResult(', '').rstrip(')')
        json_data = json.loads(data)
        
        news_list = []
        for item in json_data.get('relevance', []):
            try:
                title = item.get('title', '')
                content = item.get('digest', '')
                pub_time = item.get('showtime', '')
                url = item.get('url', '')
                
                if not title:
                    continue
                
                # 解析时间
                try:
                    published_at = datetime.strptime(pub_time, '%Y-%m-%d %H:%M:%S')
                except:
                    published_at = datetime.now()
                
                news_list.append({
                    'title': title,
                    'content': content,
                    'url': url,
                    'published_at': published_at,
                    'source': '东方财富',
                    'category': '财经'
                })
            except Exception as e:
                print(f"解析新闻项失败: {e}")
                continue
        
        print(f"获取到 {len(news_list)} 条东方财富新闻")
        return news_list
        
    except Exception as e:
        print(f"获取东方财富新闻失败: {e}")
        return []

def save_news(news_list):
    """保存新闻到数据库"""
    if not news_list:
        return 0
    
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    success_count = 0
    for news in news_list:
        try:
            sql = """
                INSERT IGNORE INTO news 
                (title, content, source, url, category, published_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            cursor.execute(sql, (
                news['title'],
                news['content'],
                news['source'],
                news['url'],
                news['category'],
                news['published_at']
            ))
            
            if cursor.rowcount > 0:
                success_count += 1
                
        except Exception as e:
            print(f"插入新闻失败 {news['title'][:30]}...: {e}")
            continue
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print(f"✅ 成功保存 {success_count} 条新闻")
    return success_count

if __name__ == "__main__":
    news_list = get_eastmoney_news()
    count = save_news(news_list)
    print(f"🎉 新闻同步完成，共新增 {count} 条财经新闻")
