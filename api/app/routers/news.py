from fastapi import APIRouter, HTTPException
import sqlite3
import os

router = APIRouter()

DB_PATH = '/var/www/familystock/api/data/family_stock.db'

@router.get('/')
async def get_news(limit: int = 20, category: str = None):
    """获取新闻列表"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if category and category != 'all':
            cursor.execute('''
                SELECT id, title, content, summary, source, url, category, sentiment, published_at, created_at 
                FROM news WHERE category = ? ORDER BY published_at DESC LIMIT ?
            ''', (category, limit))
        else:
            cursor.execute('''
                SELECT id, title, content, summary, source, url, category, sentiment, published_at, created_at 
                FROM news ORDER BY published_at DESC LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            result.append({
                'id': row['id'],
                'title': row['title'],
                'content': row['content'],
                'summary': row['summary'],
                'source': row['source'],
                'url': row['url'],
                'category': row['category'],
                'sentiment': row['sentiment'],
                'published_at': row['published_at'],
                'created_at': row['created_at']
            })
        
        return result
    except Exception as e:
        print(f"Error fetching news: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/{news_id}')
async def get_news_detail(news_id: int):
    """获取新闻详情"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM news WHERE id = ?', (news_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        raise HTTPException(status_code=404, detail="新闻不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
