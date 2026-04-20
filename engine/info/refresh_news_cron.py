"""
新闻数据定时刷新脚本
每30分钟运行一次，从MySQL同步最新新闻到本地NewsDB
"""
import asyncio
import sys
sys.path.insert(0, '/var/www/ai-god-of-stocks')

from engine.info.news_analyzer import NewsAnalyzer

async def main():
    analyzer = NewsAnalyzer()
    count = await analyzer.refresh(hours=48)
    print(f"[{asyncio.get_event_loop().time()}] 刷新新闻: {count}条新增")

asyncio.run(main())
