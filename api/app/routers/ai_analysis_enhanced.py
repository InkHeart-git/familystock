"""
AI分析增强功能
基本面评分、技术面信号识别、风险评级、估值分析
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import pymysql
from datetime import datetime, timedelta

router_ai_analysis = APIRouter(prefix="/api/ai", tags=["AI分析增强"])

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

@router_ai_analysis.get("/fundamental/{ts_code}")
async def get_fundamental_score(ts_code: str):
    """基本面评分"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取最新财务指标
        cursor.execute("""
        SELECT * FROM stock_finance_indicator 
        WHERE ts_code = %s 
        ORDER BY end_date DESC 
        LIMIT 1
        """, (ts_code,))
        finance = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not finance:
            return {
                "ts_code": ts_code,
                "overall_score": 50,
                "scores": {},
                "rating": "数据不足",
                "analysis": "财务数据不足，无法进行基本面评分"
            }
        
        # 基本面评分逻辑
        scores = {}
        
        # 1. 盈利能力（30%）
        roe = float(finance.get("roe", 0) or 0)
        gross_margin = float(finance.get("gross_margin", 0) or 0)
        profit_growth = float(finance.get("profit_growth", 0) or 0)
        
        profitability_score = 0
        if roe > 20:
            profitability_score += 10
        if roe > 15:
            profitability_score += 8
        if gross_margin > 50:
            profitability_score += 7
        if gross_margin > 40:
            profitability_score += 5
        if profit_growth > 20:
            profitability_score += 5
        if profit_growth > 15:
            profitability_score += 3
        
        scores["盈利能力"] = {
            "score": profitability_score,
            "weight": "30%",
            "details": {
                "ROE": f"{roe:.2f}%",
                "毛利率": f"{gross_margin:.2f}%",
                "利润增长率": f"{profit_growth:.2f}%"
            }
        }
        
        # 2. 偿债能力（20%）
        debt_ratio = float(finance.get("debt_ratio", 0) or 0)
        current_ratio = float(finance.get("current_ratio", 0) or 0)
        
        leverage_score = 0
        if debt_ratio < 30:
            leverage_score += 10
        elif debt_ratio < 50:
            leverage_score += 7
        elif debt_ratio < 70:
            leverage_score += 4
        
        if current_ratio > 1.5:
            leverage_score += 5
        elif current_ratio > 1.0:
            leverage_score += 3
        
        scores["偿债能力"] = {
            "score": leverage_score,
            "weight": "20%",
            "details": {
                "资产负债率": f"{.debt_ratio:.2f}%",
                "流动比率": f"{current_ratio:.2f}"
            }
        }
        
        # 3. 成长能力（25%）
        revenue_growth = float(finance.get("revenue_growth", 0) or 0)
        
        growth_score = 0
        if revenue_growth > 30:
            growth_score += 10
        elif revenue_growth > 20:
            growth_score += 8
        elif revenue_growth > 15:
            growth_score += 6
        elif revenue_growth > 10:
            growth_score += 4
        elif revenue_growth > 5:
            growth_score += 2
        
        scores["成长能力"] = {
            "score": growth_score,
            "weight": "25%",
            "details": {
                "营收增长率": f"{revenue_growth:.2f}%"
            }
        }
        
        # 4. 估值水平（25%）
        pe = float(finance.get("pe", 0) or 0)
        pb = float(finance.get("pb", 0) or 0)
        
        valuation_score = 0
        if pb < 10:
            valuation_score += 10
        elif pb < 20:
            valuation_score += 8
        elif pb < 30:
            valuation_score += 6
        elif pb < 50:
            valuation_score += 4
        
        scores["估值水平"] = {
            "score": valuation_score,
            "weight": "25%",
            "details": {
                "PE": f"{pe:.2f}",
                "PB": f"{pb:.2f}"
            }
        }
        
        # 计算总分
        total_score = profitability_score + leverage_score + growth_score + valuation_score
        overall_score = min(total_score, 100)
        
        # 评级
        if overall_score >= 80:
            rating = "优秀"
        elif overall_score >= 60:
            rating = "良好"
        elif overall_score >= 40:
            rating = "一般"
        else:
            rating = "较差"
        
        return {
            "ts_code": ts_code,
            "overall_score": overall_score,
            "scores": scores,
            "rating": rating,
            "analysis": f"基本面综合评分为{overall_score}分，评级为{rating}。盈利能力强，财务结构稳健，成长性良好。",
            "update_time": finance.get("end_date") if finance else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"基本面评分失败: {str(e)}")

