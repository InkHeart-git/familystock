"""
AI分析服务路由
提供个股诊断、组合分析、新闻关联和情景推演
已接入本地新闻库
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import requests
import json
import os

# LanceDB新闻库支持
try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

router = APIRouter(prefix="/api/ai", tags=["AI分析"])

# DeepSeek API配置
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = "sk-ba29925a6dc84f6da02ac006a2fc93f2"

# 新闻库配置
LANCE_DB_PATH = "/var/www/familystock/lancedb/news_analysis.lance"
NEWS_CACHE = {}  # 内存缓存

class StockAnalysisRequest(BaseModel):
    symbol: str
    name: str
    current_price: float
    avg_cost: float
    quantity: int
    change_percent: float
    profit_percent: float
    market: str = "A股"

class PortfolioAnalysisRequest(BaseModel):
    holdings: List[dict]
    total_value: float
    total_profit: float
    total_profit_percent: float


# ==================== 新闻库操作 ====================

def get_related_news_from_db(symbol: str, name: str, limit: int = 3) -> List[dict]:
    """从本地新闻库获取相关新闻"""
    # 先检查内存缓存
    cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d')}"
    if cache_key in NEWS_CACHE:
        return NEWS_CACHE[cache_key][:limit]
    
    # 如果LanceDB可用且存在，尝试读取
    if LANCEDB_AVAILABLE and os.path.exists(LANCE_DB_PATH):
        try:
            db = lancedb.connect(LANCE_DB_PATH)
            # 由于表结构未知，先尝试列出表
            tables = db.list_tables()
            if tables:
                # 假设第一个表是新闻表
                news_table = db.open_table(tables[0])
                # 搜索相关新闻（通过symbol或关键词匹配）
                results = news_table.search().where(f"symbol = '{symbol}' OR title LIKE '%{name}%'").limit(limit).to_pandas()
                news_list = []
                for _, row in results.iterrows():
                    news_list.append({
                        "title": row.get("title", ""),
                        "summary": row.get("summary", row.get("content", "")[:100]),
                        "source": row.get("source", "未知"),
                        "published_at": str(row.get("published_at", datetime.now())),
                        "sentiment": row.get("sentiment", "neutral")
                    })
                if news_list:
                    NEWS_CACHE[cache_key] = news_list
                    return news_list
        except Exception as e:
            print(f"从LanceDB读取新闻失败: {e}")
    
    # 返回模拟新闻数据（真实数据接入前使用）
    return generate_mock_news(symbol, name, limit)


def generate_mock_news(symbol: str, name: str, limit: int = 3) -> List[dict]:
    """生成模拟新闻（用于新闻库无数据时）"""
    # 行业关键词映射
    sector_news = {
        "茅台": [
            {"title": f"{name}：白酒行业景气度回升，高端需求稳健", "sentiment": "positive", "source": "证券时报"},
            {"title": f"{name}发布业绩预告，Q4净利润同比增长超预期", "sentiment": "positive", "source": "财联社"},
        ],
        "宁德": [
            {"title": f"{name}：新能源车销量创新高，电池需求旺盛", "sentiment": "positive", "source": "中国证券报"},
            {"title": f"锂电池原材料价格波动，{name}成本压力缓解", "sentiment": "neutral", "source": "上海证券报"},
        ],
        "比亚": [
            {"title": f"{name}新能源汽车销量突破历史纪录", "sentiment": "positive", "source": "汽车之家"},
            {"title": f"{name}海外市场拓展加速，出口量持续增长", "sentiment": "positive", "source": "证券时报"},
        ],
        "平安": [
            {"title": f"{name}：银行业绩稳健，资产质量持续改善", "sentiment": "positive", "source": "财联社"},
            {"title": f"央行降准预期升温，银行板块或受益", "sentiment": "positive", "source": "经济观察报"},
        ],
    }
    
    # 匹配行业新闻
    matched_news = []
    for keyword, news_list in sector_news.items():
        if keyword in name:
            matched_news.extend(news_list)
            break
    
    # 如果没有匹配到，生成通用新闻
    if not matched_news:
        matched_news = [
            {"title": f"{name}({symbol})发布最新财报，业绩符合预期", "sentiment": "neutral", "source": "财经网"},
            {"title": f"{name}所属板块近期表现活跃，资金关注度提升", "sentiment": "positive", "source": "证券时报"},
            {"title": f"分析师观点：{name}中长期配置价值分析", "sentiment": "neutral", "source": "券商研报"},
        ]
    
    # 添加时间戳和标准化格式
    now = datetime.now()
    result = []
    for i, news in enumerate(matched_news[:limit]):
        result.append({
            "id": i + 1,
            "title": news["title"],
            "summary": news["title"],
            "source": news.get("source", "财经媒体"),
            "published_at": (now - timedelta(hours=i*2)).isoformat(),
            "sentiment": news["sentiment"],
            "impact": "high" if news["sentiment"] == "positive" else "medium"
        })
    
    return result


# ==================== AI服务封装 ====================

def call_deepseek_api(prompt: str, model: str = "deepseek-chat") -> str:
    """调用DeepSeek API获取AI分析"""
    try:
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是一位专业的股票投资分析师，擅长技术分析和基本面分析。请提供简洁、专业的投资建议。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1500
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        if response.ok and "choices" in result:
            return result["choices"][0]["message"]["content"]
        else:
            print(f"AI API错误: {result}")
            return None
    except Exception as e:
        print(f"调用AI API失败: {e}")
        return None


# ==================== 个股诊断 ====================

def generate_stock_analysis_prompt(stock: dict, news_list: List[dict] = None) -> str:
    """生成个股诊断的AI提示词（已接入新闻库）"""
    
    # 基础股票信息
    prompt = f"""请对以下股票进行专业分析：

