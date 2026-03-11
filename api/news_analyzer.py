#!/usr/bin/env python3
"""
MiniRock 新闻-股票关联分析模块
分析新闻事件与持仓股票的关联度
"""

import json
import re
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StockHolding:
    """持仓股票"""
    symbol: str
    name: str
    sector: str = ""  # 所属行业
    tags: List[str] = None  # 标签
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []

@dataclass
class NewsEvent:
    """新闻事件"""
    title: str
    content: str
    source: str
    timestamp: str
    keywords: List[str] = None
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []

@dataclass
class CorrelationResult:
    """关联分析结果"""
    stock: StockHolding
    news: NewsEvent
    correlation_score: float  # 0-100
    impact_level: str  # high/medium/low
    reason: str


class NewsStockAnalyzer:
    """新闻-股票关联分析器"""
    
    # 行业关键词映射
    SECTOR_KEYWORDS = {
        '白酒': ['茅台', '五粮液', '泸州老窖', '白酒', '酱香', '浓香', '酒水', '酒类', '消费'],
        '新能源': ['宁德时代', '比亚迪', '新能源', '电池', '锂电', '电动车', '储能', '光伏', '风电'],
        '银行': ['平安银行', '招商银行', '银行', '金融', '信贷', '利率', '央行', '降息', '降准'],
        '科技': ['科大讯飞', '海康威视', '科技', 'AI', '人工智能', '芯片', '半导体', '算力'],
        '医药': ['医药', '医疗', '疫苗', '医保', '集采', '生物', '健康'],
        '房地产': ['房地产', '楼市', '房价', '地产', '建材', '基建'],
        '汽车': ['汽车', '整车', '造车', '车企', '销量', '新能源'],
    }
    
    # 情感关键词
    POSITIVE_KEYWORDS = ['增长', '上涨', '利好', '突破', '创新', '扩张', '盈利', '增持', '看好', '推荐']
    NEGATIVE_KEYWORDS = ['下跌', '利空', '风险', '亏损', '减持', '警告', '召回', '调查', '处罚', '暴雷']
    
    def __init__(self):
        self.holdings: List[StockHolding] = []
    
    def set_holdings(self, holdings: List[Dict]):
        """设置持仓股票"""
        self.holdings = []
        for h in holdings:
            stock = StockHolding(
                symbol=h.get('symbol', ''),
                name=h.get('name', ''),
                sector=h.get('sector', ''),
                tags=h.get('tags', [])
            )
            self.holdings.append(stock)
    
    def analyze(self, news_list: List[Dict]) -> List[CorrelationResult]:
        """分析新闻与持仓的关联"""
        results = []
        
        for news_data in news_list:
            news = NewsEvent(
                title=news_data.get('title', ''),
                content=news_data.get('content', ''),
                source=news_data.get('source', ''),
                timestamp=news_data.get('timestamp', ''),
                keywords=self._extract_keywords(news_data.get('title', '') + ' ' + news_data.get('content', ''))
            )
            
            for stock in self.holdings:
                score, reason = self._calculate_correlation(stock, news)
                if score > 30:  # 只返回有关联的结果
                    impact = 'high' if score > 70 else ('medium' if score > 50 else 'low')
                    results.append(CorrelationResult(
                        stock=stock,
                        news=news,
                        correlation_score=score,
                        impact_level=impact,
                        reason=reason
                    ))
        
        # 按关联度排序
        results.sort(key=lambda x: x.correlation_score, reverse=True)
        return results
    
    def _extract_keywords(self, text: str) -> List[str]:
        """从文本提取关键词"""
        # 简单的中文分词，实际应使用jieba等工具
        words = re.findall(r'[\u4e00-\u9fa5]{2,}', text)
        return list(set(words))
    
    def _calculate_correlation(self, stock: StockHolding, news: NewsEvent) -> Tuple[float, str]:
        """计算股票与新闻的关联度"""
        score = 0.0
        reasons = []
        
        text = (news.title + ' ' + news.content).lower()
        
        # 1. 直接名称匹配 (最高权重)
        if stock.name in text or stock.symbol in text:
            score += 40
            reasons.append(f"直接提及{stock.name}")
        
        # 2. 行业关键词匹配
        for sector, keywords in self.SECTOR_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                if stock.sector == sector or any(kw in stock.name for kw in keywords):
                    score += 25
                    reasons.append(f"涉及{sector}行业")
                    break
        
        # 3. 标签匹配
        for tag in stock.tags:
            if tag in text:
                score += 15
                reasons.append(f"匹配标签'{tag}'")
        
        # 4. 情感分析加分
        positive_count = sum(1 for kw in self.POSITIVE_KEYWORDS if kw in text)
        negative_count = sum(1 for kw in self.NEGATIVE_KEYWORDS if kw in text)
        
        if positive_count > negative_count:
            score += 10
            reasons.append("正面情绪")
        elif negative_count > positive_count:
            score += 10
            reasons.append("负面情绪")
        
        # 5. 新闻来源可信度
        trusted_sources = ['新华社', '央视', '财联社', '证券时报', '上海证券报']
        if any(src in news.source for src in trusted_sources):
            score += 10
            reasons.append("权威来源")
        
        # 限制最高分
        score = min(100, score)
        
        reason_str = "; ".join(reasons) if reasons else "弱关联"
        return score, reason_str
    
    def generate_report(self, results: List[CorrelationResult]) -> str:
        """生成关联分析报告"""
        if not results:
            return "暂无与持仓相关的重要新闻"
        
        lines = [
            "## 📊 新闻-持仓关联分析",
            f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"**持仓数量**: {len(self.holdings)} 只",
            f"**相关新闻**: {len(results)} 条",
            ""
        ]
        
        # 高影响新闻
        high_impact = [r for r in results if r.impact_level == 'high']
        if high_impact:
            lines.append("### 🔴 高度关注")
            for r in high_impact[:3]:
                emoji = "📈" if "正面" in r.reason else "📉"
                lines.append(f"{emoji} **{r.stock.name}** ({r.stock.symbol})")
                lines.append(f"   关联度: {r.correlation_score:.0f}% | {r.reason}")
                lines.append(f"   新闻: {r.news.title}")
                lines.append("")
        
        # 中等影响
        medium_impact = [r for r in results if r.impact_level == 'medium']
        if medium_impact:
            lines.append("### 🟡 值得关注")
            for r in medium_impact[:3]:
                lines.append(f"• **{r.stock.name}**: {r.news.title[:30]}...")
            lines.append("")
        
        # 持仓风险汇总
        lines.append("### 📋 持仓风险摘要")
        affected_stocks = set(r.stock.symbol for r in results)
        safe_stocks = [h for h in self.holdings if h.symbol not in affected_stocks]
        
        if safe_stocks:
            lines.append(f"✅ **暂无明显风险**: {', '.join(h.name for h in safe_stocks[:3])}")
        
        if high_impact:
            lines.append(f"⚠️ **需要关注**: {', '.join(set(r.stock.name for r in high_impact))}")
        
        return "\n".join(lines)