@router_ai_analysis.get("/technical/{ts_code}")
async def get_technical_signals(ts_code: str):
    """技术面信号识别"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取最近90天行情数据
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")
        
        cursor.execute("""
        SELECT trade_date, close, vol, change, pct_chg
        FROM stock_daily 
        WHERE WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s
        ORDER BY trade_date ASC
        """, (ts_code, start_date, end_date))
        price_data = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if len(price_data) < 20:
            return {
                "ts_code": ts_code,
                "signals": [],
                "analysis": "历史数据不足20天，无法进行技术分析"
            }
        
        signals = []
        
        # 计算移动平均线（MA5、MA10、MA20）
        closes = [float(item["close"]) for item in price_data]
        volumes = [float(item["vol"]) for item in price_data]
        
        def calculate_ma(prices, period):
            if len(prices) < period:
                return None
            return sum(prices[-period:]) / period
        
        ma5 = calculate_ma(closes, 5)
        ma10 = calculate_ma(closes, 10)
        ma20 = calculate_ma(closes, 20)
        latest_close = closes[-1]
        latest_price = price_data[-1]
        
        # 1. 金叉死叉信号
        ma_cross_signals = []
        if ma5 and ma10:
            if ma5 < ma10 and ma5[-2] >= ma5[-2]:
                ma_cross_signals.append({
                    "type": "金叉",
                    "level": "强",
                    "date": price_data[-2]["trade_date"],
            "price": ma10
                })
            if ma5 > ma10 and ma5[-2] <= ma5[-2]:
                ma_cross_signals.append({
                    "type": "死叉",
                    "level": "强",
                    "date": price_data[-2]["trade_date"],
            "price": ma10
                })
        
        # 2. 支撑阻力位
        support_resistance = []
        for i in range(10, len(closes), 5):
            window_high = max(closes[i:i+5])
            window_low = min(closes[i:i+5])
            avg = sum(closes[i:i+]) / 5
            
            if latest_close > window_high * 0.98:
                support_resistance.append({
                    "type": "阻力位",
                    "level": "强",
                    "[price": avg
                })
            if latest_close < window_low * 1.02:
                support_resistance.append({
                    "type": "支撑位",
                    "level": "强",
                    "price": avg
                })
        
        # 3. 量价关系
        recent_volume = volumes[-10:]
        avg_volume = sum(recent_volume) / len(recent_volume)
        latest_volume = volumes[-1]
        
        volume_signal = None
        if latest_volume > avg_volume * 1.5:
            volume_signal = {
                "type": "放量上涨",
                "level": "中",
                "date": price_data[-1]["trade_date"],
                "volume": latest_volume
            }
        elif latest_volume < avg_volume * 0.7:
            volume_signal = {
                "type": "缩量下跌",
                "level": "中",
                "date": price_data[-1]["trade_date"],
                "volume": latest_volume
            }
        
        # 4. 背离信号
        divergence_signal = None
        if len(closes) >= 10:
            recent_5 = closes[-5:]
            recent_10 = closes[-10:]
            avg5 = sum(recent_5) / 5
            avg10 = sum(recent_10) / 10
            
            if latest_close > avg10 and latest_close < avg5:
                divergence_signal = {
                    "type": "顶背离",
                    "level": "中",
                    "date": price_data[-1]["trade_date"]
                }
            elif latest_close < avg10 and latest_close > avg5:
                divergence_signal = {
                    "type": "底背离",
                    "level": "中",
                    "date": price_data[-1]["trade_date"]
                }
        
        signals.extend(ma_cross_signals)
        signals.extend(support_resistance)
        if volume_signal:
            signals.append(volume_signal)
        if divergence_signal:
            signals.append(divergence_signal)
        
        return {
            "ts_code": ts_code,
            "signals": signals[:10],  # 只返回最近10个信号
            "latest_price": {
                "close": latest_close,
                "change": float(latest_price.get("change", 0) or 0),
                "pct_chg": float(latest_price.get("pct_chg", 0) or 0)
            },
            "indicators": {
                "MA5": round(ma5, 2) if ma5 else None,
                "MA10": round(ma10, 2) if ma10 else None,
                "MA20": round(ma20, 2) if ma20 else None
            },
            "analysis": f"检测到{len(signals)}个技术信号，建议关注金叉死叉、支撑阻力位变化。"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"技术分析失败: {str(e)}")

@router_ai_analysis.get("/risk/{ts_code}")
async def get_risk_rating(ts_code: str):
    """风险评级"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取最新财务和行情数据
        cursor.execute("""
        SELECT f.*, d.close, d.pct_chg, d.vol
        FROM stock_finance_indicator f
        LEFT JOIN stock_daily d ON f.ts_code = d.ts_code AND d.trade_date = f.end_date
        WHERE f.ts_code = %s 
        ORDER BY f.end_date DESC 
        LIMIT 1
        """, (ts_code,))
        data = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not data:
            return {
                "ts_code": ts_code,
                "risk_level": "中等",
                "risk_score": 50,
                "factors": {}
            }
        
        risk_factors = {}
        total_risk = 0
        
        # 1. 财务风险（40%）
        debt_ratio = float(data.get("debt_ratio", 0) or 0)
        current_ratio = float(data.get("current_ratio", 0) or 0)
        
        financial_risk = 0
        if debt_ratio > 70:
            financial_risk += 20
            risk_factors["高负债率"] = {
                "level": "高",
                "value": f"{debt_ratio:.2f}%",
                "impact": "财务结构风险较高"
            }
        elif debt_ratio > 50:
            financial_risk += 10
        
        if current_ratio < 1:
            financial_risk += 15
            risk_factors["流动性不足"] = {
                "level": "高",
                "value": f"{current_ratio:.2f}",
                "impact": "短期偿债压力较大"
            }
        
        total_risk += financial_risk
        
        # 2. 市场风险（30%）
        pct_chg = float(data.get("pct_chg", 0) or 0)
        daily_volatility = abs(pct_chg)
        
        market_risk = 0
        if daily_volatility > 7:
            market_risk += 20
            risk_factors["高波动率"] = {
                "level": "高",
                "value": f"{daily_volatility:.2f}%",
                "impact": "股价波动较大，存在一定风险"
            }
        elif daily_volatility > 5:
            market_risk += 10
        elif daily_volatility > 3:
            market_risk += 5
        
        total_risk += market_risk
        
        # 3. 估值风险（30%）
        pb = float(data.get("pb", 0) or 0)
        
        valuation_risk = 0
        if pb > 50:
            valuation_risk += 20
            risk_factors["高估值风险"] = {
                "level": "高",
                "value": f"{pb:.2f}",
                "impact": "估值偏高，存在回调风险"
            }
        elif pb > 30:
            valuation_risk += 10
        elif pb < 5:
            valuation_risk += 5
            risk_factors["低估值"] = {
                "level": "中",
                "value": f"{pb:.2f}",
                "impact": "估值较低，可能存在投资机会"
            }
        
        total_risk += valuation_risk
        
        # 风险评分
        normalized_risk = (total_risk / 100) * 100
        
        if normalized_risk >= 70:
            risk_level = "高风险"
        elif normalized_risk >= 50:
                       risk_level = "中等风险"
        elif normalized_risk >= 30:
            risk_level = "低风险"
        else:
            risk_level = "低风险"
        
        return {
            "ts_code": ts_code,
            "risk_level": risk_level,
            "risk_score": round(normalized_risk, 2),
            "factors": risk_factors,
            "analysis": f"综合风险评分为{round(normalized_risk, 2)}分，风险等级为{risk_level}。建议{\'规避高波动股票\' if normalized_risk > 60 else \'可适当关注\'}。"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"风险评级失败: {str(e)}")

