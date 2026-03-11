#!/usr/bin/env python3
"""
FamilyStock AI推演预警系统 - 全自动流水线调度器
参考贝莱德阿拉丁(Aladdin)系统设计

流水线: 新闻采集 → NLP分析 → 黑天鹅识别 → AI推演 → 预警生成
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import queue

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

# 配置日志
logger.add("/var/www/familystock/api/logs/pipeline.log", rotation="10 MB", retention="7 days")


class PipelineStage(Enum):
    """流水线阶段"""
    IDLE = "idle"
    CRAWLING = "crawling"
    NLP_ANALYZING = "nlp_analyzing"
    BLACK_SWAN_DETECTING = "black_swan_detecting"
    AI_SIMULATING = "ai_simulating"
    ALERT_GENERATING = "alert_generating"
    COMPLETED = "completed"
    ERROR = "error"


class AlertLevel(Enum):
    """预警等级"""
    CRITICAL = "🔴"      # 严重
    WARNING = "🟠"       # 警告
    CAUTION = "🟡"       # 注意
    INFO = "🔵"          # 信息


@dataclass
class NewsItem:
    """新闻条目"""
    id: str
    title: str
    content: str
    source: str
    url: str
    published_at: datetime
    category: str = ""
    keywords: List[str] = None
    sentiment_score: float = 0.0
    entities: Dict[str, List[str]] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []
        if self.entities is None:
            self.entities = {}


@dataclass
class RiskAlert:
    """风险预警"""
    id: str
    level: AlertLevel
    title: str
    description: str
    affected_assets: List[str]
    affected_sectors: List[str]
    recommendation: str
    confidence: float
    urgency_score: float
    created_at: datetime
    expires_at: Optional[datetime] = None
    related_news: List[str] = None
    simulation_results: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.related_news is None:
            self.related_news = []
        if self.simulation_results is None:
            self.simulation_results = {}


@dataclass
class PipelineState:
    """流水线状态"""
    stage: PipelineStage
    start_time: datetime
    current_task: str
    progress: float  # 0-100
    news_count: int
    alerts_generated: int
    last_error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "stage": self.stage.value,
            "start_time": self.start_time.isoformat(),
            "current_task": self.current_task,
            "progress": self.progress,
            "news_count": self.news_count,
            "alerts_generated": self.alerts_generated,
            "last_error": self.last_error
        }


class NewsCrawler:
    """新闻采集器"""
    
    SOURCES = {
        "xinhua": "新华社",
        "cctv": "央视财经",
        "reuters": "路透社",
        "bloomberg": "彭博社",
        "caixin": "财新网",
        "yicai": "第一财经",
        "eastmoney": "东方财富",
        "xueqiu": "雪球",
        "weibo": "微博"
    }
    
    def __init__(self):
        self.crawl_history = []
        
    async def crawl_all(self) -> List[NewsItem]:
        """采集所有数据源"""
        logger.info("开始新闻采集...")
        all_news = []
        
        # 并行采集所有数据源
        tasks = [self._crawl_source(source) for source in self.SOURCES.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for source, result in zip(self.SOURCES.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"{source} 采集失败: {result}")
            else:
                all_news.extend(result)
                logger.info(f"{source} 采集完成: {len(result)} 条")
        
        # 去重
        seen = set()
        unique_news = []
        for news in all_news:
            key = news.title[:30]  # 使用标题前30字符去重
            if key not in seen:
                seen.add(key)
                unique_news.append(news)
        
        logger.info(f"新闻采集完成，共 {len(unique_news)} 条")
        return unique_news
    
    async def _crawl_source(self, source: str) -> List[NewsItem]:
        """采集单个数据源"""
        # 模拟采集（实际应调用爬虫API）
        await asyncio.sleep(0.5)  # 模拟网络延迟
        
        # 生成模拟新闻数据
        mock_news = self._generate_mock_news(source)
        return mock_news
    
    def _generate_mock_news(self, source: str) -> List[NewsItem]:
        """生成模拟新闻（实际应从API获取）"""
        import uuid
        
        templates = {
            "conflict": [
                "{location}局势紧张，{party}发动{action}",
                "{party}警告：{threat}",
                "{location}冲突升级，{impact}"
            ],
            "market": [
                "{asset}价格{direction}，{reason}",
                "{indicator}数据{result}，市场{reaction}",
                "{country}央行{action}，{impact}"
            ],
            "policy": [
                "{country}宣布{policy}，{impact}",
                "{organization}通过{decision}，{reaction}",
                "{country}与{country2}签署{agreement}"
            ]
        }
        
        news_items = []
        count = 3  # 每个源采集3条
        
        for i in range(count):
            news_id = str(uuid.uuid4())[:8]
            news_items.append(NewsItem(
                id=news_id,
                title=f"[{self.SOURCES[source]}] 新闻标题 {i+1}",
                content=f"这是来自{self.SOURCES[source]}的新闻内容，涉及市场动态...",
                source=source,
                url=f"https://example.com/news/{news_id}",
                published_at=datetime.now() - timedelta(minutes=i*10),
                category=["conflict", "market", "policy"][i % 3]
            ))
        
        return news_items


class NLPAnalyzer:
    """NLP分析器"""
    
    # 风险关键词库
    RISK_KEYWORDS = {
        "military": ["战争", "冲突", "导弹", "空袭", "军事", "打击", "袭击", "轰炸"],
        "geopolitical": ["制裁", "断交", "封锁", "禁运", "外交", "领土", "争端"],
        "financial": ["崩盘", "熔断", "破产", "危机", "暴跌", "债务", "违约"],
        "natural": ["地震", "海啸", "台风", "洪水", "灾害", "疫情"],
        "policy": ["加息", "降息", "政策", "监管", "关税", "贸易", "限制"]
    }
    
    def __init__(self):
        self.analysis_history = []
    
    async def analyze_batch(self, news_items: List[NewsItem]) -> List[NewsItem]:
        """批量分析新闻"""
        logger.info(f"开始NLP分析，共 {len(news_items)} 条新闻...")
        
        analyzed_items = []
        for i, item in enumerate(news_items):
            analyzed = await self._analyze_single(item)
            analyzed_items.append(analyzed)
            
            if (i + 1) % 10 == 0:
                logger.info(f"NLP分析进度: {i+1}/{len(news_items)}")
        
        logger.info("NLP分析完成")
        return analyzed_items
    
    async def _analyze_single(self, item: NewsItem) -> NewsItem:
        """分析单条新闻"""
        # 提取关键词
        item.keywords = self._extract_keywords(item.title + " " + item.content)
        
        # 情绪分析
        item.sentiment_score = self._analyze_sentiment(item.title + " " + item.content)
        
        # 实体识别
        item.entities = self._extract_entities(item.title + " " + item.content)
        
        return item
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        # 简化版关键词提取
        words = []
        for category, keywords in self.RISK_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    words.append(kw)
        return list(set(words))
    
    def _analyze_sentiment(self, text: str) -> float:
        """情绪分析 (-1 到 +1)"""
        # 简化版情绪分析
        negative_words = ["下跌", "暴跌", "危机", "冲突", "战争", "制裁", "风险"]
        positive_words = ["上涨", "增长", "利好", "合作", "复苏", "稳定"]
        
        score = 0
        for word in negative_words:
            if word in text:
                score -= 0.2
        for word in positive_words:
            if word in text:
                score += 0.2
        
        return max(-1, min(1, score))
    
    def _extract_entities(self, text: str) -> Dict[str, List[str]]:
        """提取实体"""
        # 简化版实体识别
        countries = ["中国", "美国", "俄罗斯", "欧盟", "日本", "韩国", "伊朗", "以色列"]
        assets = ["原油", "黄金", "美元", "人民币", "比特币", "股票", "债券"]
        
        found_countries = [c for c in countries if c in text]
        found_assets = [a for a in assets if a in text]
        
        return {
            "countries": found_countries,
            "assets": found_assets,
            "organizations": []
        }


class BlackSwanDetector:
    """黑天鹅事件检测器"""
    
    # 黑天鹅事件模式
    BLACK_SWAN_PATTERNS = {
        "war_outbreak": {
            "name": "战争爆发",
            "keywords": ["宣战", "全面战争", "大规模军事行动"],
            "threshold": 0.8,
            "urgency": 1.0
        },
        "financial_crisis": {
            "name": "金融危机",
            "keywords": ["系统性风险", "银行破产", "市场崩盘"],
            "threshold": 0.85,
            "urgency": 0.95
        },
        "supply_chain_collapse": {
            "name": "供应链崩溃",
            "keywords": ["港口关闭", "航运中断", "物资短缺"],
            "threshold": 0.75,
            "urgency": 0.9
        },
        "energy_crisis": {
            "name": "能源危机",
            "keywords": ["石油禁运", "天然气断供", "能源短缺"],
            "threshold": 0.7,
            "urgency": 0.85
        },
        "pandemic": {
            "name": "大规模疫情",
            "keywords": ["全球大流行", "病毒变异", "封锁"],
            "threshold": 0.8,
            "urgency": 0.9
        }
    }
    
    def __init__(self):
        self.detection_history = []
        self.sentiment_history = []
    
    async def detect(self, news_items: List[NewsItem]) -> List[Dict[str, Any]]:
        """检测黑天鹅事件"""
        logger.info("开始黑天鹅事件检测...")
        
        detected_events = []
        
        for item in news_items:
            # 检测异常情绪
            anomaly = self._detect_sentiment_anomaly(item)
            if anomaly["is_anomaly"]:
                logger.warning(f"检测到情绪异常: {item.title}")
            
            # 检测黑天鹅模式
            for pattern_id, pattern in self.BLACK_SWAN_PATTERNS.items():
                score = self._match_pattern(item, pattern)
                if score >= pattern["threshold"]:
                    detected_events.append({
                        "pattern_id": pattern_id,
                        "pattern_name": pattern["name"],
                        "news_item": item,
                        "score": score,
                        "urgency": pattern["urgency"],
                        "matched_keywords": [kw for kw in pattern["keywords"] if kw in item.title or kw in item.content]
                    })
                    logger.warning(f"检测到黑天鹅事件: {pattern['name']} - {item.title}")
        
        # 按紧急度排序
        detected_events.sort(key=lambda x: x["urgency"], reverse=True)
        
        logger.info(f"黑天鹅检测完成，发现 {len(detected_events)} 个潜在事件")
        return detected_events
    
    def _detect_sentiment_anomaly(self, item: NewsItem) -> Dict[str, Any]:
        """检测情绪异常"""
        self.sentiment_history.append(item.sentiment_score)
        
        if len(self.sentiment_history) < 10:
            return {"is_anomaly": False}
        
        # 保持最近100条记录
        if len(self.sentiment_history) > 100:
            self.sentiment_history = self.sentiment_history[-100:]
        
        import numpy as np
        mean = np.mean(self.sentiment_history[:-1])
        std = np.std(self.sentiment_history[:-1])
        
        if std == 0:
            return {"is_anomaly": False}
        
        z_score = abs(item.sentiment_score - mean) / std
        
        return {
            "is_anomaly": z_score > 2.5,
            "z_score": z_score,
            "current": item.sentiment_score
        }
    
    def _match_pattern(self, item: NewsItem, pattern: Dict) -> float:
        """匹配事件模式"""
        text = item.title + " " + item.content
        matched = sum(1 for kw in pattern["keywords"] if kw in text)
        return matched / len(pattern["keywords"])


class AISimulator:
    """AI推演引擎 - 模拟贝莱德阿拉丁的情景分析"""
    
    # 资产类别映射
    ASSET_CLASSES = {
        "stocks": ["A股", "港股", "美股", "欧股"],
        "bonds": ["国债", "企业债", "高收益债"],
        "commodities": ["原油", "黄金", "铜", "天然气"],
        "currencies": ["美元", "人民币", "欧元", "日元"],
        "crypto": ["比特币", "以太坊"]
    }
    
    # 行业映射
    SECTORS = {
        "energy": ["石油", "天然气", "煤炭", "新能源"],
        "finance": ["银行", "保险", "证券", "金融科技"],
        "tech": ["半导体", "软件", "硬件", "互联网"],
        "consumer": ["白酒", "家电", "零售", "汽车"],
        "healthcare": ["制药", "医疗器械", "医疗服务"],
        "defense": ["军工", "航空航天", "安防"]
    }
    
    def __init__(self):
        self.simulation_history = []
    
    async def simulate(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """AI推演 - 分析事件对市场的影响"""
        logger.info(f"开始AI推演: {event['pattern_name']}")
        
        # 情景分析
        scenarios = self._generate_scenarios(event)
        
        # 资产影响分析
        asset_impacts = self._analyze_asset_impacts(event)
        
        # 行业影响分析
        sector_impacts = self._analyze_sector_impacts(event)
        
        # 压力测试
        stress_test = self._run_stress_test(event)
        
        # 生成投资建议
        recommendations = self._generate_recommendations(event, asset_impacts, sector_impacts)
        
        result = {
            "event": event,
            "scenarios": scenarios,
            "asset_impacts": asset_impacts,
            "sector_impacts": sector_impacts,
            "stress_test": stress_test,
            "recommendations": recommendations,
            "confidence": event["score"],
            "simulated_at": datetime.now().isoformat()
        }
        
        self.simulation_history.append(result)
        logger.info("AI推演完成")
        
        return result
    
    def _generate_scenarios(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """生成情景分析"""
        scenarios = [
            {
                "name": "基准情景",
                "probability": 0.5,
                "description": "事件按当前趋势发展，市场逐步消化影响",
                "market_impact": "温和波动",
                "time_horizon": "1-3个月"
            },
            {
                "name": "乐观情景",
                "probability": 0.25,
                "description": "事件得到快速解决，市场恢复稳定",
                "market_impact": "小幅上涨",
                "time_horizon": "1个月内"
            },
            {
                "name": "悲观情景",
                "probability": 0.25,
                "description": "事件升级扩大，引发连锁反应",
                "market_impact": "大幅下跌",
                "time_horizon": "3-6个月"
            }
        ]
        return scenarios
    
    def _analyze_asset_impacts(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """分析资产影响"""
        pattern_id = event["pattern_id"]
        
        # 基于事件类型的资产影响映射
        impact_map = {
            "war_outbreak": {
                "gold": {"direction": "up", "magnitude": "+10-20%", "confidence": 0.9},
                "oil": {"direction": "up", "magnitude": "+15-30%", "confidence": 0.85},
                "stocks": {"direction": "down", "magnitude": "-10-20%", "confidence": 0.8},
                "bonds": {"direction": "up", "magnitude": "+2-5%", "confidence": 0.7}
            },
            "financial_crisis": {
                "gold": {"direction": "up", "magnitude": "+5-15%", "confidence": 0.85},
                "stocks": {"direction": "down", "magnitude": "-20-40%", "confidence": 0.9},
                "bonds": {"direction": "mixed", "magnitude": "±5%", "confidence": 0.6}
            },
            "supply_chain_collapse": {
                "commodities": {"direction": "up", "magnitude": "+10-25%", "confidence": 0.8},
                "shipping": {"direction": "up", "magnitude": "+20-50%", "confidence": 0.85},
                "manufacturing": {"direction": "down", "magnitude": "-10-20%", "confidence": 0.75}
            },
            "energy_crisis": {
                "oil": {"direction": "up", "magnitude": "+20-50%", "confidence": 0.9},
                "gas": {"direction": "up", "magnitude": "+30-100%", "confidence": 0.9},
                "renewable": {"direction": "up", "magnitude": "+10-20%", "confidence": 0.7}
            },
            "pandemic": {
                "healthcare": {"direction": "up", "magnitude": "+10-30%", "confidence": 0.8},
                "travel": {"direction": "down", "magnitude": "-20-40%", "confidence": 0.85},
                "tech": {"direction": "up", "magnitude": "+5-15%", "confidence": 0.6}
            }
        }
        
        return impact_map.get(pattern_id, {})
    
    def _analyze_sector_impacts(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """分析行业影响"""
        pattern_id = event["pattern_id"]
        
        sector_map = {
            "war_outbreak": {
                "defense": {"impact": "positive", "strength": "strong"},
                "energy": {"impact": "positive", "strength": "strong"},
                "finance": {"impact": "negative", "strength": "moderate"},
                "consumer": {"impact": "negative", "strength": "moderate"}
            },
            "financial_crisis": {
                "finance": {"impact": "negative", "strength": "severe"},
                "tech": {"impact": "negative", "strength": "strong"},
                "consumer": {"impact": "negative", "strength": "strong"}
            },
            "energy_crisis": {
                "energy": {"impact": "positive", "strength": "strong"},
                "consumer": {"impact": "negative", "strength": "strong"},
                "transportation": {"impact": "negative", "strength": "severe"}
            }
        }
        
        return sector_map.get(pattern_id, {})
    
    def _run_stress_test(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """压力测试"""
        return {
            "portfolio_loss_estimate": "-5% to -15%",
            "var_95": "-8%",  # 95%置信区间的风险价值
            "max_drawdown": "-20%",
            "recovery_time": "3-6个月",
            "liquidity_risk": "moderate",
            "correlation_breakdown": True
        }
    
    def _generate_recommendations(self, event: Dict[str, Any], 
                                   asset_impacts: Dict, 
                                   sector_impacts: Dict) -> Dict[str, List[str]]:
        """生成投资建议"""
        pattern_id = event["pattern_id"]
        
        recommendations = {
            "immediate_actions": [],
            "portfolio_adjustments": [],
            "hedging_strategies": [],
            "opportunities": []
        }
        
        if pattern_id == "war_outbreak":
            recommendations["immediate_actions"] = [
                "增持黄金和原油相关资产",
                "降低股票仓位至50%以下",
                "增加现金储备"
            ]
            recommendations["hedging_strategies"] = [
                "买入VIX看涨期权",
                "配置避险货币（日元、瑞郎）",
                "考虑购买看跌期权保护"
            ]
        elif pattern_id == "financial_crisis":
            recommendations["immediate_actions"] = [
                "大幅减持风险资产",
                "增持国债和高评级债券",
                "保持高流动性"
            ]
        elif pattern_id == "energy_crisis":
            recommendations["opportunities"] = [
                "关注新能源板块",
                "配置传统能源股票",
                "投资能源效率技术"
            ]
        
        return recommendations


class AlertGenerator:
    """预警生成器"""
    
    def __init__(self):
        self.alert_history = []
        self.alert_counter = 0
    
    async def generate(self, simulation_result: Dict[str, Any]) -> RiskAlert:
        """生成预警"""
        self.alert_counter += 1
        
        event = simulation_result["event"]
        
        # 确定预警等级
        level = self._determine_level(event)
        
        # 构建预警对象
        alert = RiskAlert(
            id=f"ALT-{datetime.now().strftime('%Y%m%d')}-{self.alert_counter:04d}",
            level=level,
            title=self._generate_title(event),
            description=self._generate_description(event, simulation_result),
            affected_assets=list(simulation_result["asset_impacts"].keys()),
            affected_sectors=list(simulation_result["sector_impacts"].keys()),
            recommendation=self._format_recommendations(simulation_result["recommendations"]),
            confidence=event["score"],
            urgency_score=event["urgency"],
            created_at=datetime.now(),
            expires_at=datetime.now() + timedelta(days=7),
            related_news=[event["news_item"].id],
            simulation_results=simulation_result
        )
        
        self.alert_history.append(alert)
        logger.info(f"生成预警: {alert.id} - {alert.title}")
        
        return alert
    
    def _determine_level(self, event: Dict[str, Any]) -> AlertLevel:
        """确定预警等级"""
        urgency = event["urgency"]
        score = event["score"]
        
        if urgency >= 0.95 and score >= 0.9:
            return AlertLevel.CRITICAL
        elif urgency >= 0.85 and score >= 0.8:
            return AlertLevel.WARNING
        elif urgency >= 0.7 and score >= 0.7:
            return AlertLevel.CAUTION
        else:
            return AlertLevel.INFO
    
    def _generate_title(self, event: Dict[str, Any]) -> str:
        """生成预警标题"""
        return f"{event['pattern_name']}风险预警"
    
    def _generate_description(self, event: Dict[str, Any], 
                               simulation: Dict[str, Any]) -> str:
        """生成预警描述"""
        news_title = event["news_item"].title
        scenarios = simulation["scenarios"]
        
        desc = f"基于新闻「{news_title}」的分析，"
        desc += f"检测到{event['pattern_name']}风险信号。"
        desc += f"基准情景概率{scenarios[0]['probability']*100:.0f}%，"
        desc += f"建议密切关注市场动态。"
        
        return desc
    
    def _format_recommendations(self, recs: Dict[str, List[str]]) -> str:
        """格式化建议"""
        lines = []
        
        if recs.get("immediate_actions"):
            lines.append("【立即行动】")
            lines.extend([f"• {a}" for a in recs["immediate_actions"]])
        
        if recs.get("portfolio_adjustments"):
            lines.append("\n【组合调整】")
            lines.extend([f"• {a}" for a in recs["portfolio_adjustments"]])
        
        if recs.get("hedging_strategies"):
            lines.append("\n【对冲策略】")
            lines.extend([f"• {a}" for a in recs["hedging_strategies"]])
        
        if recs.get("opportunities"):
            lines.append("\n【投资机会】")
            lines.extend([f"• {a}" for a in recs["opportunities"]])
        
        return "\n".join(lines)


class Pipeline:
    """全自动AI推演流水线"""
    
    def __init__(self):
        self.state = PipelineState(
            stage=PipelineStage.IDLE,
            start_time=datetime.now(),
            current_task="等待启动",
            progress=0,
            news_count=0,
            alerts_generated=0
        )
        
        self.crawler = NewsCrawler()
        self.nlp = NLPAnalyzer()
        self.detector = BlackSwanDetector()
        self.simulator = AISimulator()
        self.generator = AlertGenerator()
        
        self.alerts: List[RiskAlert] = []
        self.running = False
        self._state_lock = threading.Lock()
    
    def _update_state(self, **kwargs):
        """更新状态"""
        with self._state_lock:
            for key, value in kwargs.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
    
    async def run_once(self) -> List[RiskAlert]:
        """运行一次完整流水线"""
        logger.info("=" * 60)
        logger.info("启动 FamilyStock AI推演流水线")
        logger.info("=" * 60)
        
        new_alerts = []
        
        try:
            # Stage 1: 新闻采集
            self._update_state(
                stage=PipelineStage.CRAWLING,
                current_task="正在采集新闻数据...",
                progress=10
            )
            news_items = await self.crawler.crawl_all()
            self._update_state(news_count=len(news_items), progress=20)
            
            if not news_items:
                logger.warning("未采集到新闻，跳过本次流水线")
                self._update_state(stage=PipelineStage.IDLE, current_task="无新闻数据")
                return []
            
            # Stage 2: NLP分析
            self._update_state(
                stage=PipelineStage.NLP_ANALYZING,
                current_task="正在进行NLP分析...",
                progress=30
            )
            analyzed_items = await self.nlp.analyze_batch(news_items)
            self._update_state(progress=45)
            
            # Stage 3: 黑天鹅检测
            self._update_state(
                stage=PipelineStage.BLACK_SWAN_DETECTING,
                current_task="正在检测黑天鹅事件...",
                progress=50
            )
            detected_events = await self.detector.detect(analyzed_items)
            self._update_state(progress=65)
            
            if not detected_events:
                logger.info("未检测到黑天鹅事件")
                self._update_state(
                    stage=PipelineStage.COMPLETED,
                    current_task="分析完成，无风险事件",
                    progress=100
                )
                return []
            
            # Stage 4 & 5: AI推演 + 预警生成
            self._update_state(
                stage=PipelineStage.AI_SIMULATING,
                current_task=f"正在推演 {len(detected_events)} 个风险事件...",
                progress=70
            )
            
            for i, event in enumerate(detected_events):
                # AI推演
                simulation = await self.simulator.simulate(event)
                
                # 生成预警
                self._update_state(
                    stage=PipelineStage.ALERT_GENERATING,
                    current_task=f"正在生成预警 {i+1}/{len(detected_events)}...",
                    progress=70 + (i + 1) / len(detected_events) * 25
                )
                
                alert = await self.generator.generate(simulation)
                new_alerts.append(alert)
                self.alerts.append(alert)
            
            self._update_state(
                stage=PipelineStage.COMPLETED,
                current_task="预警生成完成",
                alerts_generated=len(self.alerts),
                progress=100
            )
            
            logger.info(f"流水线完成，生成 {len(new_alerts)} 个预警")
            
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            self._update_state(
                stage=PipelineStage.ERROR,
                current_task=f"执行失败: {str(e)}",
                last_error=str(e)
            )
        
        return new_alerts
    
    async def run_continuous(self, interval_minutes: int = 5):
        """持续运行流水线"""
        self.running = True
        logger.info(f"启动持续运行模式，间隔 {interval_minutes} 分钟")
        
        while self.running:
            try:
                await self.run_once()
                
                # 等待下一次运行
                for i in range(interval_minutes * 60):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"持续运行出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟重试
    
    def stop(self):
        """停止流水线"""
        self.running = False
        logger.info("流水线停止信号已发送")
    
    def get_state(self) -> Dict[str, Any]:
        """获取当前状态"""
        return self.state.to_dict()
    
    def get_alerts(self, level: Optional[AlertLevel] = None, 
                   limit: int = 50) -> List[RiskAlert]:
        """获取预警列表"""
        alerts = self.alerts
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        
        # 按时间倒序
        alerts = sorted(alerts, key=lambda x: x.created_at, reverse=True)
        
        return alerts[:limit]
    
    def get_active_alerts(self) -> List[RiskAlert]:
        """获取有效预警"""
        now = datetime.now()
        return [a for a in self.alerts if a.expires_at is None or a.expires_at > now]


# 全局流水线实例
_pipeline_instance: Optional[Pipeline] = None


def get_pipeline() -> Pipeline:
    """获取流水线实例（单例）"""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = Pipeline()
    return _pipeline_instance


if __name__ == "__main__":
    # 测试运行
    async def test():
        pipeline = get_pipeline()
        alerts = await pipeline.run_once()
        
        print(f"\n生成 {len(alerts)} 个预警:")
        for alert in alerts:
            print(f"\n[{alert.level.value}] {alert.title}")
            print(f"  描述: {alert.description}")
            print(f"  紧急度: {alert.urgency_score*100:.1f}%")
            print(f"  建议: {alert.recommendation[:100]}...")
    
    asyncio.run(test())
