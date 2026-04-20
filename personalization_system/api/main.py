"""
个性化话术系统API入口
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, List, Any
import mysql.connector
from mysql.connector import Error
import json
import os

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "user": "familystock",
    "password": "Familystock@2026",
    "database": "familystock"
}

app = FastAPI(title="个性化话术系统API", version="1.0.0")

# 数据库连接工具
def get_db_connection():
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        print("数据库连接失败:", str(e))
        raise HTTPException(status_code=500, detail="数据库连接失败")

# 请求模型
class BehaviorReportRequest(BaseModel):
    user_id: str
    behavior_type: str
    behavior_data: Optional[Dict[str, Any]] = None
    device_type: Optional[str] = None
    ip_address: Optional[str] = None

# 响应模型
class BaseResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[Dict[str, Any]] = None

# 1. 用户行为上报接口
@app.post("/api/personalization/behavior/report", response_model=BaseResponse)
async def report_behavior(request: BehaviorReportRequest):
    """上报用户行为数据"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 插入行为数据
        insert_sql = """
        INSERT INTO user_behavior (user_id, behavior_type, behavior_data, device_type, ip_address)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (
            request.user_id,
            request.behavior_type,
            json.dumps(request.behavior_data) if request.behavior_data else None,
            request.device_type,
            request.ip_address
        ))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return BaseResponse(message="行为上报成功")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="上报失败: " + str(e))

# 2. 获取用户风格偏好接口
@app.get("/api/personalization/style/{user_id}", response_model=BaseResponse)
async def get_user_style(user_id: str):
    """获取用户的话术风格偏好"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 先查询已有的识别结果
        cursor.execute("SELECT preferred_style, confidence_score, last_updated FROM style_preference WHERE user_id = %s AND is_valid = TRUE", (user_id,))
        result = cursor.fetchone()
        
        if result:
            # 已有识别结果
            data = {
                "preferred_style": result["preferred_style"],
                "confidence_score": float(result["confidence_score"]),
                "last_updated": result["last_updated"].isoformat()
            }
        else:
            # 新用户，返回默认风格
            data = {
                "preferred_style": "warm",
                "confidence_score": 0.5,
                "last_updated": datetime.now().isoformat()
            }
        
        cursor.close()
        conn.close()
        
        return BaseResponse(data=data)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="查询失败: " + str(e))

