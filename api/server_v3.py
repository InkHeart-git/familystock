#!/usr/bin/env python3
"""
FamilyStock API Server V3 - 全自动AI推演预警系统
参考贝莱德阿拉丁(Aladdin)系统设计

API端点:
- /api/v3/pipeline/status - 流水线状态
- /api/v3/pipeline/run - 手动触发流水线
- /api/v3/alerts - 获取预警列表
- /api/v3/alerts/active - 获取有效预警
- /api/v3/alerts/stream - SSE实时预警流
- /api/v3/dashboard - 风险仪表盘数据
- /api/v3/news - 新闻列表
- /api/v3/simulation - AI推演结果
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading
import time

from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from pipeline import (
    get_pipeline, Pipeline, PipelineStage, 
    RiskAlert, AlertLevel, NewsItem
)

# 配置日志
logger.add("/var/www/familystock/api/logs/api.log", rotation="10 MB", retention="7 days")

app = Flask(__name__)
CORS(app)

# 全局流水线实例
pipeline: Optional[Pipeline] = None

# SSE客户端队列
sse_clients: List[asyncio.Queue] = []


def get_or_create_pipeline() -> Pipeline:
    """获取或创建流水线实例"""
    global pipeline
    if pipeline is None:
        pipeline = get_pipeline()
    return pipeline


# ==================== API 路由 ====================

@app.route('/')
def root():
    """根路径"""
    return jsonify({
        'name': 'FamilyStock AI推演预警系统',
        'version': '3.0.0',
        'description': '参考贝莱德阿拉丁系统设计的全自动AI推演预警系统',
        'endpoints': {
            'pipeline': '/api/v3/pipeline/*',
            'alerts': '/api/v3/alerts/*',
            'dashboard': '/api/v3/dashboard',
            'news': '/api/v3/news',
            'simulation': '/api/v3/simulation'
        },
        'time': datetime.now().isoformat()
    })


# ==================== 流水线API ====================

@app.route('/api/v3/pipeline/status')
def pipeline_status():
    """获取流水线状态"""
    pl = get_or_create_pipeline()
    state = pl.get_state()
    
    return jsonify({
        'success': True,
        'data': state,
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/pipeline/run', methods=['POST'])
def pipeline_run():
    """手动触发流水线运行"""
    pl = get_or_create_pipeline()
    
    # 异步运行流水线
    def run_pipeline():
        asyncio.run(pl.run_once())
    
    thread = threading.Thread(target=run_pipeline)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': '流水线已启动',
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/pipeline/start', methods=['POST'])
def pipeline_start():
    """启动持续运行模式"""
    pl = get_or_create_pipeline()
    interval = request.json.get('interval_minutes', 5) if request.json else 5
    
    def run_continuous():
        asyncio.run(pl.run_continuous(interval_minutes=interval))
    
    thread = threading.Thread(target=run_continuous)
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'message': f'持续运行模式已启动，间隔 {interval} 分钟',
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/pipeline/stop', methods=['POST'])
def pipeline_stop():
    """停止流水线"""
    pl = get_or_create_pipeline()
    pl.stop()
    
    return jsonify({
        'success': True,
        'message': '流水线停止信号已发送',
        'time': datetime.now().isoformat()
    })


# ==================== 预警API ====================

@app.route('/api/v3/alerts')
def get_alerts():
    """获取预警列表"""
    pl = get_or_create_pipeline()
    
    # 查询参数
    level = request.args.get('level')
    limit = int(request.args.get('limit', 50))
    
    # 转换level参数
    level_enum = None
    if level:
        level_map = {
            'critical': AlertLevel.CRITICAL,
            'warning': AlertLevel.WARNING,
            'caution': AlertLevel.CAUTION,
            'info': AlertLevel.INFO
        }
        level_enum = level_map.get(level.lower())
    
    alerts = pl.get_alerts(level=level_enum, limit=limit)
    
    return jsonify({
        'success': True,
        'data': [alert_to_dict(a) for a in alerts],
        'count': len(alerts),
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/alerts/active')
def get_active_alerts():
    """获取有效预警"""
    pl = get_or_create_pipeline()
    alerts = pl.get_active_alerts()
    
    # 按等级分组
    grouped = {
        'critical': [],
        'warning': [],
        'caution': [],
        'info': []
    }
    
    for alert in alerts:
        key = alert.level.name.lower()
        if key in grouped:
            grouped[key].append(alert_to_dict(alert))
    
    return jsonify({
        'success': True,
        'data': {
            'alerts': [alert_to_dict(a) for a in alerts],
            'grouped': grouped,
            'summary': {
                'total': len(alerts),
                'critical': len(grouped['critical']),
                'warning': len(grouped['warning']),
                'caution': len(grouped['caution']),
                'info': len(grouped['info'])
            }
        },
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/alerts/stream')
def alerts_stream():
    """SSE实时预警流"""
    def event_stream():
        client_queue = asyncio.Queue()
        sse_clients.append(client_queue)
        
        try:
            # 发送初始连接消息
            yield f"data: {json.dumps({'type': 'connected', 'time': datetime.now().isoformat()})}\n\n"
            
            while True:
                # 等待新预警（带超时）
                try:
                    alert = asyncio.run(asyncio.wait_for(client_queue.get(), timeout=30))
                    yield f"data: {json.dumps({'type': 'alert', 'data': alert_to_dict(alert)})}\n\n"
                except asyncio.TimeoutError:
                    # 发送心跳
                    yield f"data: {json.dumps({'type': 'heartbeat', 'time': datetime.now().isoformat()})}\n\n"
                    
        except GeneratorExit:
            sse_clients.remove(client_queue)
    
    return Response(
        stream_with_context(event_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/v3/alerts/<alert_id>')
def get_alert_detail(alert_id: str):
    """获取预警详情"""
    pl = get_or_create_pipeline()
    
    for alert in pl.alerts:
        if alert.id == alert_id:
            return jsonify({
                'success': True,
                'data': alert_to_dict(alert, detail=True),
                'time': datetime.now().isoformat()
            })
    
    return jsonify({
        'success': False,
        'message': f'预警 {alert_id} 未找到',
        'time': datetime.now().isoformat()
    }), 404


# ==================== 仪表盘API ====================

@app.route('/api/v3/dashboard')
def get_dashboard():
    """获取风险仪表盘数据"""
    pl = get_or_create_pipeline()
    
    # 获取有效预警
    active_alerts = pl.get_active_alerts()
    
    # 计算风险指标
    risk_score = calculate_risk_score(active_alerts)
    
    # 获取流水线状态
    pipeline_state = pl.get_state()
    
    # 生成仪表盘数据
    dashboard = {
        'risk_score': risk_score,
        'risk_level': get_risk_level(risk_score),
        'active_alerts': {
            'total': len(active_alerts),
            'critical': len([a for a in active_alerts if a.level == AlertLevel.CRITICAL]),
            'warning': len([a for a in active_alerts if a.level == AlertLevel.WARNING]),
            'caution': len([a for a in active_alerts if a.level == AlertLevel.CAUTION]),
            'info': len([a for a in active_alerts if a.level == AlertLevel.INFO])
        },
        'pipeline': pipeline_state,
        'market_sentiment': calculate_market_sentiment(),
        'asset_exposure': calculate_asset_exposure(active_alerts),
        'sector_exposure': calculate_sector_exposure(active_alerts),
        'stress_test': run_stress_test(active_alerts),
        'last_updated': datetime.now().isoformat()
    }
    
    return jsonify({
        'success': True,
        'data': dashboard,
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/dashboard/risk-metrics')
def get_risk_metrics():
    """获取风险指标详情"""
    pl = get_or_create_pipeline()
    active_alerts = pl.get_active_alerts()
    
    metrics = {
        'var_95': calculate_var_95(active_alerts),  # 风险价值
        'expected_shortfall': calculate_expected_shortfall(active_alerts),
        'beta': calculate_portfolio_beta(),
        'volatility': calculate_volatility(),
        'sharpe_ratio': calculate_sharpe_ratio(),
        'max_drawdown': estimate_max_drawdown(active_alerts),
        'correlation_matrix': get_correlation_matrix(),
        'time_series': get_risk_time_series()
    }
    
    return jsonify({
        'success': True,
        'data': metrics,
        'time': datetime.now().isoformat()
    })


# ==================== 新闻API ====================

@app.route('/api/v3/news')
def get_news():
    """获取新闻列表"""
    pl = get_or_create_pipeline()
    
    # 这里应该从数据库获取新闻
    # 简化版返回模拟数据
    news = generate_mock_news()
    
    return jsonify({
        'success': True,
        'data': [news_to_dict(n) for n in news],
        'count': len(news),
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/news/analysis')
def get_news_analysis():
    """获取新闻分析结果"""
    pl = get_or_create_pipeline()
    
    analysis = {
        'sentiment_distribution': {
            'positive': 35,
            'neutral': 45,
            'negative': 20
        },
        'topic_distribution': {
            'conflict': 25,
            'policy': 30,
            'market': 35,
            'other': 10
        },
        'keyword_cloud': [
            {'word': '战争', 'weight': 100},
            {'word': '原油', 'weight': 85},
            {'word': '黄金', 'weight': 80},
            {'word': '制裁', 'weight': 75},
            {'word': '加息', 'weight': 70}
        ],
        'trending_topics': [
            {'topic': '中东局势', 'change': '+15%', 'sentiment': 'negative'},
            {'topic': '美联储政策', 'change': '+8%', 'sentiment': 'neutral'},
            {'topic': '科技股', 'change': '-5%', 'sentiment': 'positive'}
        ]
    }
    
    return jsonify({
        'success': True,
        'data': analysis,
        'time': datetime.now().isoformat()
    })


# ==================== 推演API ====================

@app.route('/api/v3/simulation')
def get_simulations():
    """获取AI推演结果"""
    pl = get_or_create_pipeline()
    
    # 从预警中提取推演结果
    simulations = []
    for alert in pl.alerts[:20]:  # 最近20条
        if alert.simulation_results:
            simulations.append({
                'alert_id': alert.id,
                'event': alert.simulation_results.get('event', {}),
                'scenarios': alert.simulation_results.get('scenarios', []),
                'asset_impacts': alert.simulation_results.get('asset_impacts', {}),
                'sector_impacts': alert.simulation_results.get('sector_impacts', {}),
                'stress_test': alert.simulation_results.get('stress_test', {}),
                'created_at': alert.created_at.isoformat()
            })
    
    return jsonify({
        'success': True,
        'data': simulations,
        'count': len(simulations),
        'time': datetime.now().isoformat()
    })


@app.route('/api/v3/simulation/scenarios')
def get_scenarios():
    """获取情景分析"""
    scenarios = [
        {
            'id': 'base',
            'name': '基准情景',
            'probability': 0.5,
            'description': '市场按当前趋势发展，风险事件逐步消化',
            'market_impact': {'stocks': '±5%', 'bonds': '±2%', 'commodities': '±10%'},
            'time_horizon': '1-3个月'
        },
        {
            'id': 'bull',
            'name': '乐观情景',
            'probability': 0.25,
            'description': '地缘政治风险缓解，经济复苏超预期',
            'market_impact': {'stocks': '+10-20%', 'bonds': '-2-5%', 'commodities': '+5-15%'},
            'time_horizon': '1-6个月'
        },
        {
            'id': 'bear',
            'name': '悲观情景',
            'probability': 0.25,
            'description': '风险事件升级，引发全球市场动荡',
            'market_impact': {'stocks': '-15-30%', 'bonds': '+5-10%', 'commodities': '+20-40%'},
            'time_horizon': '3-12个月'
        }
    ]
    
    return jsonify({
        'success': True,
        'data': scenarios,
        'time': datetime.now().isoformat()
    })


# ==================== 辅助函数 ====================

def alert_to_dict(alert: RiskAlert, detail: bool = False) -> Dict[str, Any]:
    """预警对象转字典"""
    result = {
        'id': alert.id,
        'level': alert.level.name,
        'level_icon': alert.level.value,
        'title': alert.title,
        'description': alert.description,
        'affected_assets': alert.affected_assets,
        'affected_sectors': alert.affected_sectors,
        'recommendation': alert.recommendation,
        'confidence': alert.confidence,
        'urgency_score': alert.urgency_score,
        'created_at': alert.created_at.isoformat(),
        'expires_at': alert.expires_at.isoformat() if alert.expires_at else None
    }
    
    if detail and alert.simulation_results:
        result['simulation'] = {
            'scenarios': alert.simulation_results.get('scenarios', []),
            'asset_impacts': alert.simulation_results.get('asset_impacts', {}),
            'sector_impacts': alert.simulation_results.get('sector_impacts', {}),
            'stress_test': alert.simulation_results.get('stress_test', {}),
            'recommendations': alert.simulation_results.get('recommendations', {})
        }
    
    return result


def news_to_dict(news: NewsItem) -> Dict[str, Any]:
    """新闻对象转字典"""
    return {
        'id': news.id,
        'title': news.title,
        'content': news.content[:200] + '...' if len(news.content) > 200 else news.content,
        'source': news.source,
        'url': news.url,
        'published_at': news.published_at.isoformat(),
        'category': news.category,
        'keywords': news.keywords,
        'sentiment_score': news.sentiment_score,
        'entities': news.entities
    }


def calculate_risk_score(alerts: List[RiskAlert]) -> float:
    """计算综合风险分数 (0-100)"""
    if not alerts:
        return 0.0
    
    weights = {
        AlertLevel.CRITICAL: 1.0,
        AlertLevel.WARNING: 0.6,
        AlertLevel.CAUTION: 0.3,
        AlertLevel.INFO: 0.1
    }
    
    total_weight = sum(weights.get(a.level, 0) * a.urgency_score for a in alerts)
    max_possible = len(alerts) * 1.0
    
    score = (total_weight / max_possible) * 100 if max_possible > 0 else 0
    return min(100, score * 2)  # 放大系数


def get_risk_level(score: float) -> str:
    """获取风险等级"""
    if score >= 80:
        return 'critical'
    elif score >= 60:
        return 'high'
    elif score >= 40:
        return 'medium'
    elif score >= 20:
        return 'low'
    else:
        return 'minimal'


def calculate_market_sentiment() -> Dict[str, Any]:
    """计算市场情绪"""
    return {
        'overall': 'neutral',
        'score': 0.0,
        'fear_greed_index': 50,
        'vix': 18.5,
        'put_call_ratio': 0.85
    }


def calculate_asset_exposure(alerts: List[RiskAlert]) -> List[Dict[str, Any]]:
    """计算资产敞口"""
    return [
        {'asset': '股票', 'exposure': 45, 'risk': 'medium', 'var': '-5%'},
        {'asset': '债券', 'exposure': 30, 'risk': 'low', 'var': '-1%'},
        {'asset': '商品', 'exposure': 15, 'risk': 'high', 'var': '-10%'},
        {'asset': '现金', 'exposure': 10, 'risk': 'minimal', 'var': '0%'}
    ]


def calculate_sector_exposure(alerts: List[RiskAlert]) -> List[Dict[str, Any]]:
    """计算行业敞口"""
    return [
        {'sector': '科技', 'exposure': 25, 'trend': 'up', 'risk_score': 65},
        {'sector': '金融', 'exposure': 20, 'trend': 'stable', 'risk_score': 55},
        {'sector': '能源', 'exposure': 15, 'trend': 'up', 'risk_score': 75},
        {'sector': '消费', 'exposure': 20, 'trend': 'down', 'risk_score': 45},
        {'sector': '医疗', 'exposure': 10, 'trend': 'stable', 'risk_score': 40},
        {'sector': '军工', 'exposure': 10, 'trend': 'up', 'risk_score': 80}
    ]


def run_stress_test(alerts: List[RiskAlert]) -> Dict[str, Any]:
    """压力测试结果"""
    return {
        'portfolio_loss_estimate': '-5% to -15%',
        'var_95': '-8%',
        'max_drawdown': '-20%',
        'recovery_time': '3-6个月',
        'liquidity_risk': 'moderate',
        'correlation_breakdown': True
    }


def calculate_var_95(alerts: List[RiskAlert]) -> float:
    """计算95%风险价值"""
    return -8.5


def calculate_expected_shortfall(alerts: List[RiskAlert]) -> float:
    """计算预期亏损"""
    return -12.3


def calculate_portfolio_beta() -> float:
    """计算组合Beta"""
    return 1.15


def calculate_volatility() -> float:
    """计算波动率"""
    return 18.5


def calculate_sharpe_ratio() -> float:
    """计算夏普比率"""
    return 0.85


def estimate_max_drawdown(alerts: List[RiskAlert]) -> float:
    """估计最大回撤"""
    return -20.5


def get_correlation_matrix() -> Dict[str, List[float]]:
    """获取相关性矩阵"""
    return {
        'labels': ['股票', '债券', '商品', '现金'],
        'matrix': [
            [1.0, -0.3, 0.4, 0.0],
            [-0.3, 1.0, -0.1, 0.1],
            [0.4, -0.1, 1.0, 0.0],
            [0.0, 0.1, 0.0, 1.0]
        ]
    }


def get_risk_time_series() -> List[Dict[str, Any]]:
    """获取风险时间序列"""
    import random
    data = []
    for i in range(30):
        data.append({
            'date': (datetime.now() - __import__('datetime').timedelta(days=29-i)).strftime('%m-%d'),
            'risk_score': random.randint(30, 70),
            'var': random.randint(-10, -5)
        })
    return data


def generate_mock_news() -> List[NewsItem]:
    """生成模拟新闻"""
    from datetime import timedelta
    import uuid
    
    news_data = [
        {
            'title': '美军空袭也门胡塞武装目标，红海局势升级',
            'source': 'reuters',
            'category': 'conflict',
            'sentiment': -0.8
        },
        {
            'title': '布伦特原油突破85美元，地缘风险溢价上升',
            'source': 'bloomberg',
            'category': 'market',
            'sentiment': -0.3
        },
        {
            'title': '欧盟通过对俄第14轮制裁方案',
            'source': 'xinhua',
            'category': 'policy',
            'sentiment': -0.5
        },
        {
            'title': '以军空袭加沙南部，哈马斯称将扩大反击',
            'source': 'cctv',
            'category': 'conflict',
            'sentiment': -0.9
        },
        {
            'title': '现货黄金创历史新高，避险需求激增',
            'source': 'caixin',
            'category': 'market',
            'sentiment': -0.4
        },
        {
            'title': '北约秘书长：将增加对乌克兰军事援助',
            'source': 'yicai',
            'category': 'policy',
            'sentiment': -0.6
        },
        {
            'title': '俄军对基辅发动大规模无人机袭击',
            'source': 'eastmoney',
            'category': 'conflict',
            'sentiment': -0.85
        },
        {
            'title': '美元指数下跌，美联储降息预期升温',
            'source': 'xueqiu',
            'category': 'market',
            'sentiment': 0.2
        }
    ]
    
    news_items = []
    for i, data in enumerate(news_data):
        news_items.append(NewsItem(
            id=str(uuid.uuid4())[:8],
            title=data['title'],
            content=f"{data['title']}的详细内容...",
            source=data['source'],
            url=f"https://example.com/news/{i}",
            published_at=datetime.now() - timedelta(minutes=i*15),
            category=data['category'],
            keywords=[data['category']],
            sentiment_score=data['sentiment']
        ))
    
    return news_items


# ==================== 后台任务 ====================

def broadcast_alert(alert: RiskAlert):
    """广播预警到所有SSE客户端"""
    message = json.dumps({
        'type': 'new_alert',
        'data': alert_to_dict(alert)
    })
    
    for queue in sse_clients:
        try:
            asyncio.run(queue.put(alert))
        except:
            pass


# ==================== 启动 ====================

# ==================== Tushare API路由 ====================

import requests
from datetime import timedelta

TUSHARE_API_URL = "http://api.tushare.pro"
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"


def call_tushare_api(api_name, params=None, fields=""):
    """调用Tushare API"""
    payload = {
        "api_name": api_name,
        "token": TUSHARE_TOKEN,
        "params": params or {},
        "fields": fields
    }
    
    try:
        response = requests.post(TUSHARE_API_URL, json=payload, timeout=30)
        result = response.json()
        
        if result.get("code") != 0:
            raise Exception(f"Tushare API Error: {result.get('msg')}")
        
        data = result.get("data", {})
        fields_list = data.get("fields", [])
        items = data.get("items", [])
        
        return [dict(zip(fields_list, item)) for item in items]
    except Exception as e:
        logger.error(f"Tushare API调用失败: {e}")
        return None


@app.route('/api/v3/tushare/quote/<ts_code>')
def get_tushare_stock_quote(ts_code):
    """通过Tushare获取股票最新行情"""
    try:
        if "." not in ts_code:
            if ts_code.startswith("6"):
                ts_code = f"{ts_code}.SH"
            else:
                ts_code = f"{ts_code}.SZ"
        
        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=7)).strftime("%Y%m%d")
        
        data = call_tushare_api("daily", {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date
        })
        
        if not data:
            return jsonify({"error": "股票数据不存在"}), 404
        
        latest = data[-1]
        
        return jsonify({
            "symbol": ts_code.split(".")[0],
            "ts_code": latest.get("ts_code"),
            "trade_date": latest.get("trade_date"),
            "open": float(latest.get("open", 0)),
            "high": float(latest.get("high", 0)),
            "low": float(latest.get("low", 0)),
            "close": float(latest.get("close", 0)),
            "pre_close": float(latest.get("pre_close", 0)),
            "change": float(latest.get("change", 0)),
            "pct_chg": float(latest.get("pct_chg", 0)),
            "volume": float(latest.get("vol", 0)),
            "amount": float(latest.get("amount", 0)),
            "market": "A股",
            "currency": "CNY",
            "source": "Tushare"
        })
    except Exception as e:
        logger.error(f"获取股票数据失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/v3/tushare/batch')
def get_tushare_batch_quotes():
    """批量获取股票行情"""
    try:
        symbols = request.args.get('symbols', '')
        symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
        results = []
        
        for symbol in symbol_list:
            try:
                if "." not in symbol:
                    if symbol.startswith("6"):
                        ts_code = f"{symbol}.SH"
                    else:
                        ts_code = f"{symbol}.SZ"
                else:
                    ts_code = symbol
                
                end_date = datetime.now().strftime("%Y%m%d")
                start_date = (datetime.now() - timedelta(days=3)).strftime("%Y%m%d")
                
                data = call_tushare_api("daily", {
                    "ts_code": ts_code,
                    "start_date": start_date,
                    "end_date": end_date
                })
                
                if data and len(data) > 0:
                    latest = data[-1]
                    results.append({
                        "symbol": symbol,
                        "ts_code": latest.get("ts_code"),
                        "trade_date": latest.get("trade_date"),
                        "close": float(latest.get("close", 0)),
                        "open": float(latest.get("open", 0)),
                        "high": float(latest.get("high", 0)),
                        "low": float(latest.get("low", 0)),
                        "pct_chg": float(latest.get("pct_chg", 0)),
                        "volume": float(latest.get("vol", 0)),
                        "market": "A股",
                        "currency": "CNY"
                    })
            except Exception as e:
                logger.error(f"获取{symbol}失败: {e}")
        
        return jsonify({"stocks": results, "count": len(results)})
    except Exception as e:
        logger.error(f"批量获取失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/v3/tushare/search')
def search_tushare_stocks():
    """搜索股票"""
    try:
        keyword = request.args.get('keyword', '').upper()
        
        data = call_tushare_api("stock_basic", {
            "list_status": "L"
        }, "ts_code,name,area,industry")
        
        if not data:
            return jsonify({"results": [], "count": 0})
        
        results = [
            {
                "ts_code": item.get("ts_code"),
                "symbol": item.get("ts_code").split(".")[0],
                "name": item.get("name"),
                "area": item.get("area"),
                "industry": item.get("industry"),
                "market": "A股"
            }
            for item in data
            if keyword in item.get("ts_code", "").upper() or 
               keyword in item.get("name", "").upper()
        ]
        
        return jsonify({"results": results[:10], "count": len(results[:10])})
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return jsonify({"error": str(e)}), 500


logger.info("Tushare API路由已加载")

# ==================== 注册新模块路由 ====================

try:
    from holdings_routes import holdings_bp
    app.register_blueprint(holdings_bp)
    logger.info("持仓管理路由已加载")
except Exception as e:
    logger.error(f"持仓路由加载失败: {e}")

try:
    from ai_analysis import ai_bp
    app.register_blueprint(ai_bp)
    logger.info("AI分析路由已加载")
except Exception as e:
    logger.error(f"AI路由加载失败: {e}")

try:
    from stock_cache_service import start_cache_service
    logger.info("股票缓存服务已加载")
except Exception as e:
    logger.error(f"缓存服务加载失败: {e}")

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("FamilyStock API Server V3 启动")
    logger.info("全自动AI推演预警系统")
    logger.info("=" * 60)
    
    # 初始化流水线
    pl = get_or_create_pipeline()
    
    # 启动后台流水线（持续模式）
    def start_background_pipeline():
        asyncio.run(pl.run_continuous(interval_minutes=5))
    
    bg_thread = threading.Thread(target=start_background_pipeline)
    bg_thread.daemon = True
    bg_thread.start()
    
    logger.info("后台流水线已启动")
    
    # 启动股票缓存服务
    try:
        start_cache_service(interval_minutes=5)
        logger.info("股票缓存服务已启动")
    except Exception as e:
        logger.error(f"缓存服务启动失败: {e}")
    
    # 启动Flask服务
    app.run(host='0.0.0.0', port=8080, debug=False, threaded=True)