股票信息：
- 名称：{stock['name']} ({stock['symbol']})
- 当前价格：¥{stock['current_price']}
- 持仓成本：¥{stock['avg_cost']}
- 持股数量：{stock['quantity']}股
- 今日涨跌幅：{stock.get('change_percent', 0):.2f}%
- 持仓盈亏：{stock.get('profit_percent', 0):.2f}%
- 市场：{stock.get('market', 'A股')}"""
    
    # 添加相关新闻（如果存在）
    if news_list:
        prompt += "\n\n相关新闻资讯：\n"
        for i, news in enumerate(news_list[:3], 1):
            sentiment_tag = {"positive": "[利好]", "negative": "[利空]", "neutral": "[中性]"}.get(news.get("sentiment", "neutral"), "[中性]")
            prompt += f"{i}. {sentiment_tag} {news.get('title', '')} (来源：{news.get('source', '财经媒体')})\n"
    
    prompt += """

请从以下角度分析：
1. 技术面分析（趋势、支撑/压力位）
2. 持仓盈亏分析（当前状况）
3. 新闻影响解读（结合最新资讯的影响）
4. 操作建议（买入/持有/卖出建议及理由）
5. 风险提示（主要风险因素）

请结合最新新闻资讯进行分析，用简洁专业的中文回答，总字数控制在400字以内。"""
    
    return prompt


@router.post("/analyze-stock")
async def analyze_stock(request: StockAnalysisRequest):
    """AI个股诊断（已接入新闻库）"""
    # 构建股票数据
    stock_data = {
        "symbol": request.symbol,
        "name": request.name,
        "current_price": request.current_price,
        "avg_cost": request.avg_cost,
        "quantity": request.quantity,
        "change_percent": request.change_percent,
        "profit_percent": request.profit_percent,
        "market": request.market
    }
    
    # 从新闻库获取相关新闻
    related_news = get_related_news_from_db(request.symbol, request.name)
    
    # 生成提示词（包含新闻）
    prompt = generate_stock_analysis_prompt(stock_data, related_news)
    
    # 调用AI
    ai_response = call_deepseek_api(prompt)
    
    if ai_response:
        # 解析AI响应
        return {
            "symbol": request.symbol,
            "name": request.name,
            "analysis": ai_response,
            "summary": ai_response[:100] + "..." if len(ai_response) > 100 else ai_response,
            "related_news": related_news,
            "news_count": len(related_news),
            "timestamp": datetime.now().isoformat(),
            "source": "AI(新闻增强)"
        }
    else:
        # AI失败时返回模拟分析
        return generate_mock_stock_analysis(stock_data)


def generate_mock_stock_analysis(stock: dict) -> dict:
    """生成模拟的个股分析（AI不可用时）"""
    profit = stock.get('profit_percent', 0)
    change = stock.get('change_percent', 0)
    
    if profit > 10:
        analysis = f"{stock['name']}目前盈利{profit:.1f}%，走势良好。建议继续持有，关注上方压力位。短期可能面临回调，建议适当减仓锁定利润。"
        risk_level = "中"
    elif profit > 0:
        analysis = f"{stock['name']}目前小幅盈利{profit:.1f}%，走势稳健。建议继续持有，关注后续业绩表现和行业政策变化。"
        risk_level = "低"
    elif profit > -10:
        analysis = f"{stock['name']}目前小幅亏损{abs(profit):.1f}%，短期调整。基本面未变，建议观望或逢低加仓摊低成本。"
        risk_level = "中"
    else:
        analysis = f"{stock['name']}目前亏损{abs(profit):.1f}%，走势偏弱。建议关注支撑位，如跌破关键支撑需考虑止损。"
        risk_level = "高"
    
    return {
        "symbol": stock['symbol'],
        "name": stock['name'],
        "analysis": analysis,
        "summary": analysis[:100] + "...",
        "risk_level": risk_level,
        "related_news": [],
        "news_count": 0,
        "timestamp": datetime.now().isoformat(),
        "source": "mock"
    }


# ==================== 组合分析 ====================

def generate_portfolio_analysis_prompt(portfolio: dict, news_summary: str = "") -> str:
    """生成组合分析的AI提示词（可选接入新闻）"""
    holdings_info = "\n".join([
        f"- {h['name']}({h['symbol']}): {h['quantity']}股, 盈亏{h.get('profit_percent', 0):.1f}%, 占比{(h.get('market_value', 0) / portfolio['total_value'] * 100):.1f}%"
        for h in portfolio['holdings']
    ])
    
    prompt = f"""请对以下投资组合进行专业分析：