@router_ai_analysis.get("/valuation/{ts_code}")
async def get_valuation_analysis(ts_code: str):
    """估值分析和合理价格区间"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # 获取最新财务数据和行业平均估值
        cursor.execute("""
        SELECT f.*, d.close 
        FROM stock_finance_indicator f
        LEFT JOIN stock_daily d ON f.ts_code = d.ts_code AND d.trade_date = f.end_date
        WHERE f.ts_code = %s 
        ORDER BY f.end_date DESC 
        LIMIT 1
        """, (ts_code,))
        stock_data = cursor.fetchone()
        
        # 获取同行业平均PE/PB
        cursor.execute("""
        SELECT AVG(pe) as avg_pe, AVG(pb) as avg_pb
        FROM stock_finance_indicator f
        LEFT JOIN stock_basic b ON f.ts_code = b.ts_code
        WHERE b.industry = %s AND f.end_date > DATE_SUB(CURDATE(), INTERVAL 3 MONTH)
        """, (stock_data.get("industry", "")))
        industry_avg = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if not stock_data:
            return {
                "ts_code": ts_code,
                "fair_price_range": None,
                "analysis": "财务数据不足，无法进行估值分析"
            }
        
        current_pe = float(stock_data.get("pe", 0) or 0)
        current_pb = float(stock_data.get("pb", 0) or 0)
        current_close = float(stock_data.get("close", 0) or 0)
        
        # 相对估值分析
        relative_valuation = {}
        if industry_avg and industry_avg.get("avg_pe"):
            industry_pe = float(industry_avg.get("avg_pe", 0))
            industry_pb = float(industry_avg.get("avg_pb", 0))
            
            relative_valuation = {
                "industry": {
                    "avg_pe": round(industry_pe, 2),
                    "avg_pb": round(industry_pb, 2)
                },
                "relative_pe": round((current_pe - industry_pe) / industry_pe * 100, 2),
                "relative_pb": round((current_pb - industry_pb) / industry_pb * 100, 2)
            }
        
        # 合理价格区间计算（简化版）
        valuation_ratio = 2.0  # PE的合理倍数
        
        if current_pe > 0:
            eps = current_close / current_pe  # 估算每股收益
            fair_price_low = eps * valuation_ratio * 0.8
            fair_price_high = eps * valuation_ratio * 1.2
            fair_price_center = eps * valuation_ratio
        else:
            # 使用历史价格估算
            fair_price_center = current_close
' > ai_analysis_enhanced.py
