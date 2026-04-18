"""
MiniRock AI分析模块
集成Kimi API进行智能分析
"""

import json
import urllib.request
import urllib.error
from datetime import datetime
from database import save_ai_report

# MiniRock 家族股票 API 地址
MINIROCK_API_BASE = "http://127.0.0.1:8000"


def call_minirock_tiered(symbol: str, name: str = "", current_price: float = 0.0,
                          avg_cost: float = 0.0, quantity: int = 0,
                          profit_percent: float = 0.0, user_level: str = "vip") -> dict:
    """
    调用 MiniRock 分层分析 API（复用 familystock 的 v2.1 算法）
    同步版本，使用标准库 urllib
    """
    url = f"{MINIROCK_API_BASE}/api/minirock/analyze-tiered"
    payload = {
        "symbol": symbol,
        "name": name,
        "current_price": current_price,
        "avg_cost": avg_cost,
        "quantity": quantity,
        "profit_percent": profit_percent,
        "user_level": user_level  # vip 以上才有资金面+估值面
    }
    try:
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except urllib.error.URLError as e:
        return {"error": f"连接失败: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def format_minirock_for_portfolio(minirock_result: dict, holding: dict) -> str:
    """将 MiniRock 分层分析结果格式化为持仓分析文本"""
    parts = []
    summary = minirock_result.get("summary", {})
    technical = minirock_result.get("technical", {})
    fund = minirock_result.get("fund", {})
    valuation = minirock_result.get("valuation", {})
    position = minirock_result.get("position", {})
    scenario = minirock_result.get("scenario", {})

    score = summary.get("overall_score", 0)
    rating = summary.get("rating", "N/A")
    action = summary.get("action", "持有")
    conf = summary.get("confidence", 0)

    parts.append(f"**综合评分**: {score}/100 | 评级: {rating} | 建议: {action} | 置信度: {conf}%")
    parts.append(f"**当前价**: ¥{summary.get('current_price', 0):.2f} ({summary.get('change_percent', 0):+.2f}%)")

    # 技术面
    ma = technical.get("ma", {})
    if isinstance(ma, dict) and ma.get("status"):
        parts.append(f"**均线系统**: {ma.get('status', '-')} (MA{ma.get('period', '')} {ma.get('price', 'N/A')})")

    # 资金面
    if fund.get("main_force_status") and fund.get("main_force_status") != "数据采集中":
        main_force = fund.get("main_force_status", "-")
        fund_net = fund.get("fund_flow_net", "-")
        parts.append(f"**资金面**: 主向{'净流入' if '净流入' in str(main_force) else '净流出' if '净流出' in str(main_force) else main_force} | 净额: {fund_net}万")

    # 估值
    dcf_val = valuation.get("dcf_value", 0)
    premium = valuation.get("premium_discount", 0)
    if dcf_val and dcf_val > 0:
        parts.append(f"**估值**: DCF ¥{dcf_val:.2f} | 现价{dcf_val:.1f}={premium:+.1f}%")

    # 持仓建议
    if isinstance(position, dict) and position.get("position_advice"):
        parts.append(f"**持仓建议**: {position.get('position_advice')} | 止损: {position.get('stop_loss', '-')} | 止盈: {position.get('take_profit', '-')}")
        if position.get("analysis"):
            parts.append(f"   {position.get('analysis')}")

    # 情景推演
    if scenario and isinstance(scenario, dict):
        bullish = scenario.get("bullish_scenario", {})
        if bullish:
            parts.append(f"**乐观情景**: {bullish.get('target_price', '-')} ({bullish.get('probability', '-')})")
        bearish = scenario.get("bearish_scenario", {})
        if bearish:
            parts.append(f"**悲观情景**: {bearish.get('target_price', '-')} ({bearish.get('probability', '-')})")

    return " | ".join(parts) if parts else ""
def analyze_portfolio(holdings, news_list=None):
    """
    分析投资组合
    返回：风险等级、评分、建议
    """
    if not holdings:
        return {
            'score': 0,
            'risk_level': 'unknown',
            'recommendation': '暂无持仓',
            'analysis': '您还没有添加任何持仓。'
        }
    
    # 计算基础指标
    total_value = sum(h.get('market_value', 0) for h in holdings)
    avg_ai_score = sum(h.get('ai_score', 50) for h in holdings) / len(holdings)
    
    # 风险分析
    risk_factors = []
    opportunities = []
    
    for h in holdings:
        profit_pct = h.get('profit_pct', 0)
        ai_score = h.get('ai_score', 50)
        
        if profit_pct < -10:
            risk_factors.append(f"{h['name']}({h['symbol']})亏损超10%，建议关注")
        elif profit_pct > 20:
            opportunities.append(f"{h['name']}({h['symbol']})盈利超20%，可考虑部分止盈")
        
        if ai_score < 40:
            risk_factors.append(f"{h['name']}({h['symbol']})AI评分较低({ai_score})，技术面偏弱")
    
    # 计算综合评分
    score = int(avg_ai_score)
    if len(risk_factors) > len(opportunities):
        score -= 10
    elif len(opportunities) > len(risk_factors):
        score += 5
    
    score = max(0, min(100, score))
    
    # 确定风险等级
    if score >= 70:
        risk_level = 'low'
        risk_text = '低风险'
        recommendation = '积极'
    elif score >= 50:
        risk_level = 'medium'
        risk_text = '中等风险'
        recommendation = '观望'
    else:
        risk_level = 'high'
        risk_text = '高风险'
        recommendation = '谨慎'
    
    # 生成分析报告
    analysis_parts = []
    analysis_parts.append(f"## 投资组合分析报告")
    analysis_parts.append(f"")
    analysis_parts.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    analysis_parts.append(f"**持仓数量**: {len(holdings)}只")
    analysis_parts.append(f"**总资产**: ¥{total_value:,.2f}")
    analysis_parts.append(f"**综合评分**: {score}/100")
    analysis_parts.append(f"**风险等级**: {risk_text}")
    analysis_parts.append(f"**操作建议**: {recommendation}")
    analysis_parts.append(f"")
    
    if risk_factors:
        analysis_parts.append(f"### ⚠️ 风险提示")
        for risk in risk_factors:
            analysis_parts.append(f"- {risk}")
        analysis_parts.append(f"")
    
    if opportunities:
        analysis_parts.append(f"### ✅ 机会提醒")
        for opp in opportunities:
            analysis_parts.append(f"- {opp}")
        analysis_parts.append(f"")
    
    # 个股分析
    analysis_parts.append(f"### 📊 持仓明细")
    for h in holdings:
        emoji = '🟢' if h.get('profit_pct', 0) > 0 else '🔴'
        analysis_parts.append(f"{emoji} **{h['name']}({h['symbol']})**: 持仓{h['quantity']}股, 成本¥{h['avg_cost']:.2f}, 现价¥{h['current_price']:.2f}, 盈亏{h.get('profit_pct', 0):+.2f}%")
    
    analysis_text = '\n'.join(analysis_parts)
    
    return {
        'score': score,
        'risk_level': risk_level,
        'recommendation': recommendation,
        'analysis': analysis_text,
        'risk_factors': risk_factors,
        'opportunities': opportunities
    }


def analyze_single_stock(symbol, name, stock_data):
    """分析单只股票"""
    close = stock_data.get('close', 0)
    pct_chg = stock_data.get('pct_chg', 0)
    ai_score = stock_data.get('ai_score', 50)
    
    # 技术分析
    tech_signals = []
    if pct_chg > 5:
        tech_signals.append("强势上涨，注意追高风险")
    elif pct_chg > 2:
        tech_signals.append("温和上涨，趋势良好")
    elif pct_chg < -5:
        tech_signals.append("大幅下跌，建议观望")
    elif pct_chg < -2:
        tech_signals.append("小幅回调，关注支撑")
    
    # AI评分解读
    if ai_score >= 70:
        score_comment = "AI评分优秀，技术面强劲"
    elif ai_score >= 50:
        score_comment = "AI评分中等，表现平稳"
    else:
        score_comment = "AI评分偏低，需谨慎对待"
    
    analysis = f"""## {name}({symbol}) 分析报告

**当前价格**: ¥{close:.2f}  
**今日涨跌**: {pct_chg:+.2f}%  
**AI评分**: {ai_score}/100 - {score_comment}

### 技术面分析
{chr(10).join(['- ' + s for s in tech_signals]) if tech_signals else '- 走势平稳，无明显信号'}

### 操作建议
基于当前技术面，建议{('关注' if ai_score >= 60 else '观望' if ai_score >= 40 else '谨慎')}对待该股票。
"""
    
    return {
        'symbol': symbol,
        'name': name,
        'score': ai_score,
        'recommendation': '关注' if ai_score >= 60 else '观望' if ai_score >= 40 else '谨慎',
        'analysis': analysis
    }


def detect_black_swan(news_list):
    """检测黑天鹅事件"""
    high_risk_keywords = ['战争', '冲突', '制裁', '崩盘', '危机', '暴跌', '黑天鹅']
    
    alerts = []
    for news in news_list:
        title = news.get('title', '')
        for keyword in high_risk_keywords:
            if keyword in title:
                alerts.append({
                    'type': 'black_swan',
                    'level': 'high',
                    'source': news.get('source'),
                    'title': title,
                    'detected_at': datetime.now().isoformat()
                })
                break
    
    return alerts


def generate_daily_report(user_id, holdings, news_list):
    """生成每日报告并保存"""
    # 组合分析
    portfolio_analysis = analyze_portfolio(holdings, news_list)
    
    # 黑天鹅检测
    black_swans = detect_black_swan(news_list) if news_list else []
    
    # 保存报告
    report_id = save_ai_report(
        user_id=user_id,
        report_type='daily',
        content=portfolio_analysis['analysis'],
        risk_level=portfolio_analysis['risk_level'],
        score=portfolio_analysis['score']
    )
    
    return {
        'report_id': report_id,
        'portfolio': portfolio_analysis,
        'alerts': black_swans
    }


# ==================== API路由 ====================

from flask import Blueprint, jsonify
from database import get_user_holdings, get_recent_news

ai_bp = Blueprint('ai', __name__, url_prefix='/api/v3/ai')


def login_required(f):
    """登录验证装饰器"""
    def decorated(*args, **kwargs):
        from flask import g, request
        from auth import verify_token
        
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'success': False, 'error': '缺少Token'}), 401
        
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'success': False, 'error': 'Token无效'}), 401
        
        g.user_id = user_id
        return f(*args, **kwargs)
    
    decorated.__name__ = f.__name__
    return decorated