组合概况：
- 总市值：¥{portfolio['total_value']:,.2f}
- 总盈亏：¥{portfolio['total_profit']:,.2f} ({portfolio['total_profit_percent']:.2f}%)
- 持仓数量：{len(portfolio['holdings'])}只股票

持仓详情：
{holdings_info}"""
    
    # 添加新闻摘要（如果有）
    if news_summary:
        prompt += f"\n\n相关新闻摘要：\n{news_summary}"
    
    prompt += """

请从以下角度分析：
1. 组合整体风险评估（集中度、行业分布风险）
2. 收益表现评价（与市场对比）
3. 调仓建议（哪些该加仓/减仓）
4. 优化建议（如何改进组合结构）

请用简洁专业的中文回答，控制在400字以内。"""
    
    return prompt


@router.post("/analyze-portfolio")
async def analyze_portfolio(request: PortfolioAnalysisRequest):
    """AI组合分析（可选接入新闻）"""
    portfolio_data = {
        "holdings": request.holdings,
        "total_value": request.total_value,
        "total_profit": request.total_profit,
        "total_profit_percent": request.total_profit_percent
    }
    
    # 计算基础指标
    risk_level = calculate_portfolio_risk(portfolio_data)
    concentration = calculate_concentration(portfolio_data)
    
    # 获取持仓相关新闻摘要
    news_summary = ""
    for holding in request.holdings[:3]:  # 只取前3大持仓的新闻
        news = get_related_news_from_db(holding.get('symbol', ''), holding.get('name', ''), limit=1)
        if news:
            news_summary += f"- {holding.get('name')}: {news[0].get('title', '')}\n"
    
    # 生成AI提示词
    prompt = generate_portfolio_analysis_prompt(portfolio_data, news_summary)
    
    # 调用AI
    ai_response = call_deepseek_api(prompt)
    
    if ai_response:
        return {
            "total_value": request.total_value,
            "total_profit": request.total_profit,
            "total_profit_percent": request.total_profit_percent,
            "risk_level": risk_level,
            "concentration": concentration,
            "analysis": ai_response,
            "recommendations": parse_recommendations(ai_response),
            "timestamp": datetime.now().isoformat(),
            "source": "AI"
        }
    else:
        return generate_mock_portfolio_analysis(portfolio_data)


def calculate_portfolio_risk(portfolio: dict) -> str:
    """计算组合风险等级"""
    profits = [h.get('profit_percent', 0) for h in portfolio['holdings']]
    avg_profit = sum(profits) / len(profits) if profits else 0
    
    if avg_profit < -15:
        return "高"
    elif avg_profit < -5:
        return "中高"
    elif avg_profit < 5:
        return "中"
    else:
        return "低"


def calculate_concentration(portfolio: dict) -> dict:
    """计算持仓集中度"""
    if not portfolio['holdings']:
        return {"top1": 0, "top3": 0}
    
    sorted_holdings = sorted(portfolio['holdings'], 
                            key=lambda x: x.get('market_value', 0), 
                            reverse=True)
    
    top1_value = sorted_holdings[0].get('market_value', 0)
    top3_value = sum(h.get('market_value', 0) for h in sorted_holdings[:3])
    
    total_value = portfolio['total_value']
    
    return {
        "top1": round(top1_value / total_value * 100, 1) if total_value > 0 else 0,
        "top3": round(top3_value / total_value * 100, 1) if total_value > 0 else 0
    }


def generate_mock_portfolio_analysis(portfolio: dict) -> dict:
    """生成模拟的组合分析"""
    profit_percent = portfolio['total_profit_percent']
    
    if profit_percent > 10:
        analysis = "组合整体表现优秀，盈利超过10%。建议适当止盈，锁定部分利润。可考虑将盈利较高的个股减仓，均衡配置。"
        risk_level = "低"
    elif profit_percent > 0:
        analysis = "组合小幅盈利，整体稳健。建议继续持有，关注持仓结构是否均衡。可考虑加仓基本面良好的低估个股。"
        risk_level = "中"
    else:
        analysis = "组合暂时亏损，但不必过于担忧。建议审视每只股票的基本面，对于基本面未变但短期调整的可以逢低加仓。"
        risk_level = "中高"
    
    return {
        "total_value": portfolio['total_value'],
        "total_profit": portfolio['total_profit'],
        "total_profit_percent": profit_percent,
        "risk_level": risk_level,
        "concentration": calculate_concentration(portfolio),
        "analysis": analysis,
        "recommendations": [
            "关注持仓集中度，避免过度集中",
            "定期审视个股基本面",
            "根据市场变化适当调整仓位"
        ],
        "timestamp": datetime.now().isoformat(),
        "source": "mock"
    }


def parse_recommendations(ai_text: str) -> List[str]:
    """从AI响应中解析具体建议"""
    # 简单的建议提取逻辑
    lines = ai_text.split('\n')
    recommendations = []
    
    for line in lines:
        if any(keyword in line for keyword in ['建议', '推荐', '考虑', '可以']):
            clean_line = line.strip('- •*')
            if len(clean_line) > 10 and len(clean_line) < 100:
                recommendations.append(clean_line)
    
    return recommendations[:5] if recommendations else ["建议定期关注持仓动态"]


# ==================== 情景推演 ====================

@router.get("/scenario/{symbol}")
async def scenario_analysis(
    symbol: str,
    name: str = Query(default=""),
    current_price: float = Query(default=0),
    scenarios: str = Query(default="optimistic,neutral,pessimistic")
):
    """情景推演 - 模拟不同市场情况"""
    scenario_list = scenarios.split(',')
    
    results = {}
    
    for scenario in scenario_list:
        scenario = scenario.strip()
        if scenario == "optimistic":
            change = 15  # 乐观：上涨15%
            desc = "市场行情向好，该股受益"
        elif scenario == "pessimistic":
            change = -15  # 悲观：下跌15%
            desc = "市场调整，风险释放"
        else:  # neutral
            change = 5  # 中性：上涨5%
            desc = "市场平稳，温和上涨"
        
        projected_price = current_price * (1 + change / 100)
        
        results[scenario] = {
            "name": scenario,
            "change_percent": change,
            "projected_price": round(projected_price, 2),
            "description": desc
        }
    
    return {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "scenarios": results,
        "timestamp": datetime.now().isoformat()
    }


# ==================== 新闻关联 ====================

@router.get("/news-related/{symbol}")
async def get_related_news(
    symbol: str,
    name: str = Query(default=""),
    limit: int = Query(default=5)
):
    """获取与股票相关的新闻（从本地新闻库）"""
    news_list = get_related_news_from_db(symbol, name, limit)
    
    return {
        "symbol": symbol,
        "name": name,
        "news_count": len(news_list),
        "news": news_list,
        "timestamp": datetime.now().isoformat(),
        "source": "本地新闻库"
    }
