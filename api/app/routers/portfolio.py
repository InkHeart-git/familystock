"""
持仓管理API路由 - 支持数据库持久化
提供用户持仓的CRUD操作、实时行情查询和预警系统
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import requests
import os
import psycopg2
from psycopg2.extras import RealDictCursor

router = APIRouter(prefix="/portfolio", tags=["持仓管理"])

# Tushare配置
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"
TUSHARE_API_URL = "http://api.tushare.pro"

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'database': 'minirock',
    'user': 'minirock',
    'password': 'minirock123',
    'port': 5432
}

class HoldingRequest(BaseModel):
    symbol: str
    name: str
    quantity: int
    avg_cost: float


# ==================== 数据库操作 ====================

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('UTF8')
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None


# 内存备份（数据库不可用时使用）
USER_PORTFOLIO_BACKUP = {}


def ensure_user_exists(conn, user_id):
    """确保用户存在"""
    try:
        with conn.cursor() as cur:
            # 先检查用户是否存在
            cur.execute("SELECT id FROM users WHERE user_id = %s OR phone = %s", (user_id, user_id))
            if cur.fetchone():
                return  # 用户已存在
            
            # 插入新用户（提供所有必需的列）
            cur.execute("""
                INSERT INTO users (phone, name, password_hash) 
                VALUES (%s, %s, %s) 
                ON CONFLICT DO NOTHING
            """, (user_id, '投资者', 'temp_hash'))
            conn.commit()
    except:
        conn.rollback()


# ==================== 行情获取 ====================

def get_tushare_quote(symbol: str):
    """从SQLite stock_quotes表获取实时行情"""
    import sqlite3
    
    try:
        # 确保有交易所后缀
        if '.' not in symbol:
            if symbol.startswith('6'):
                ts_code = f"{symbol}.SH"
            elif symbol.startswith('0') or symbol.startswith('3'):
                ts_code = f"{symbol}.SZ"
            elif symbol.startswith('8') or symbol.startswith('4'):
                ts_code = f"{symbol}.BJ"
            else:
                ts_code = symbol
        else:
            ts_code = symbol
        
        # 连接SQLite数据库
        db_path = "/var/www/familystock/api/data/family_stock.db"
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # 查询最新行情
        cur.execute("""
            SELECT ts_code, close, open, high, low, pre_close, 
                   change, pct_chg, vol, amount
            FROM stock_quotes 
            WHERE ts_code = ?
            ORDER BY trade_date DESC
            LIMIT 1
        """, (ts_code,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        
        if not row:
            return None
        
        return {
            "symbol": ts_code,
            "price": float(row["close"] or 0),
            "open": float(row["open"] or 0),
            "high": float(row["high"] or 0),
            "low": float(row["low"] or 0),
            "prev_close": float(row["pre_close"] or 0),
            "change": float(row["change"] or 0),
            "change_percent": float(row["pct_chg"] or 0),
            "volume": int(row["vol"] or 0),
            "amount": float(row["amount"] or 0),
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"获取行情失败 {symbol}: {e}")
        return None


def sync_stock_quote(symbol: str):
    """从Tushare获取行情并保存到SQLite（用于添加持仓时自动同步）"""
    import sqlite3
    
    try:
        # 确保有交易所后缀
        if '.' not in symbol:
            if symbol.startswith('6'):
                ts_code = f"{symbol}.SH"
            elif symbol.startswith('0') or symbol.startswith('3'):
                ts_code = f"{symbol}.SZ"
            elif symbol.startswith('8') or symbol.startswith('4'):
                ts_code = f"{symbol}.BJ"
            else:
                ts_code = symbol
        else:
            ts_code = symbol
            symbol = ts_code.split('.')[0]
        
        # 检查stock_quotes表是否已有数据
        db_path = "/var/www/familystock/api/data/family_stock.db"
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        cur.execute("SELECT 1 FROM stock_quotes WHERE ts_code = ? LIMIT 1", (ts_code,))
        if cur.fetchone():
            cur.close()
            conn.close()
            return True  # 已有数据，无需同步
        
        # 从Tushare获取最新行情
        payload = {
            "api_name": "daily",
            "token": TUSHARE_TOKEN,
            "params": {"ts_code": ts_code, "limit": 1}
        }
        
        response = requests.post(TUSHARE_API_URL, json=payload, timeout=10)
        result = response.json()
        
        if result.get("code") != 0 or not result.get("data", {}).get("items"):
            cur.close()
            conn.close()
            return False
        
        fields = result["data"]["fields"]
        item = result["data"]["items"][0]
        data = dict(zip(fields, item))
        
        # 保存到stock_quotes
        cur.execute('''
            INSERT OR REPLACE INTO stock_quotes 
            (ts_code, symbol, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ts_code, symbol, str(data.get("trade_date", "")),
            float(data.get("open", 0)), float(data.get("high", 0)),
            float(data.get("low", 0)), float(data.get("close", 0)),
            float(data.get("pre_close", 0)), float(data.get("change", 0)),
            float(data.get("pct_chg", 0)), float(data.get("vol", 0)),
            float(data.get("amount", 0))
        ))
        conn.commit()
        cur.close()
        conn.close()
        print(f"✅ 已同步行情数据: {ts_code}")
        return True
        
    except Exception as e:
        print(f"❌ 同步行情失败 {symbol}: {e}")
        return False


# ==================== API路由 ====================

@router.get("/holdings")
async def get_holdings(user_id: str = Query(default="demo_user", description="用户ID")):
    """获取用户持仓列表（含实时行情）"""
    conn = get_db_connection()
    
    # 数据库可用时使用数据库，否则使用内存备份
    if conn:
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # 确保表存在
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS holdings (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        stock_code VARCHAR(20) NOT NULL,
                        stock_name VARCHAR(100) NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 0,
                        avg_cost DECIMAL(10, 2) NOT NULL DEFAULT 0,
                        market VARCHAR(20) DEFAULT 'A股',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, stock_code)
                    )
                """)
                
                # 确保用户存在
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        phone VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(100) DEFAULT '投资者',
                        password_hash VARCHAR(255) DEFAULT 'temp',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                cur.execute("""
                    INSERT INTO users (phone, name, password_hash) VALUES (%s, %s, 'temp123') ON CONFLICT DO NOTHING
                """, (user_id, '投资者'))
                
                # 插入初始数据（如果没有）
                cur.execute("""
                    INSERT INTO holdings (user_id, stock_code, stock_name, quantity, avg_cost) VALUES
                    ('demo_user', '600519.SH', '贵州茅台', 10, 1650.00),
                    ('demo_user', '300750.SZ', '宁德时代', 50, 200.00),
                    ('demo_user', '002594.SZ', '比亚迪', 30, 260.00)
                    ON CONFLICT DO NOTHING
                """)
                
                conn.commit()
                
                # 查询持仓
                cur.execute("""
                    SELECT stock_code, stock_name, quantity, avg_cost 
                    FROM holdings 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                """, (user_id,))
                holdings = cur.fetchall()
                # 将元组转换为字典
                holdings = [
                    {
                        "symbol": row["stock_code"],
                        "name": row["stock_name"],
                        "quantity": row["quantity"],
                        "avg_cost": row["avg_cost"]
                    }
                    for row in holdings
                ]
        except Exception as e:
            print(f"数据库错误: {e}")
            holdings = USER_PORTFOLIO_BACKUP.get(user_id, [])
        finally:
            conn.close()
    else:
        # 使用内存数据
        holdings = USER_PORTFOLIO_BACKUP.get(user_id, [
            {"symbol": "600519", "name": "贵州茅台", "quantity": 10, "avg_cost": 1650.0, "market": "A股"},
            {"symbol": "300750", "name": "宁德时代", "quantity": 50, "avg_cost": 200.0, "market": "A股"},
            {"symbol": "002594", "name": "比亚迪", "quantity": 30, "avg_cost": 260.0, "market": "A股"}
        ])
    
    if not holdings:
        return {
            "user_id": user_id,
            "holdings": [],
            "total_value": 0,
            "total_cost": 0,
            "total_profit": 0,
            "total_profit_percent": 0,
            "health_score": 0
        }
    
    # 获取实时行情
    enriched_holdings = []
    total_value = 0
    total_cost = 0
    
    for holding in holdings:
        quote = get_tushare_quote(holding["symbol"])
        
        if quote:
            current_price = quote["price"]
            market_value = current_price * float(holding["quantity"])
            cost_value = float(holding["avg_cost"]) * float(holding["quantity"])
            profit = market_value - cost_value
            profit_percent = (profit / cost_value * 100) if cost_value > 0 else 0
            
            enriched_holding = {
                **holding,
                "current_price": current_price,
                "market_value": round(market_value, 2),
                "cost_value": round(cost_value, 2),
                "profit": round(profit, 2),
                "profit_percent": round(profit_percent, 2),
                "change_percent": quote.get("change_percent", 0),
                "health_score": calculate_health_score(profit_percent, quote.get("change_percent", 0))
            }
            
            total_value += float(market_value)
            total_cost += float(cost_value)
        else:
            enriched_holding = {
                **holding,
                "current_price": holding["avg_cost"],
                "market_value": float(holding["avg_cost"]) * float(holding["quantity"]),
                "cost_value": float(holding["avg_cost"]) * float(holding["quantity"]),
                "profit": 0,
                "profit_percent": 0,
                "change_percent": 0,
                "health_score": 70,
                "data_source": "fallback"
            }
            total_value += enriched_holding["market_value"]
            total_cost += enriched_holding["cost_value"]
        
        enriched_holdings.append(enriched_holding)
    
    # 更新内存备份
    USER_PORTFOLIO_BACKUP[user_id] = list(holdings)
    
    total_profit = total_value - total_cost
    total_profit_percent = (total_profit / total_cost * 100) if total_cost > 0 else 0
    health_score = calculate_portfolio_health(enriched_holdings)
    
    return {
        "user_id": user_id,
        "holdings": enriched_holdings,
        "total_value": round(total_value, 2),
        "total_cost": round(total_cost, 2),
        "total_profit": round(total_profit, 2),
        "total_profit_percent": round(total_profit_percent, 2),
        "health_score": health_score,
        "updated_at": datetime.now().isoformat()
    }


