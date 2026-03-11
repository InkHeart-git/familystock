"""
MiniRock数据库连接模块
提供PostgreSQL连接和常用操作
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'database': 'minirock',
    'user': 'minirock',
    'password': 'minirock123',
    'port': 5432
}

class Database:
    """数据库连接类"""
    
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """建立数据库连接"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            return True
        except Exception as e:
            print(f"数据库连接失败: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
    
    def execute(self, sql, params=None):
        """执行SQL"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(sql, params)
                self.conn.commit()
                return True
        except Exception as e:
            self.conn.rollback()
            print(f"SQL执行失败: {e}")
            return False
    
    def fetch_one(self, sql, params=None):
        """查询单条记录"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        except Exception as e:
            print(f"查询失败: {e}")
            return None
    
    def fetch_all(self, sql, params=None):
        """查询多条记录"""
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        except Exception as e:
            print(f"查询失败: {e}")
            return []


# ==================== 用户相关操作 ====================

def create_user(phone, password_hash, name='投资者'):
    """创建用户"""
    db = Database()
    sql = """
        INSERT INTO users (phone, password_hash, name)
        VALUES (%s, %s, %s)
        RETURNING id, phone, name, created_at
    """
    result = db.fetch_one(sql, (phone, password_hash, name))
    db.close()
    return result


def get_user_by_phone(phone):
    """根据手机号获取用户"""
    db = Database()
    sql = "SELECT * FROM users WHERE phone = %s AND is_active = TRUE"
    result = db.fetch_one(sql, (phone,))
    db.close()
    return result


def get_user_by_id(user_id):
    """根据ID获取用户"""
    db = Database()
    sql = "SELECT * FROM users WHERE id = %s"
    result = db.fetch_one(sql, (user_id,))
    db.close()
    return result


def update_user_quota(user_id, quota):
    """更新用户额度"""
    db = Database()
    sql = "UPDATE users SET quota_remaining = %s WHERE id = %s"
    success = db.execute(sql, (quota, user_id))
    db.close()
    return success


# ==================== 持仓相关操作 ====================

def add_holding(user_id, symbol, name, quantity, avg_cost, market='A股', currency='CNY'):
    """添加持仓"""
    db = Database()
    # 检查是否已存在
    existing = db.fetch_one(
        "SELECT * FROM holdings WHERE user_id = %s AND symbol = %s",
        (user_id, symbol)
    )
    
    if existing:
        # 更新持仓
        new_qty = float(existing['quantity']) + quantity
        new_cost = (float(existing['avg_cost']) * float(existing['quantity']) + avg_cost * quantity) / new_qty
        sql = """
            UPDATE holdings 
            SET quantity = %s, avg_cost = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND symbol = %s
        """
        success = db.execute(sql, (new_qty, new_cost, user_id, symbol))
    else:
        # 新增持仓
        sql = """
            INSERT INTO holdings (user_id, symbol, name, quantity, avg_cost, market, currency)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        success = db.execute(sql, (user_id, symbol, name, quantity, avg_cost, market, currency))
    
    db.close()
    return success


def get_user_holdings(user_id):
    """获取用户所有持仓"""
    db = Database()
    sql = """
        SELECT h.*, sc.close as current_price, sc.pct_chg, sc.ai_score
        FROM holdings h
        LEFT JOIN stock_cache sc ON h.symbol = sc.symbol
        WHERE h.user_id = %s
        ORDER BY h.created_at DESC
    """
    results = db.fetch_all(sql, (user_id,))
    db.close()
    return results


def update_holding(user_id, symbol, quantity, avg_cost):
    """更新持仓"""
    db = Database()
    sql = """
        UPDATE holdings 
        SET quantity = %s, avg_cost = %s, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = %s AND symbol = %s
    """
    success = db.execute(sql, (quantity, avg_cost, user_id, symbol))
    db.close()
    return success


def delete_holding(user_id, symbol):
    """删除持仓"""
    db = Database()
    sql = "DELETE FROM holdings WHERE user_id = %s AND symbol = %s"
    success = db.execute(sql, (user_id, symbol))
    db.close()
    return success


# ==================== 股票缓存相关操作 ====================

def cache_stock_data(stock_data):
    """缓存股票数据"""
    db = Database()
    sql = """
        INSERT INTO stock_cache 
        (symbol, ts_code, name, close, open, high, low, pct_chg, volume, amount, market, currency, ai_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (symbol) DO UPDATE SET
            ts_code = EXCLUDED.ts_code,
            name = EXCLUDED.name,
            close = EXCLUDED.close,
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            pct_chg = EXCLUDED.pct_chg,
            volume = EXCLUDED.volume,
            amount = EXCLUDED.amount,
            market = EXCLUDED.market,
            currency = EXCLUDED.currency,
            ai_score = EXCLUDED.ai_score,
            cached_at = CURRENT_TIMESTAMP
    """
    success = db.execute(sql, (
        stock_data.get('symbol'),
        stock_data.get('ts_code'),
        stock_data.get('name'),
        stock_data.get('close'),
        stock_data.get('open'),
        stock_data.get('high'),
        stock_data.get('low'),
        stock_data.get('pct_chg'),
        stock_data.get('volume'),
        stock_data.get('amount'),
        stock_data.get('market'),
        stock_data.get('currency'),
        stock_data.get('ai_score', 50)
    ))
    db.close()
    return success


def get_cached_stock(symbol):
    """获取缓存的股票数据"""
    db = Database()
    sql = "SELECT * FROM stock_cache WHERE symbol = %s"
    result = db.fetch_one(sql, (symbol,))
    db.close()
    return result


def get_all_cached_stocks():
    """获取所有缓存的股票"""
    db = Database()
    sql = "SELECT * FROM stock_cache ORDER BY cached_at DESC"
    results = db.fetch_all(sql)
    db.close()
    return results


# ==================== 汇率相关操作 ====================

def get_exchange_rate(from_currency, to_currency):
    """获取汇率"""
    db = Database()
    sql = "SELECT rate FROM exchange_rates WHERE from_currency = %s AND to_currency = %s"
    result = db.fetch_one(sql, (from_currency, to_currency))
    db.close()
    return result['rate'] if result else None


def update_exchange_rate(from_currency, to_currency, rate):
    """更新汇率"""
    db = Database()
    sql = """
        INSERT INTO exchange_rates (from_currency, to_currency, rate)
        VALUES (%s, %s, %s)
        ON CONFLICT (from_currency, to_currency) DO UPDATE SET
            rate = EXCLUDED.rate,
            updated_at = CURRENT_TIMESTAMP
    """
    success = db.execute(sql, (from_currency, to_currency, rate))
    db.close()
    return success


# ==================== AI报告相关操作 ====================

def save_ai_report(user_id, report_type, content, risk_level='medium', score=50):
    """保存AI分析报告"""
    db = Database()
    sql = """
        INSERT INTO ai_analysis_reports (user_id, report_type, content, risk_level, score)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """
    result = db.fetch_one(sql, (user_id, report_type, content, risk_level, score))
    db.close()
    return result['id'] if result else None


def get_user_reports(user_id, limit=10):
    """获取用户报告历史"""
    db = Database()
    sql = """
        SELECT * FROM ai_analysis_reports 
        WHERE user_id = %s 
        ORDER BY created_at DESC 
        LIMIT %s
    """
    results = db.fetch_all(sql, (user_id, limit))
    db.close()
    return results


# ==================== 新闻相关操作 ====================

def save_news(title, content, source, url, category, sentiment_score, keywords, published_at):
    """保存新闻"""
    db = Database()
    sql = """
        INSERT INTO news (title, content, source, url, category, sentiment_score, keywords, published_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """
    success = db.execute(sql, (title, content, source, url, category, sentiment_score, keywords, published_at))
    db.close()
    return success


def get_recent_news(limit=20):
    """获取最近新闻"""
    db = Database()
    sql = """
        SELECT * FROM news 
        ORDER BY published_at DESC 
        LIMIT %s
    """
    results = db.fetch_all(sql, (limit,))
    db.close()
    return results


if __name__ == '__main__':
    # 测试连接
    db = Database()
    print("✅ 数据库连接成功!")
    
    # 测试查询
    result = db.fetch_one("SELECT version()")
    print(f"PostgreSQL版本: {result['version']}")
    db.close()
