#!/usr/bin/env python3
"""
Tushare新闻抓取脚本
抓取最新财经新闻并存入数据库
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from app.routers.tushare import call_tushare_api
from database import SessionLocal, engine
import models

# 创建数据库表
models.Base.metadata.create_all(bind=engine)

def fetch_latest_news(start_date=None, end_date=None, limit=20):
    """抓取最新新闻"""
    if not end_date:
        end_date = datetime.now().strftime("%Y%m%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
    print(f"正在抓取 {start_date} 至 {end_date} 的新闻...")
    
    # 调用Tushare新闻API
    news_data = call_tushare_api("news", {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit
    }, "title,content,summary,source,url,published_at")
    
    if not news_data:
        print("未获取到新闻数据")
        return []
    
    print(f"获取到 {len(news_data)} 条新闻")
    return news_data

def save_news_to_db(news_list):
    """保存新闻到数据库"""
    db = SessionLocal()
    saved_count = 0
    duplicate_count = 0
    
    for news in news_list:
        # 检查是否已存在相同URL的新闻
        existing = db.query(models.News).filter(models.News.url == news.get("url")).first()
        if existing:
            duplicate_count += 1
            continue
        
        # 创建新新闻记录
        db_news = models.News(
            title=news.get("title"),
            content=news.get("content"),
            summary=news.get("summary"),
            source=news.get("source"),
            url=news.get("url"),
            category="财经",
            sentiment="neutral",
            published_at=datetime.strptime(news.get("published_at"), "%Y-%m-%d %H:%M:%S") if news.get("published_at") else None
        )
        
        db.add(db_news)
        saved_count += 1
    
    db.commit()
    db.close()
    
    print(f"新闻保存完成：新增 {saved_count} 条，重复 {duplicate_count} 条")
    return saved_count, duplicate_count

def check_stock_prices():
    """检查股价信息是否为最新"""
    print("\n正在检查股价信息...")
    
    # 测试几个主要指数
    test_stocks = ["000001.SH", "399001.SZ", "000300.SH"]
    latest_dates = []
    
    for ts_code in test_stocks:
        data = call_tushare_api("daily", {
            "ts_code": ts_code,
            "limit": 1
        }, "trade_date,close")
        
        if data and len(data) > 0:
            latest = data[0]
            trade_date = latest.get("trade_date")
            close = latest.get("close")
            print(f"{ts_code}: 最新交易日 {trade_date}, 收盘价 {close}")
            latest_dates.append(trade_date)
    
    if latest_dates:
        latest_date = max(latest_dates)
        today = datetime.now().strftime("%Y%m%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        
        if latest_date == today:
            print(f"✅ 股价数据已更新到今日（{latest_date}）")
        elif latest_date == yesterday:
            print(f"⚠️  股价数据已更新到昨日（{latest_date}），今日数据可能尚未发布")
        else:
            print(f"❌ 股价数据过旧，最新为 {latest_date}")
    else:
        print("❌ 无法获取股价数据")

if __name__ == "__main__":
    print("=" * 50)
    print("Tushare晚间新闻更新脚本")
    print("=" * 50)
    
    # 抓取新闻
    news_list = fetch_latest_news(limit=20)
    
    if news_list:
        # 保存到数据库
        saved, duplicate = save_news_to_db(news_list)
        
        # 预览前3条
        print("\n最新新闻预览：")
        for i, news in enumerate(news_list[:3]):
            print(f"\n{i+1}. {news.get('title')}")
            print(f"   来源：{news.get('source')}")
            print(f"   时间：{news.get('published_at')}")
        
        print("\n新闻更新完成。")
    
    # 检查股价信息
    check_stock_prices()
    
    print("\n任务完成。")
