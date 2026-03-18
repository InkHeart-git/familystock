"""
组合分析接口
包含持仓行业分布、收益分析、风险指标等功能
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pymysql
from datetime import datetime, timedelta
# from app.core.auth import get_current_user

router_portfolio_analysis = APIRouter(prefix="/api/portfolio-analysis", tags=["组合分析"])

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "user": "familystock",
    "password": "Familystock@2026",
    "database": "familystock",
    "charset": "utf8mb4"
}

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        raise HTTPException(status_code=500, detail="数据库连接失败")

@router_portfolio_analysis.get("/list")
async def get_user_portfolio(user_id: str = Query(default="demo_user")):
    """获取当前用户的持仓列表"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        cursor.execute("""
        SELECT p.*, b.name, b.industry, b.market,
               d.close, d.pct_chg, d.change
        FROM portfolio p
        LEFT JOIN stock_basic b ON p.stock_code = b.symbol
        LEFT JOIN stock_daily d ON b.ts_code = d.ts_code
        WHERE p.user_phone = %s
        ORDER BY d.trade_date DESC
        """, (current_user["phone"],))
        
        portfolio = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # 计算总盈亏和收益率
        total_cost = 0
        total_current_value = 0
        total_profit = 0
        
        formatted_portfolio = []
        for item in portfolio:
            cost = float(item["cost_price"]) * int(item["quantity"])
            current_value = float(item["close"] or 0) * int(item["quantity"])
            profit = current_value - cost
            profit_rate = (profit / cost) * 100 if cost > 0 else 0
            
            total_cost += cost
            total_current_value += current_value
            total_profit += profit
            
            formatted_portfolio.append({
                "id": item["id"],
                "stock_code": item["stock_code"],
                "stock_name": item["name"],
                "industry": item["industry"],
                "market": item["market"],
                "cost_price": float(item["cost_price"]),
                "quantity": int(item["quantity"]),
                "current_price": float(item["close"] or 0),
                "change": float(item["change"] or 0),
                "pct_chg": float(item["pct_chg"] or 0),
                "profit": profit,
                "profit_rate": profit_rate,
                "current_value": current_value,
                "added_at": item["created_at"]
            })
        
        total_profit_rate = (total_profit / total_cost) * 100 if total_cost > 0 else 0
        
        return {
            "portfolio": formatted_portfolio,
            "summary": {
                "total_cost": total_cost,
                "total_current_value": total_current_value,
                "total_profit": total_profit,
                "total_profit_rate": total_profit_rate,
                "stock_count": len(formatted_portfolio)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取持仓失败: {str(e)}")

@router_portfolio_analysis.get("/analysis")
async def get_portfolio_analysis(user_id: str = Query(default="demo_user")):
    """获取组合分析数据：行业分布、风险指标等"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取用户持仓
        cursor.execute("""
        SELECT p.stock_code, p.cost_price, p.quantity, b.name, b.industry,
               d.close, d.pct_chg
        FROM portfolio p
        LEFT JOIN stock_basic b ON p.stock_code = b.symbol
        LEFT JOIN stock_daily d ON b.ts_code = d.ts_code
        WHERE p.user_phone = %s
        ORDER BY d.trade_date DESC
        """, (current_user["phone"],))
        
        portfolio = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not portfolio:
            return {
                "industry_distribution": [],
                "performance": {
                    "total_profit": 0,
                    "total_profit_rate": 0,
                    "max_drawdown": 0,
                    "sharpe_ratio": 0,
                    "volatility": 0
                },
                "correlation_analysis": [],
                "benchmark_comparison": {
                    "portfolio_return": 0,
                    "hs300_return": 0,
                    "excess_return": 0
                }
            }
        
        # 计算行业分布
        industry_map = {}
        total_value = 0
        
        for item in portfolio:
            current_value = float(item["close"] or 0) * int(item["quantity"])
            total_value += current_value
            industry = item["industry"] or "其他"
            
            if industry in industry_map:
                industry_map[industry] += current_value
            else:
                industry_map[industry] = current_value
        
        # 格式化行业分布
        industry_distribution = []
        for industry, value in industry_map.items():
            percentage = (value / total_value) * 100 if total_value > 0 else 0
            industry_distribution.append({
                "industry": industry,
                "value": value,
                "percentage": round(percentage, 2)
            })
        
        # 按占比排序
        industry_distribution.sort(key=lambda x: x["percentage"], reverse=True)
        
        # 计算收益指标
        total_cost = 0
        total_current_value = 0
        total_profit = 0
        
        for item in portfolio:
            cost = float(item["cost_price"]) * int(item["quantity"])
            current_value = float(item["close"] or 0) * int(item["quantity"])
            profit = current_value - cost
            
            total_cost += cost
            total_current_value += current_value
            total_profit += profit
        
        total_profit_rate = (total_profit / total_cost) * 100 if total_cost > 0 else 0
        
        return {
            "industry_distribution": industry_distribution,
            "performance": {
                "total_profit": total_profit,
                "total_profit_rate": round(total_profit_rate, 2),
                "max_drawdown": 0,  # 后续补充
                "sharpe_ratio": 0,   # 后续补充
                "volatility": 0      # 后续补充
            },
            "correlation_analysis": [],  # 后续补充
            "benchmark_comparison": {
                "portfolio_return": round(total_profit_rate, 2),
                "hs300_return": 3.25,  # 示例数据，后续替换为真实数据
                "excess_return": round(total_profit_rate - 3.25, 2)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取组合分析失败: {str(e)}")

# 演示接口，无需登录，返回模拟数据
@router_portfolio_analysis.get("/demo")
async def get_demo_portfolio():
    """获取演示持仓数据"""
    demo_data = [
        {
            "id": 1,
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "industry": "食品饮料",
            "market": "A股",
            "cost_price": 1700.0,
            "quantity": 100,
            "current_price": 1725.0,
            "change": 40.0,
            "pct_chg": 2.35,
            "profit": 25000.0,
            "profit_rate": 1.47,
            "current_value": 172500.0,
            "added_at": "2026-03-01 10:00:00"
        },
        {
            "id": 2,
            "stock_code": "002594",
            "stock_name": "比亚迪",
            "industry": "汽车",
            "market": "A股",
            "cost_price": 250.0,
            "quantity": 200,
            "current_price": 265.0,
            "change": 8.5,
            "pct_chg": 3.21,
            "profit": 30000.0,
            "profit_rate": 6.0,
            "current_value": 53000.0,
            "added_at": "2026-03-05 14:30:00"
        },
        {
            "id": 3,
            "stock_code": "000858",
            "stock_name": "五粮液",
            "industry": "食品饮料",
            "market": "A股",
            "cost_price": 165.0,
            "quantity": 300,
            "current_price": 172.0,
            "change": 4.2,
            "pct_chg": 2.5,
            "profit": 2100.0,
            "profit_rate": 1.27,
            "current_value": 51600.0,
            "added_at": "2026-03-10 09:30:00"
        }
    ]
    
    total_cost = 1700*100 + 250*200 + 165*300
    total_current_value = 1725*100 + 265*200 + 172*300
    total_profit = total_current_value - total_cost
    total_profit_rate = (total_profit / total_cost) * 100
    
    return {
        "portfolio": demo_data,
        "summary": {
            "total_cost": total_cost,
            "total_current_value": total_current_value,
            "total_profit": total_profit,
            "total_profit_rate": round(total_profit_rate, 2),
            "stock_count": 3
        }
    }

@router_portfolio_analysis.get("/analysis/demo")
async def get_demo_analysis():
    """获取演示组合分析数据"""
    return {
        "industry_distribution": [
            {"industry": "食品饮料", "value": 224100.0, "percentage": 68.2},
            {"industry": "汽车", "value": 53000.0, "percentage": 16.1},
            {"industry": "新能源", "value": 32500.0, "percentage": 9.9},
            {"industry": "其他", "value": 19000.0, "percentage": 5.8}
        ],
        "performance": {
            "total_profit": 30100.0,
            "total_profit_rate": 9.87,
            "max_drawdown": 2.34,
            "sharpe_ratio": 1.85,
            "volatility": 12.56
        },
        "benchmark_comparison": {
            "portfolio_return": 9.87,
            "hs300_return": 3.25,
            "excess_return": 6.62
        }
    }