@router.post("/holdings")
async def add_holding(request: HoldingRequest, user_id: str = Query(default="demo_user")):
    """添加持仓"""
    conn = get_db_connection()
    
    if conn:
        try:
            with conn.cursor() as cur:
                # 确保表存在
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS holdings (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(50) NOT NULL,
                        stock_code VARCHAR(20) NOT NULL,
                        stock_name VARCHAR(100) NOT NULL,
                        quantity INTEGER NOT NULL DEFAULT 0,
                        avg_cost DECIMAL(10, 2) NOT NULL DEFAULT 0,
                        market VARCHAR(20) DEFAULT 'A股',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id, stock_code)
                    )
                """)
                conn.commit()
                
                # 检查是否已存在
                cur.execute("""
                    SELECT quantity, avg_cost FROM holdings 
                    WHERE user_id = %s AND stock_code = %s
                """, (user_id, request.symbol))
                existing = cur.fetchone()
                
                if existing:
                    old_qty, old_cost = existing
                    total_qty = old_qty + request.quantity
                    total_cost_value = (old_qty * old_cost) + (request.quantity * request.avg_cost)
                    new_avg_cost = round(total_cost_value / total_qty, 2)
                    
                    cur.execute("""
                        UPDATE holdings 
                        SET quantity = %s, avg_cost = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND stock_code = %s
                    """, (total_qty, new_avg_cost, user_id, request.symbol))
                else:
                    cur.execute("""
                        INSERT INTO holdings (user_id, stock_code, stock_name, quantity, avg_cost)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (user_id, request.symbol, request.name, request.quantity, request.avg_cost))
                
                conn.commit()
        except Exception as e:
            conn.rollback()
            # 使用内存备份
            if user_id not in USER_PORTFOLIO_BACKUP:
                USER_PORTFOLIO_BACKUP[user_id] = []
            
            existing = next((h for h in USER_PORTFOLIO_BACKUP[user_id] if h["symbol"] == request.symbol), None)
            if existing:
                total_qty = existing["quantity"] + request.quantity
                total_cost = (existing["quantity"] * existing["avg_cost"]) + (request.quantity * request.avg_cost)
                existing["quantity"] = total_qty
                existing["avg_cost"] = round(total_cost / total_qty, 2)
            else:
                USER_PORTFOLIO_BACKUP[user_id].append({
                    "symbol": request.symbol,
                    "name": request.name,
                    "quantity": request.quantity,
                    "avg_cost": request.avg_cost,
                    "market": "A股"
                })
        finally:
            conn.close()
    else:
        # 使用内存备份
        if user_id not in USER_PORTFOLIO_BACKUP:
            USER_PORTFOLIO_BACKUP[user_id] = []
        
        existing = next((h for h in USER_PORTFOLIO_BACKUP[user_id] if h["symbol"] == request.symbol), None)
        if existing:
            total_qty = existing["quantity"] + request.quantity
            total_cost = (existing["quantity"] * existing["avg_cost"]) + (request.quantity * request.avg_cost)
            existing["quantity"] = total_qty
            existing["avg_cost"] = round(total_cost / total_qty, 2)
        else:
            USER_PORTFOLIO_BACKUP[user_id].append({
                "symbol": request.symbol,
                "name": request.name,
                "quantity": request.quantity,
                "avg_cost": request.avg_cost,
                "market": "A股"
            })
    
    # 同步行情数据到SQLite（异步执行，不阻塞返回）
    try:
        sync_stock_quote(request.symbol)
    except Exception as e:
        print(f"同步行情数据失败（非阻塞）: {e}")
    
    return {"success": True, "message": f"已添加 {request.name} 到持仓"}


