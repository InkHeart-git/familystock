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

router = APIRouter(prefix="/api/portfolio", tags=["持仓管理"])

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
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None


def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cur:
            # 创建用户表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) DEFAULT '投资者',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建持仓表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS holdings (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 0,
                    avg_cost DECIMAL(10, 2) NOT NULL DEFAULT 0,
                    market VARCHAR(20) DEFAULT 'A股',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, symbol)
                )
            """)
            
            # 创建预警表
            cur.execute("""
                CREATE TABLE IF NOT EXISTS alerts (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(50) NOT NULL,
                    symbol VARCHAR(20) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    alert_type VARCHAR(50) NOT NULL,
                    severity VARCHAR(20) NOT NULL,
                    message TEXT NOT NULL,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 插入默认用户
            cur.execute("""
                INSERT INTO users (user_id, name) 
                VALUES ('demo_user', '测试用户') 
                ON CONFLICT DO NOTHING
            """)
            
            # 插入初始持仓
            cur.execute("""
                INSERT INTO holdings (user_id, symbol, name, quantity, avg_cost, market) 
                VALUES 
                    ('demo_user', '600519', '贵州茅台', 10, 1650.00, 'A股'),
                    ('demo_user', '300750', '宁德时代', 50, 200.00, 'A股'),
                    ('demo_user', '002594', '比亚迪', 30, 260.00, 'A股')
                ON CONFLICT DO NOTHING
            """)
            
            conn.commit()
            print("✅ 数据库初始化成功")
            return True
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# 初始化数据库
init_db()


# ==================== 行情获取 ====================

def get_tushare_quote(symbol: str):
    """从Tushare获取实时行情"""
    try:
        if "." not in symbol:
            ts_code = f"{symbol}.SH" if symbol.startswith("6") else f"{symbol}.SZ"
        else:
            ts_code = symbol
        
        payload = {
            "api_name": "daily",
            "token": TUSHARE_TOKEN,
            "params": {"ts_code": ts_code, "limit": 1}
        }
        
        response = requests.post(TUSHARE_API_URL, json=payload, timeout=10)
        result = response.json()
        
        if result.get("code") != 0 or not result.get("data", {}).get("items"):
            return None
        
        fields = result["data"]["fields"]
        item = result["data"]["items"][0]
        data = dict(zip(fields, item))
        
        return {
            "symbol": symbol,
            "price": float(data.get("close", 0)),
            "open": float(data.get("open", 0)),
            "high": float(data.get("high", 0)),
            "low": float(data.get("low", 0)),
            "change": float(data.get("change", 0)),
            "change_percent": float(data.get("pct_chg", 0)),
            "volume": int(data.get("vol", 0)),
            "amount": float(data.get("amount", 0)),
            "updated_at": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"获取行情失败 {symbol}: {e}")
        return None


# ==================== API路由 ====================

@router.get("/holdings")
async def get_holdings(user_id: str = Query(default="demo_user", description="用户ID")):
    """获取用户持仓列表（含实时行情）"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="数据库连接失败")
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT symbol, name, quantity, avg_cost, market 
                FROM holdings 
                WHERE user_id = %s 
                ORDER BY created_at DESC
            """, (user_id,))
            holdings = cur.fetchall()
        
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
                market_value = current_price * holding["quantity"]
                cost_value = holding["avg_cost"] * holding["quantity"]
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
                
                total_value += market_value
                total_cost += cost_value
            else:
                # API失败时使用成本价
                enriched_holding = {
                    **holding,
                    "current_price": holding["avg_cost"],
                    "market_value": holding["avg_cost"] * holding["quantity"],
                    "cost_value": holding["avg_cost"] * holding["quantity"],
                    "profit": 0,
                    "profit_percent": 0,
                    "change_percent": 0,
                    "health_score": 70,
                    "data_source": "fallback"
                }
                total_value += enriched_holding["market_value"]
                total_cost += enriched_holding["cost_value"]
            
            enriched_holdings.append(enriched_holding)
        
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
    finally:
        conn.close()


@router.post("/holdings")
async def add_holding(request: HoldingRequest, user_id: str = Query(default="demo_user")):
    """添加持仓"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="数据库连接失败")
    
    try:
        with conn.cursor() as cur:
            # 检查是否已存在
            cur.execute("""
                SELECT quantity, avg_cost FROM holdings 
                WHERE user_id = %s AND symbol = %s
            """, (user_id, request.symbol))
            existing = cur.fetchone()
            
            if existing:
                # 更新持仓
                old_qty, old_cost = existing
                total_qty = old_qty + request.quantity
                total_cost_value = (old_qty * old_cost) + (request.quantity * request.avg_cost)
                new_avg_cost = round(total_cost_value / total_qty, 2)
                
                cur.execute("""
                    UPDATE holdings 
                    SET quantity = %s, avg_cost = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s AND symbol = %s
                """, (total_qty, new_avg_cost, user_id, request.symbol))
            else:
                # 新增持仓
                cur.execute("""
                    INSERT INTO holdings (user_id, symbol, name, quantity, avg_cost, market)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (user_id, request.symbol, request.name, request.quantity, request.avg_cost, 'A股'))
            
            conn.commit()
            return {"success": True, "message": f"已添加 {request.name} 到持仓"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"添加失败: {str(e)}")
    finally:
        conn.close()


@router.delete("/holdings/{symbol}")
async def remove_holding(symbol: str, user_id: str = Query(default="demo_user")):
    """删除持仓"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="数据库连接失败")
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM holdings WHERE user_id = %s AND symbol = %s
            """, (user_id, symbol))
            
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="未找到该持仓")
            
            conn.commit()
            return {"success": True, "message": f"已删除股票 {symbol}"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
    finally:
        conn.close()


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
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="数据库连接失败")
    
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT symbol, name, quantity, avg_cost FROM holdings 
                WHERE user_id = %s
            """, (user_id,))
            holdings = cur.fetchall()
        
        # 获取实时行情并计算盈亏
        enriched_holdings = []
        for holding in holdings:
            quote = get_tushare_quote(holding["symbol"])
            if quote:
                current_price = quote["price"]
                profit = (current_price - holding["avg_cost"]) * holding["quantity"]
                profit_percent = ((current_price - holding["avg_cost"]) / holding["avg_cost"] * 100) if holding["avg_cost"] > 0 else 0
                
                enriched_holdings.append({
                    **holding,
                    "profit_percent": profit_percent,
                    "change_percent": quote.get("change_percent", 0)
                })
        
        # 生成真实预警
        alerts = generate_real_alerts(user_id, enriched_holdings)
        
        return {
            "user_id": user_id,
            "alert_count": len(alerts),
            "alerts": alerts
        }
    finally:
        conn.close()


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