@ai_bp.route('/analyze/portfolio', methods=['POST'])
@login_required
def analyze_portfolio_api():
    """分析投资组合API - 调用 MiniRock v2.1 分层分析"""
    from flask import g

    holdings = get_user_holdings(g.user_id)
    news = get_recent_news(10)

    # 对每只持仓调用 MiniRock v2.1 分层分析（同步调用）
    minirock_results = []
    for h in holdings:
        mr = call_minirock_tiered(
            symbol=h['symbol'],
            name=h.get('name', ''),
            current_price=h.get('current_price', 0),
            avg_cost=h.get('avg_cost', 0),
            quantity=h.get('quantity', 0),
            profit_percent=h.get('profit_pct', 0),
            user_level="svip"  # SVIP 获取完整分析
        )
        minirock_results.append(mr)
    else:
        minirock_results = []

    # 组合概览
    total_value = sum(h.get('market_value', 0) for h in holdings)
    avg_score = 0
    if minirock_results:
        scores = [r.get("summary", {}).get("overall_score", 0) for r in minirock_results if r and "error" not in r]
        avg_score = sum(scores) / len(scores) if scores else 0

    # 生成报告
    analysis_parts = []
    analysis_parts.append(f"## 投资组合分析报告 (MiniRock v2.1)")
    analysis_parts.append(f"")
    analysis_parts.append(f"**分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    analysis_parts.append(f"**持仓数量**: {len(holdings)}只")
    analysis_parts.append(f"**总资产**: ¥{total_value:,.2f}")
    analysis_parts.append(f"**MiniRock综合评分**: {avg_score:.0f}/100")
    analysis_parts.append(f"")

    # 个股分析（逐只展示 MiniRock 详细信息）
    if holdings and minirock_results:
        analysis_parts.append(f"### 📊 个股分析")
        for i, (h, mr) in enumerate(zip(holdings, minirock_results)):
            emoji = '🟢' if h.get('profit_pct', 0) > 0 else '🔴'
            analysis_parts.append(f"")
            analysis_parts.append(f"#### {emoji} {h['name']}({h['symbol']})")
            analysis_parts.append(f"持仓: {h.get('quantity', 0)}股 | 成本¥{h.get('avg_cost', 0):.2f} | 现价¥{h.get('current_price', 0):.2f} | 盈亏{h.get('profit_pct', 0):+.2f}%")

            if mr and "error" not in mr:
                mr_text = format_minirock_for_portfolio(mr, h)
                if mr_text:
                    analysis_parts.append(mr_text)
                else:
                    analysis_parts.append(f"综合评分: {mr.get('summary', {}).get('overall_score', 'N/A')}/100 | 建议: {mr.get('summary', {}).get('action', '持有')}")
            else:
                err = mr.get("error", "未知错误") if mr else "无返回"
                analysis_parts.append(f"⚠️ MiniRock分析失败: {err} (降级使用基础分析)")
                # 降级：简单分析
                profit_pct = h.get('profit_pct', 0)
                ai_score = h.get('ai_score', 50)
                if profit_pct < -10:
                    analysis_parts.append(f"风险: 亏损超10%，建议关注支撑位")
                elif profit_pct > 20:
                    analysis_parts.append(f"机会: 盈利超20%，可考虑部分止盈")
                else:
                    analysis_parts.append(f"评分: {ai_score}/100，建议继续持有")

    # 黑天鹅检测
    black_swans = detect_black_swan(news) if news else []
    if black_swans:
        analysis_parts.append(f"")
        analysis_parts.append(f"### 🚨 黑天鹅预警")
        for alert in black_swans:
            analysis_parts.append(f"- [{alert['source']}] {alert['title']}")

    analysis_text = '\n'.join(analysis_parts)

    # 风险等级
    if avg_score >= 70:
        risk_level = 'low'
    elif avg_score >= 50:
        risk_level = 'medium'
    else:
        risk_level = 'high'

    # 保存报告
    save_ai_report(
        user_id=g.user_id,
        report_type='portfolio',
        content=analysis_text,
        risk_level=risk_level,
        score=avg_score
    )

    return jsonify({
        'success': True,
        'data': {
            'score': avg_score,
            'risk_level': risk_level,
            'holdings_count': len(holdings),
            'total_value': total_value,
            'analysis': analysis_text,
            'minirock_results': minirock_results,
            'black_swans': black_swans
        }
    })


@ai_bp.route('/analyze/stock/<symbol>', methods=['GET'])
def analyze_stock_api(symbol):
    """分析单只股票API"""
    from stock_cache_service import get_stock_with_cache
    
    stock_data = get_stock_with_cache(symbol)
    if not stock_data:
        return jsonify({'success': False, 'error': '股票数据不存在'}), 404
    
    result = analyze_single_stock(
        symbol=symbol,
        name=stock_data.get('name', symbol),
        stock_data=stock_data
    )
    
    return jsonify({
        'success': True,
        'data': result
    })


@ai_bp.route('/reports', methods=['GET'])
@login_required
def get_reports_api():
    """获取用户报告历史"""
    from flask import g, request
    from database import get_user_reports
    
    limit = request.args.get('limit', 10, type=int)
    reports = get_user_reports(g.user_id, limit)
    
    return jsonify({
        'success': True,
        'reports': reports
    })