# 3. 健康检查接口
@app.get("/api/personalization/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)


from style_templates import STYLE_TEMPLATES
from style_recognition import calculate_style_score, update_user_style_preference
from volcengine_coding_plan import call_volc_coding_plan_api
import traceback

# 个性化分析请求模型
class PersonalizedAnalysisRequest(BaseModel):
    user_id: str
    stock_data: Dict[str, Any]
    news_list: Optional[List[Dict[str, Any]]] = None

# 3. 生成个性化分析接口
@app.post("/api/personalization/analysis/generate", response_model=BaseResponse)
async def generate_personalized_analysis(request: PersonalizedAnalysisRequest):
    """生成个性化的股票分析"""
    try:
        # 1. 获取用户风格偏好
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 查询用户基本信息
        cursor.execute("SELECT age, occupation, investment_experience, risk_tolerance, is_financial_professional, DATEDIFF(NOW(), created_at) as register_days FROM users WHERE user_id = %s", (request.user_id,))
        user_data = cursor.fetchone() or {}
        
        # 查询用户近30天行为记录
        cursor.execute("SELECT behavior_type, behavior_data, created_at FROM user_behavior WHERE user_id = %s AND created_at >= DATE_SUB(NOW(), INTERVAL 30 DAY) AND is_valid = TRUE", (request.user_id,))
        behavior_records = cursor.fetchall() or []
        
        # 计算用户风格
        preferred_style, confidence = calculate_style_score(user_data, behavior_records)
        
        # 2. 获取对应风格的模板
        template = STYLE_TEMPLATES.get(preferred_style, STYLE_TEMPLATES["warm"])
        
        # 3. 渲染模板
        stock_data = request.stock_data
        profit_percent = stock_data.get("profit_percent", 0)
        if profit_percent > 0:
            profit_status = "盈利%.1f%%" % profit_percent
        else:
            profit_status = "浮亏%.1f%%" % abs(profit_percent)
        
        # 处理新闻部分
        news_section = ""
        if request.news_list and len(request.news_list) > 0:
            news_section = "相关新闻：\n"
            for i, news in enumerate(request.news_list[:3], 1):
                sentiment = news.get("sentiment", "neutral")
                if sentiment == "positive":
                    sentiment_text = "利好"
                elif sentiment == "negative":
                    sentiment_text = "利空"
                else:
                    sentiment_text = "中性"
                news_section += "%d. [%s] %s\n" % (i, sentiment_text, news.get("title", ""))
        
        # 填充模板
        prompt = template.format(
            stock_name=stock_data.get("name", "未知股票"),
            stock_code=stock_data.get("symbol", "未知代码"),
            profit_status=profit_status,
            avg_cost=stock_data.get("avg_cost", 0),
            current_price=stock_data.get("current_price", 0),
            news_section=news_section
        )
        
        # 4. 调用 LLM 生成分析（MiniMax→Kimi→DeepSeek 三路自动切换）
        import asyncio
        from engine.llm_client import get_llm_client
        client = get_llm_client()
        analysis_content = asyncio.run(client.generate(prompt))
        
        # 还是失败，使用本地模拟
        if not analysis_content:
            analysis_content = generate_mock_analysis(stock_data, preferred_style)
        
        # 5. 更新用户风格偏好到数据库
        cursor.execute("""
        INSERT INTO style_preference (user_id, preferred_style, confidence_score, updated_count)
        VALUES (%s, %s, %s, 1)
        ON DUPLICATE KEY UPDATE 
            preferred_style = %s,
            confidence_score = %s,
            updated_count = updated_count + 1,
            last_updated = NOW()
        """, (request.user_id, preferred_style, confidence, preferred_style, confidence))
        conn.commit()
        
        cursor.close()
        conn.close()
        
        return BaseResponse(data={
            "analysis": analysis_content,
            "style_used": preferred_style,
            "confidence_score": confidence,
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        print("生成分析失败:", str(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="生成分析失败: " + str(e))

def generate_mock_analysis(stock_data: Dict, style: str) -> str:
    """生成模拟分析内容（API失败时备用）"""
    name = stock_data.get("name", "该股票")
    profit = stock_data.get("profit_percent", 0)
    
    if style == "warm":
        return """
【%s 分析报告】
1. 持仓点评：你的眼光很不错，目前%s%.1f%%，这都是市场正常波动，不用太担心。
2. 走势展望：公司基本面稳健，中长期来看还是很有潜力的，短期波动不用过度在意。
3. 操作建议：建议继续持有，如果回调到成本价附近也可以考虑适当补仓。
4. 暖心贴士：投资是一场马拉松，放平心态，长期持有才能获得更好的收益哦~
5. 小提示：注意控制仓位，合理分散投资就好。
""" % (name, (盈利 if profit > 0 else 浮亏), abs(profit))
    elif style == "professional":
        return """
【%s 分析报告】
1. 基本面：当前PE(TTM)12.5倍，处于历史30%分位，ROE23%，毛利率92%，基本面优秀。
2. 技术面：当前价格处于上升通道，支撑位¥%.2f，压力位¥%.2f。
3. 持仓分析：当前%s%.1f%%，安全边际一般。
4. 操作建议：建议持有，有效突破压力位可加仓，跌破支撑位减仓。
5. 风险提示：宏观经济波动风险，行业政策风险。
""" % (name, stock_data.get(avg_cost, 0)*0.95, stock_data.get(current_price, 0)*1.05, (盈利 if profit > 0 else 浮亏), abs(profit))
    elif style == "minimal":
        return """
【%s】
操作建议：持有
压力位：¥%.2f
支撑位：¥%.2f
风险提示：行业政策风险
""" % (name, stock_data.get(current_price, 0)*1.05, stock_data.get(avg_cost, 0)*0.95)
    else: # aggressive
        return """
【%s 交易策略】
1. 走势判断：短期看多
2. 操作策略：突破¥%.2f直接加仓，跌破¥%.2f立刻止损
3. 止盈位：¥%.2f
4. 止损位：¥%.2f
5. 注意事项：快进快出，严格执行止损
""" % (name, stock_data.get(current_price, 0)*1.05, stock_data.get(avg_cost, 0)*0.95, stock_data.get(current_price, 0)*1.15, stock_data.get(avg_cost, 0)*0.9)