@router.delete("/holdings/{symbol}")
async def remove_holding(symbol: str, user_id: str = Query(default="demo_user")):
    """删除持仓"""
    conn = get_db_connection()
    
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM holdings WHERE user_id = %s AND stock_code = %s
                """, (user_id, symbol))
                deleted = cur.rowcount
                conn.commit()
                
                if deleted == 0:
                    raise HTTPException(status_code=404, detail="未找到该持仓")
        except HTTPException:
            raise
        except Exception as e:
            conn.rollback()
            # 从内存备份删除
            if user_id in USER_PORTFOLIO_BACKUP:
                USER_PORTFOLIO_BACKUP[user_id] = [h for h in USER_PORTFOLIO_BACKUP[user_id] if h["symbol"] != symbol]
        finally:
            conn.close()
    else:
        # 从内存备份删除
        if user_id in USER_PORTFOLIO_BACKUP:
            original_len = len(USER_PORTFOLIO_BACKUP[user_id])
            USER_PORTFOLIO_BACKUP[user_id] = [h for h in USER_PORTFOLIO_BACKUP[user_id] if h["symbol"] != symbol]
            if len(USER_PORTFOLIO_BACKUP[user_id]) == original_len:
                raise HTTPException(status_code=404, detail="未找到该持仓")
    
    return {"success": True, "message": f"已删除股票 {symbol}"}


# ==================== 预警系统 ====================

def generate_real_alerts(user_id: str, holdings: list) -> list:
    """基于持仓数据生成真实预警"""
    alerts = []
    
    for holding in holdings:
        profit_percent = holding.get('profit_percent', 0)
        change_percent = holding.get('change_percent', 0)
        
        # 亏损预警
        if profit_percent < -10:
            alerts.append({
                "symbol": holding['symbol'],
                "name": holding['name'],
                "type": "loss_warning",
                "severity": "high",
                "message": f"{holding['name']}持仓亏损超过10%({profit_percent:.1f}%)，建议关注止损"
            })
        elif profit_percent < -5:
            alerts.append({
                "symbol": holding['symbol'],
                "name": holding['name'],
                "type": "loss_warning",
                "severity": "medium",
                "message": f"{holding['name']}持仓亏损超过5%({profit_percent:.1f}%)"
            })
        
        # 今日大涨预警
        if change_percent > 5:
            alerts.append({
                "symbol": holding['symbol'],
                "name": holding['name'],
                "type": "price_surge",
                "severity": "medium",
                "message": f"{holding['name']}今日大涨{change_percent:.1f}%，可考虑适量减仓"
            })
        
        # 今日大跌预警
        if change_percent < -5:
            alerts.append({
                "symbol": holding['symbol'],
                "name": holding['name'],
                "type": "price_drop",
                "severity": "medium",
                "message": f"{holding['name']}今日大跌{abs(change_percent):.1f}%，建议关注支撑位"
            })
        
        # 盈利止盈提醒
        if profit_percent > 20:
            alerts.append({
                "symbol": holding['symbol'],
                "name": holding['name'],
                "type": "profit_take",
                "severity": "low",
                "message": f"{holding['name']}盈利超过20%({profit_percent:.1f}%)，可考虑止盈"
            })
    
    return alerts


@router.get("/alerts")
async def get_alerts(user_id: str = Query(default="demo_user")):
    """获取用户预警信息（基于真实持仓数据生成）"""
    # 先获取用户持仓
    result = await get_holdings(user_id)
    holdings = result.get("holdings", [])
    
    # 生成真实预警
    alerts = generate_real_alerts(user_id, holdings)
    
    return {
        "user_id": user_id,
        "alert_count": len(alerts),
        "alerts": alerts
    }


# ==================== 工具函数 ====================

def calculate_health_score(profit_percent: float, change_percent: float) -> int:
    """计算个股健康度分数"""
    score = 70
    
    if profit_percent > 10:
        score += 15
    elif profit_percent > 0:
        score += 10
    elif profit_percent > -5:
        score -= 5
    else:
        score -= 15
    
    if change_percent > 3:
        score += 5
    elif change_percent < -3:
        score -= 5
    
    return max(0, min(100, score))


def calculate_portfolio_health(holdings: list) -> int:
    """计算组合整体健康度"""
    if not holdings:
        return 0
    
    total_score = sum(h.get("health_score", 70) for h in holdings)
    avg_score = total_score / len(holdings)
    
    total_profit = sum(h.get("profit", 0) for h in holdings)
    if total_profit > 0:
        avg_score += 5
    elif total_profit < -1000:
        avg_score -= 10
    
    return max(0, min(100, int(avg_score)))
