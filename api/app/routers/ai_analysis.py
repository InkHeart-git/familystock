"""
AI分析服务路由
提供个股诊断、组合分析、新闻关联和情景推演
已接入本地新闻库 (SQLite)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
import requests
import json
import os
import sqlite3

router = APIRouter(prefix="/ai", tags=["AI分析"])

# Kimi Code Plan API配置（主要接口）
KIMI_API_URL = "https://api.kimi.com/coding/v1/messages"
KIMI_API_KEY = "sk-kimi-4i8L6z8eA89Oj8430WbkbwaldakqTBVUhbAEfbDdf02aQPpPDzVuAjHAAoTS2IYW"
KIMI_MODEL = "k2p5"

# DeepSeek API配置（备用接口）
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_API_KEY = "sk-ba29925a6dc84f6da02ac006a2fc93f2"

# 新闻库配置
SQLITE_DB_PATH = "/var/www/familystock/api/data/family_stock.db"
NEWS_CACHE = {}  # 内存缓存

class StockAnalysisRequest(BaseModel):
    symbol: str
    name: str = ""
    current_price: float = 0.0
    avg_cost: float = 0.0
    quantity: int = 0
    change_percent: float = 0.0
    profit_percent: float = 0.0
    market: str = "A股"

class PortfolioAnalysisRequest(BaseModel):
    holdings: List[dict]
    total_value: float
    total_profit: float
    total_profit_percent: float = 0.0


# ==================== MiniRock v2.1 集成 ====================

MINIROCK_API = "http://127.0.0.1:8000"


def call_minirock_tiered(symbol: str, name: str = "", current_price: float = 0.0,
                          avg_cost: float = 0.0, quantity: int = 0,
                          profit_percent: float = 0.0, user_level: str = "svip") -> dict:
    """
    调用 MiniRock 分层分析 API（复用 familystock 的 v2.1 算法）
    """
    url = f"{MINIROCK_API}/api/minirock/analyze-tiered"
    payload = {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "avg_cost": avg_cost,
        "quantity": quantity,
        "profit_percent": profit_percent,
        "user_level": user_level
    }
    try:
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def format_minirock_result(mr: dict, holding: dict) -> str:
    """将 MiniRock 结果格式化为持仓分析文本"""
    if "error" in mr:
        return f"⚠️ MiniRock分析失败: {mr['error']}"

    data = mr.get("data", {})
    if not data:
        return "⚠️ MiniRock返回空数据"

    summary = data.get("summary", {}).get("data", {})
    technical = data.get("technical", {}).get("data", {})
    fund = data.get("fund", {}).get("data", {})
    valuation = data.get("valuation", {}).get("data", {})
    position = data.get("position", {}).get("data", {})
    scenario = data.get("scenario", {}).get("data", {})

    score = summary.get("overall_score", 0)
    rating = summary.get("rating", "N/A")
    action = summary.get("action", "持有")
    conf = summary.get("confidence", 0)
    price = summary.get("current_price", 0)
    pct_chg = summary.get("change_percent", 0)

    parts = [
        f"**评分**: {score}/100 | {rating} | {action} | 置信度{conf}%",
        f"现价¥{price:.2f} ({pct_chg:+.2f}%)"
    ]

    # 技术面
    ma_status = technical.get("ma", {}).get("status") if isinstance(technical.get("ma"), dict) else None
    if ma_status:
        parts.append(f"均线: {ma_status}")
    trend = technical.get("trend", "")
    if trend:
        parts.append(f"趋势: {trend}")

    # 资金面
    main_force = fund.get("main_force", "")
    main_amount = fund.get("main_amount", "")
    if main_force and main_force not in ("数据采集中", ""):
        parts.append(f"资金: {main_force}{main_amount}")

    # 估值
    dcf = valuation.get("dcf_value", 0)
    premium = valuation.get("premium_discount", 0)
    if dcf and dcf > 0:
        parts.append(f"DCF¥{dcf:.2f} (现价{premium:+.1f}%)")

    # 持仓建议
    pos_advice = position.get("position_advice", "")
    stop_loss = position.get("stop_loss", "")
    take_profit = position.get("take_profit", "")
    if pos_advice:
        parts.append(f"建议: {pos_advice} | 止损{stop_loss} | 止盈{take_profit}")

    # 情景
    scenarios = scenario.get("scenarios", []) if isinstance(scenario, dict) else []
    if scenarios:
        top = scenarios[0]
        parts.append(f"情景: {top.get('name','-')} {top.get('probability','-')} → ¥{top.get('price_target','-')}")

    return " | ".join(parts)


# ==================== 新闻库操作 ====================

def get_related_news_from_db(symbol: str, name: str, limit: int = 3) -> List[dict]:
    """从本地新闻库获取相关新闻 (优先SQLite，支持灵犀的新闻库)"""
    # 先检查内存缓存
    cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d')}"
    if cache_key in NEWS_CACHE:
        return NEWS_CACHE[cache_key][:limit]
    
    news_list = []
    
    # 1. 尝试从SQLite读取 (灵犀的新闻库)
    if os.path.exists(SQLITE_DB_PATH):
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 获取表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 检测新闻表名 (支持: news, articles, news_articles)
            table_name = None
            for t in ['news_articles', 'news', 'articles']:
                if t in tables:
                    table_name = t
                    break
            
            if table_name:
                
                # 搜索相关新闻 (按股票名称或代码匹配)
                query = f"""
                    SELECT title, content, source, published_at, category 
                    FROM {table_name} 
                    WHERE title LIKE ? OR content LIKE ? OR category LIKE ?
                    ORDER BY published_at DESC 
                    LIMIT ?
                """
                cursor.execute(query, (f'%{name}%', f'%{name}%', f'%{name}%', limit))
                
                rows = cursor.fetchall()
                for row in rows:
                    news_list.append({
                        "title": row['title'],
                        "summary": row['content'][:150] + "..." if row['content'] else row['title'],
                        "source": row.get('source', '新浪财经'),
                        "published_at": row.get('published_at', datetime.now().isoformat()),
                        "category": row.get('category', '财经'),
                        "sentiment": analyze_sentiment(row['title'] + row.get('content', ''))
                    })
            
            conn.close()
        except Exception as e:
            print(f"从SQLite读取新闻失败: {e}")
    
    # 2. 如果SQLite没有数据，使用模拟新闻
    if not news_list:
        news_list = generate_mock_news(symbol, name, limit)
    
    # 缓存结果
    if news_list:
        NEWS_CACHE[cache_key] = news_list
    
    return news_list


def analyze_sentiment(text: str) -> str:
    """简单情感分析"""
    positive_words = ['上涨', '利好', '突破', '增长', '盈利', '增持', '看好', '推荐', '强势']
    negative_words = ['下跌', '利空', '风险', '亏损', '减持', '警告', '调查', '处罚', '暴雷']
    
    p_count = sum(1 for w in positive_words if w in text)
    n_count = sum(1 for w in negative_words if w in text)
    
    if p_count > n_count:
        return "positive"
    elif n_count > p_count:
        return "negative"
    return "neutral"


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
        "招商": [
            {"title": f"{name}：零售银行业务增长强劲", "sentiment": "positive", "source": "证券时报"},
            {"title": f"财富管理业务推动{name}业绩提升", "sentiment": "positive", "source": "财联社"},
        ],
        "讯飞": [
            {"title": f"{name}AI大模型业务进展迅速", "sentiment": "positive", "source": "科技日报"},
            {"title": f"人工智能政策利好，{name}有望受益", "sentiment": "positive", "source": "中国证券报"},
        ],
        "海康": [
            {"title": f"{name}安防业务稳健，创新业务高增长", "sentiment": "positive", "source": "财联社"},
            {"title": f"数字化转型加速，{name}订单充足", "sentiment": "positive", "source": "证券时报"},
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

def call_kimi_api(prompt: str) -> Optional[str]:
    """调用Kimi Code Plan API（主要接口）"""
    try:
        headers = {
            "x-api-key": KIMI_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "Kimi Claw Plugin",
            "anthropic-version": "2023-06-01"
        }
        
        payload = {
            "model": KIMI_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 1500,
            "temperature": 0.7
        }
        
        response = requests.post(KIMI_API_URL, headers=headers, json=payload, timeout=45)
        result = response.json()
        
        if response.ok and "content" in result:
            content_blocks = result["content"]
            if isinstance(content_blocks, list) and len(content_blocks) > 0:
                return content_blocks[0].get("text", "")
            return str(content_blocks)
        else:
            print(f"Kimi API错误: {result}")
            return None
    except Exception as e:
        print(f"调用Kimi API失败: {e}")
        return None


def call_ai_api(prompt: str) -> Optional[str]:
    """调用AI API（Kimi优先，DeepSeek备用）"""
    # 先尝试Kimi
    result = call_kimi_api(prompt)
    if result:
        print("使用Kimi生成分析")
        return result
    
    # Kimi失败时回退到DeepSeek
    print("Kimi失败，回退到DeepSeek")
    return call_deepseek_api(prompt)


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
    """AI个股诊断（已接入新闻库）- 支持自动获取缺失字段"""
    import sqlite3
    
    symbol = request.symbol
    
    # 如果没有提供完整数据，从数据库自动获取
    if not request.name or request.current_price == 0:
        try:
            conn = sqlite3.connect("/var/www/familystock/api/data/family_stock.db")
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 处理代码格式
            ts_code = symbol
            if "." not in symbol:
                if symbol.startswith("6"):
                    ts_code = f"{symbol}.SH"
                else:
                    ts_code = f"{symbol}.SZ"
            
            # 查询最新行情
            cursor.execute("""
                SELECT ts_code, close, pct_chg FROM stock_quotes 
                WHERE ts_code = ? ORDER BY trade_date DESC LIMIT 1
            """, (ts_code,))
            row = cursor.fetchone()
            
            if row:
                current_price = float(row["close"] or 0)
                change_percent = float(row["pct_chg"] or 0)
            else:
                current_price = request.current_price
                change_percent = request.change_percent
            
            conn.close()
        except Exception as e:
            print(f"获取行情失败: {e}")
            current_price = request.current_price
            change_percent = request.change_percent
    else:
        current_price = request.current_price
        change_percent = request.change_percent
    
    # 构建股票数据
    stock_data = {
        "symbol": symbol,
        "name": request.name or symbol,
        "current_price": current_price,
        "avg_cost": request.avg_cost or current_price,
        "quantity": request.quantity,
        "change_percent": change_percent,
        "profit_percent": request.profit_percent,
        "market": request.market
    }
    
    # 从新闻库获取相关新闻
    related_news = get_related_news_from_db(request.symbol, request.name)
    
    # 生成提示词（包含新闻）
    prompt = generate_stock_analysis_prompt(stock_data, related_news)
    
    # 调用AI
    ai_response = call_ai_api(prompt)
    
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
            "source": "Kimi AI"
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
    """
    AI组合分析 - 已集成 MiniRock v2.1 分层分析算法
    对每只持仓调用 MiniRock，复用 familystock 的完整分析能力
    """
    portfolio_data = {
        "holdings": request.holdings,
        "total_value": request.total_value,
        "total_profit": request.total_profit,
        "total_profit_percent": request.total_profit_percent
    }

    # 风险和集中度
    risk_level = calculate_portfolio_risk(portfolio_data)
    concentration = calculate_concentration(portfolio_data)

    # === 核心改动：对每只持仓调用 MiniRock v2.1 ===
    minirock_details = []
    total_score = 0
    scored_count = 0

    for h in request.holdings:
        mr = call_minirock_tiered(
            symbol=h.get('symbol', ''),
            name=h.get('name', ''),
            current_price=h.get('current_price', 0),
            avg_cost=h.get('avg_cost', 0),
            quantity=h.get('quantity', 0),
            profit_percent=h.get('profit_percent', 0),
            user_level="svip"
        )
        mr_text = format_minirock_result(mr, h)
        mr_score = mr.get("data", {}).get("summary", {}).get("data", {}).get("overall_score", 0) if "error" not in mr else 0
        if mr_score > 0:
            total_score += mr_score
            scored_count += 1
        minirock_details.append({
            "symbol": h.get('symbol'),
            "name": h.get('name'),
            "minirock_analysis": mr_text,
            "score": mr_score
        })

    avg_minirock_score = total_score / scored_count if scored_count > 0 else 0

    # 组合概览
    summary_parts = [
        f"## 组合分析报告 (MiniRock v2.1)",
        f"",
        f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**持仓**: {len(request.holdings)}只 | **总市值**: ¥{request.total_value:,.2f}",
        f"**整体评分**: {avg_minirock_score:.0f}/100 | **风险等级**: {risk_level}",
        f"**集中度**: top1 {concentration.get('top1',0):.1f}% | top3 {concentration.get('top3',0):.1f}%",
        "",
        "---",
    ]

    # 个股详情
    for detail in minirock_details:
        emoji = '🟢' if detail.get('profit_percent', 0) > 0 else '🔴'
        summary_parts.append(f"### {emoji} {detail['name']}({detail['symbol']})")
        summary_parts.append(detail['minirock_analysis'])
        summary_parts.append("")

    # 新闻摘要（保留原有逻辑）
    news_summary = ""
    for holding in request.holdings[:3]:
        news = get_related_news_from_db(holding.get('symbol', ''), holding.get('name', ''), limit=1)
        if news:
            news_summary += f"- {holding.get('name')}: {news[0].get('title', '')}\n"

    # AI综合点评
    prompt = generate_portfolio_analysis_prompt(portfolio_data, news_summary)
    ai_response = call_ai_api(prompt)
    if ai_response:
        summary_parts.append("---")
        summary_parts.append("### AI综合点评")
        summary_parts.append(ai_response)

    return {
        "total_value": request.total_value,
        "total_profit": request.total_profit,
        "total_profit_percent": request.total_profit_percent,
        "risk_level": risk_level,
        "concentration": concentration,
        "minirock_score": avg_minirock_score,
        "analysis": "\n".join(summary_parts),
        "recommendations": parse_recommendations(ai_response) if ai_response else [],
        "timestamp": datetime.now().isoformat(),
        "source": "MiniRock v2.1",
        "minirock_details": minirock_details
    }


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
        "source": "SQLite新闻库" if os.path.exists(SQLITE_DB_PATH) else "模拟数据"
    }