# 便捷函数
def analyze_news_for_holdings(news_list: List[Dict], holdings: List[Dict]) -> str:
    """快速分析函数"""
    analyzer = NewsStockAnalyzer()
    analyzer.set_holdings(holdings)
    results = analyzer.analyze(news_list)
    return analyzer.generate_report(results)


# 测试
if __name__ == "__main__":
    # 模拟持仓
    test_holdings = [
        {"symbol": "600519", "name": "贵州茅台", "sector": "白酒"},
        {"symbol": "000858", "name": "五粮液", "sector": "白酒"},
        {"symbol": "300750", "name": "宁德时代", "sector": "新能源"},
    ]
    
    # 模拟新闻
    test_news = [
        {
            "title": "贵州茅台发布2025年报，净利润同比增长15%",
            "content": "贵州茅台今日发布年报，显示业绩稳健增长...",
            "source": "财联社",
            "timestamp": "2026-03-09 09:30"
        },
        {
            "title": "新能源板块今日大涨，宁德时代领涨",
            "content": "受政策利好影响，新能源板块今日表现强势...",
            "source": "证券时报",
            "timestamp": "2026-03-09 10:15"
        },
        {
            "title": "国际局势紧张，黄金价格创新高",
            "content": "地缘政治风险推动避险资产上涨...",
            "source": "Reuters",
            "timestamp": "2026-03-09 08:00"
        }
    ]
    
    report = analyze_news_for_holdings(test_news, test_holdings)
    print(report)
