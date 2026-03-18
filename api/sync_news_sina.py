import requests
import pymysql
import time
from datetime import datetime
from bs4 import BeautifulSoup

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'familystock',
    'password': 'Familystock@2026',
    'database': 'familystock',
    'charset': 'utf8mb4'
}

def get_sina_finance_news():
    """从新浪财经获取最新新闻"""
    print("正在从新浪财经获取新闻...")
    url = "https://finance.sina.com.cn/roll/index.d.html?cid=56995"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'gbk'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        news_list = []
        items = soup.select('.list_009 li')
        
        for item in items[:100]:  # 取前100条
            try:
                a_tag = item.select_one('a')
                time_tag = item.select_one('.time')
                
                if a_tag and time_tag:
                    title = a_tag.get_text(strip=True)
                    url = a_tag.get('href', '')
                    pub_time = time_tag.get_text(strip=True)
                    
                    # 补全年份
                    current_year = datetime.now().year
                    full_time = f"{current_year}-{pub_time}:00"
                    
                    news_list.append({
                        'title': title,
                        'url': url,
                        'published_at': full_time,
                        'source': '新浪财经',
                        'category': '财经'
                    })
            except Exception as e:
                print(f"解析新闻项失败: {e}")
                continue
        
        print(f"获取到 {len(news_list)} 条新浪财经新闻")
        return news_list
        
    except Exception as e:
        print(f"获取新浪新闻失败: {e}")
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
                (title, source, url, category, published_at)
                VALUES (%s, %s, %s, %s, %s)
            """
            
            try:
                published_at = datetime.strptime(news['published_at'], '%Y-%m-%d %H:%M:%S')
            except:
                published_at = datetime.now()
            
            cursor.execute(sql, (
                news['title'],
                news['source'],
                news['url'],
                news['category'],
                published_at
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
    news_list = get_sina_finance_news()
    count = save_news(news_list)
    print(f"🎉 新闻同步完成，共新增 {count} 条财经新闻")
