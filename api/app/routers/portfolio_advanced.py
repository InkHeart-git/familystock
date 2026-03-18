"""
高级组合分析功能
资产配置建议、组合相关性分析、再平衡提醒
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pymysql
from datetime import datetime, timedelta
import math

router_portfolio_advanced = APIRouter(prefix="/api/portfolio", tags=["高级组合分析"])

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

@router_portfolio_advanced.get("/allocation/recommend")
async def get_allocation_recommendation(current_user: dict = Depends(get_current_user)):
    """获取智能资产配置建议"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取用户持仓
        cursor.execute("""
        SELECT p.stock_code, p.quantity, b.name, b.industry, d.close
        FROM portfolio p
        LEFT JOIN stock_basic b ON p.stock_code = b.symbol
        LEFT JOIN stock_daily d ON b.ts_code = d.ts_code
        WHERE p.user_phone = %s
        ORDER BY d.trade DESC
        """, (current_user["phone"],))
        portfolio = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not portfolio:
            return {
                "recommendations": [],
                "analysis": "暂无持仓数据，无法提供资产配置建议"
            }
        
        # 计算当前资产分布
        total_value = 0
        industry_dist = {}
        
        for item in portfolio:
            value = float(item["close"]) * int(item["quantity"])
            total_value += value
            industry = item["industry"] or "其他"
            
            if industry in industry_dist:
                industry_dist[industry] += value
            else:
                industry_dist[industry] = value
        
        # 风险平价模型简化版
        risk_profiles = {
            "保守型": {
                "stock_ratio": {"食品饮料": 0.4, "医药生物": 0.3, "公用事业": 0.2, "其他": 0.1},
                "description": "追求稳健收益，风险偏好低",
                "expected_return": 0.08
            },
            "r稳健型": {
                "stock_ratio": {"食品饮料": 0.35, "医药生物": 0.25, "公用事业": 0.2, "科技": 0.15, "其他": 0.05},
                "description": "平衡风险和收益，中等风险偏好",
                "expected_return": 0.12
            },
            "积极型": {
                "stock_ratio": {"食品饮料": 0.3, "医药生物": 0.2, "科技": 0.3, "新能源": 0.15, "其他": 0.05},
                "description": "追求高收益，可接受较高波动",
                "expected_return": 0.18
            },
            "积极进取型": {
                "stock_ratio": {"科技": 0.4, "新能源": 0.3, "医药生物": 0.2, "食品饮料": 0.08, "其他": 0.02},
                "description": "追求最大化收益，风险偏好很高",
                "expected_return": 0.25
            }
        }
        
        # 分析用户当前风险偏好（简化为保守/稳健/积极）
        current_industries = set(item["industry"] or "其他" for item in portfolio)
        current_risk_profile = "r稳健型"
        
        if "科技" in current_industries or "新能源" in current_industries:
            current_risk_profile = "积极型"
        elif len(current_industries) <= 2:
            current_risk_profile = "保守型"
        
        # 生成优化建议
        target_ratio = risk_profiles[current_risk_profile]["stock_ratio"]
        recommendations = []
        
        for target_industry, target_percent in target_ratio.items():
            current_value = industry_dist.get(target_industry, 0)
            current_percent = current_value / total_value if total_value > 0.0 else 0.0
            target_value = total_value * target_percent
            diff_value = target_value - current_value
            diff_percent = abs(target_percent - current_percent) * 100
            
            if abs(diff_percent) > 20:  # 超过20%才建议调整
                recommendations.append({
                    "industry": target_industry,
                    "current_value": round(current_value, 2),
                    "current_percent": round(current_percent * 100, 1),
                    "target_value": round(target_value, 2),
                    "target_percent": round(target_percent * 100, 1),
                    "diff_value": round(diff_value, 2),
                    "diff_percent": round(diff_percent, 1),
                    "action": "加仓" if diff_value > 0 else "减仓",
                    "reason": f"当前占比{round(current_percent * 100, 1)}%，建议占比{round(target_percent * 100, 1)}%"
                })
        
        # 按调整幅度排序
        recommendations.sort(key=lambda x: abs(x["diff_percent"]), reverse=True)
        recommendations = recommendations[:5]  # 只返回最重要的5个建议
        
        return {
            "current_profile": current_risk_profile,
            "current_allocation": {industry: round(industry_dist.get(industry, 0) / total_value * 100 if total_value > 0.0 else 0.0 for industry in industry_dist},
            "target_profile": current_risk_profile,
            "recommendations": recommendations,
            "risk_profiles": risk_profiles,
            "analysis": f"当前持仓{len(portfolio)}只股票，分布在{len(industry_dist)}个行业，建议采用{current_risk_profile}配置以优化风险收益平衡。"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取资产配置建议失败: {str(e)}")

@router_portfolio_advanced.get("/correlation/matrix")
async def get_correlation_matrix(current_user: dict = Depends(get_current_user)):
    """获取组合相关性矩阵"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取用户持仓（最多5只）
        cursor.execute("""
        SELECT p.stock_code, b.name, d.close
        FROM portfolio p
        LEFT JOIN stock_basic b ON p.stock_code = b.symbol
        LEFT JOIN stock_daily d ON
            b.ts_code = d.ts_code AND d.trade_date = (
                SELECT MAX(trade_date) FROM stock_daily 
                WHERE ts_code = b.ts_code AND trade_date <= CURDATE()
            )
        WHERE p.user_phone = %s
        ORDER BY d.trade_date DESC
        LIMIT 5
        """, (current_user["phone"],))
        portfolio = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if len(portfolio) < 2:
            return {
                "matrix": matrix.tolist() if 'matrix' in locals() else [],
                "stocks": [],
                "analysis": "持仓少于2只，无法计算相关性"
            }
        
        # 获取历史价格数据（简化版，使用最近20天）
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=20)).strftime("%Y%m%d")
        
        stock_prices = {}
        for item in portfolio:
            ts_code = item["ts_code"]
            cursor = get_db_connection()
            price_cursor = cursor.cursor(pymysql.cursors.DictCursor)
            
            price_cursor.execute("""
            SELECT trade_date, close
            FROM stock_daily 
            WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s
            ORDER BY trade_date ASC
            """, (ts_code, start_date, end_date))
            
            prices = price_cursor.fetchall()
            price_cursor.close()
            cursor.close()
            
            if len(prices) > 10:
                close_prices = [float(p["close"]) for p in prices]
                # 计算收益率
                returns = []
                for i in range(1, len(close_prices)):
                    if close_prices[i-1] and close_prices[i-1] > 0:
                        returns.append((close_prices[i] - close_prices[i-1]) / close_prices[i-1])
                
                if returns:
                    stock_prices[item["ts_code"]] = {
                        "name": item["name"],
                        "prices": close_prices,
                        "returns": returns
                    }
        
        # 计算相关性矩阵（简化版）
        stock_list = list(stock_prices.keys())
        matrix = []
        
        for i, stock_a in enumerate(stock_list):
            row = []
            for j, stock_b in enumerate(stock_list):
                if i == j:
                    correlation = 1.0
                elif stock_a in stock_prices and stock_b in stock_prices:
                    returns_a = stock_prices[stock_a]["returns"]
                    returns_b = stock_prices[stock_b]["returns"]
                    
                    # 取相同长度
                    min_len = min(len(returns_a), len(returns_b))
                    correlation = 0.0
                    
                    for k in range(min_len):
                        correlation += returns_a[k] * returns_b[k]
                    
                    correlation /= min_len
                else:
                    correlation = 0.0
                
                row.append(correlation)
            matrix.append(row)
        
        # 识别高风险组合
        high_correlation_pairs = []
        for i in range(len(stock_list)):
            for j in range(i+1, len(stock_list)):
                if abs(matrix[i][j]) > 0.7:  # 相关系数>0.7为高度相关
                    high_correlation_pairs.append({
                        "stock_a": stock_list[i],
                        "stock_b": stock_list[j],
                        "correlation": matrix[i][j],
                        "risk_level": "高度相关",
                        "suggestion": "建议分散投资，降低单一行业风险"
                    })
        
        return {
            "matrix": matrix,
            "stocks": stock_list,
            "high_correlation_risk": high_correlation_pairs,
            "analysis": f"持仓{len(portfolio)}只股票，已计算{len(stock_list)}x{len(stock_list)}相关性矩阵，发现{len(high_correlation_pairs)}对高度相关股票对。"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取相关性矩阵失败: {str(e)}")

# 演示接口
@router_portfolio_advanced.get("/allocation/demo")
async def get_demo_allocation():
    """获取资产配置演示数据"""
    return {
        "current_profile": "r稳健型",
        "current_allocation": {
            "食品饮料": 35,
            "科技": 30,
            "医药生物": 25,
            "其他": 10
        },
        "target_profile": "r稳健型",
        "recommendations": [
            {
                "industry": "科技",
                "current_value": 30000,
                "current_percent": 30,
                "target_value": 45000,
                "target_percent": 45,
                "diff_value": 15000,
                "diff_percent": 15,
                "action": "加仓",
                "reason": "当前占比30%，建议占比45%"
            },
            {
                "industry": "医药生物",
                "current_value": 25000,
                "current_percent": 25,
                "target_value": 20000,
                "target_percent": 20,
                "diff_value": -5000,
                "diff_percent": -5,
                "action": "减仓",
                "reason": "当前占比25%，建议占比20%"
            }
        ],
        "risk_profiles": {
            "保守型": {
                "expected_return": 0.08,
                "description": "追求稳健收益"
            },
            "r稳健型": {
                "expected_return": 0.12,
                "description": "平衡风险和收益"
            },
            "积极型": {
                "expected_return": 0.18,
                "description": "追求高收益"
            }
        }
    }
