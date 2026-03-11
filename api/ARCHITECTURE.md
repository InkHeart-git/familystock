# FamilyStock AI推演预警系统 V3 - 架构设计文档

## 参考系统: 贝莱德阿拉丁(Aladdin)

贝莱德阿拉丁是全球领先的资产管理平台，核心能力包括：
- 实时风险监测与计算
- 多资产类别关联分析
- 压力测试和情景分析
- 自动化风险预警
- 投资组合风险敞口分析

---

## 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        FamilyStock V3                           │
│                    AI推演预警系统架构                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐         │
│  │   前端层     │    │   API层     │    │  流水线层    │         │
│  │             │    │             │    │             │         │
│  │ index_v3.html│◄───│ server_v3.py│◄───│ pipeline.py │         │
│  │             │    │             │    │             │         │
│  │ • 风险仪表盘 │    │ • REST API  │    │ • 新闻采集  │         │
│  │ • 预警面板  │    │ • SSE流    │    │ • NLP分析   │         │
│  │ • 情景分析  │    │ • 数据聚合  │    │ • 黑天鹅检测 │         │
│  │ • 资产敞口  │    │             │    │ • AI推演    │         │
│  │             │    │             │    │ • 预警生成  │         │
│  └─────────────┘    └─────────────┘    └─────────────┘         │
│         │                  │                  │                 │
│         ▼                  ▼                  ▼                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    数据流 (全自动)                        │   │
│  │                                                          │   │
│  │   新闻采集 ──► NLP分析 ──► 黑天鹅识别 ──► AI推演 ──► 预警 │   │
│  │      │           │            │           │        │     │   │
│  │      ▼           ▼            ▼           ▼        ▼     │   │
│  │   [5分钟]    [情绪/实体]   [模式匹配]   [情景分析] [🔴🟠🟡]│   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 流水线详细设计

### Stage 1: 新闻采集 (NewsCrawler)
```python
输入: 无
输出: List[NewsItem]
频率: 每5分钟
数据源:
  - 紧急: 新华社、央视 (5分钟)
  - 高频: 路透社、彭博社 (10分钟)
  - 中频: 财新、第一财经、东方财富 (15分钟)
  - 社交: 微博 (3分钟)
```

### Stage 2: NLP分析 (NLPAnalyzer)
```python
输入: List[NewsItem]
输出: List[NewsItem] (带分析结果)
处理:
  - 中文分词 (jieba)
  - 关键词提取
  - 情绪分析 (-1 ~ +1)
  - 实体识别 (人名/地名/机构/股票)
```

### Stage 3: 黑天鹅检测 (BlackSwanDetector)
```python
输入: List[NewsItem]
输出: List[DetectedEvent]
检测模式:
  - war_outbreak: 战争爆发
  - financial_crisis: 金融危机
  - supply_chain_collapse: 供应链崩溃
  - energy_crisis: 能源危机
  - pandemic: 大规模疫情
阈值: 0.7-0.85 (根据事件类型)
```

### Stage 4: AI推演 (AISimulator)
```python
输入: DetectedEvent
输出: SimulationResult
推演内容:
  - 情景分析 (基准/乐观/悲观)
  - 资产影响分析 (股票/债券/商品/货币)
  - 行业影响分析 (能源/金融/科技/消费)
  - 压力测试 (VaR/最大回撤/恢复时间)
  - 投资建议 (立即行动/组合调整/对冲策略)
```

### Stage 5: 预警生成 (AlertGenerator)
```python
输入: SimulationResult
输出: RiskAlert
等级判定:
  - CRITICAL (🔴): 紧急度≥95% 且 置信度≥90%
  - WARNING (🟠): 紧急度≥85% 且 置信度≥80%
  - CAUTION (🟡): 紧急度≥70% 且 置信度≥70%
  - INFO (🔵): 其他
```

---

## 核心数据模型

### RiskAlert (风险预警)
```python
{
    id: str                    # 预警ID
    level: AlertLevel          # 等级 (CRITICAL/WARNING/CAUTION/INFO)
    title: str                 # 标题
    description: str           # 描述
    affected_assets: List[str] # 影响资产
    affected_sectors: List[str]# 影响行业
    recommendation: str        # AI投资建议
    confidence: float          # 置信度 (0-1)
    urgency_score: float       # 紧急度 (0-1)
    created_at: datetime       # 创建时间
    expires_at: datetime       # 过期时间
    simulation_results: dict   # 推演详情
}
```

### Dashboard (风险仪表盘)
```python
{
    risk_score: float          # 综合风险分数 (0-100)
    risk_level: str            # 风险等级 (critical/high/medium/low)
    active_alerts: {           # 活跃预警统计
        total: int
        critical: int
        warning: int
        caution: int
        info: int
    }
    market_sentiment: {        # 市场情绪
        overall: str
        fear_greed_index: int
        vix: float
    }
    asset_exposure: List[{     # 资产敞口
        asset: str
        exposure: float         # 占比
        risk: str
        var: str
    }]
    sector_exposure: List[{    # 行业敞口
        sector: str
        exposure: float
        trend: str
        risk_score: float
    }]
    stress_test: {             # 压力测试
        portfolio_loss_estimate: str
        var_95: str
        max_drawdown: str
        recovery_time: str
    }
}
```

---

## API设计

### 获取风险仪表盘
```http
GET /api/v3/dashboard

Response:
{
    "success": true,
    "data": {
        "risk_score": 65.5,
        "risk_level": "high",
        "active_alerts": {
            "total": 5,
            "critical": 1,
            "warning": 2,
            "caution": 2,
            "info": 0
        },
        ...
    }
}
```

### 获取活跃预警
```http
GET /api/v3/alerts/active

Response:
{
    "success": true,
    "data": {
        "alerts": [...],
        "grouped": {
            "critical": [...],
            "warning": [...],
            "caution": [...],
            "info": []
        },
        "summary": {
            "total": 5,
            "critical": 1,
            ...
        }
    }
}
```

### SSE实时预警流
```http
GET /api/v3/alerts/stream

Event Stream:
data: {"type": "connected", "time": "2024-01-01T00:00:00"}
data: {"type": "alert", "data": {...}}
data: {"type": "heartbeat", "time": "2024-01-01T00:00:30"}
```

---

## 前端设计

### 页面结构
```
index_v3.html
├── 顶部新闻滚动条 (实时)
├── 预警面板 (可折叠)
├── 首页
│   ├── 风险仪表盘 (阿拉丁风格)
│   ├── 资产敞口分析
│   ├── 流水线状态
│   ├── 全球冲突热点
│   ├── 大宗商品期货
│   └── 情景分析
├── 预警中心
│   ├── 预警统计
│   ├── 预警过滤器
│   └── 预警列表
├── AI选股
├── 新闻分析
└── AI推演结果
```

### 实时更新机制
```javascript
// 轮询更新 (30秒间隔)
setInterval(() => {
    fetchDashboard();
    fetchAlerts();
    fetchPipelineStatus();
}, 30000);

// SSE实时推送
const eventSource = new EventSource('/api/v3/alerts/stream');
eventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.type === 'alert') {
        showToast(data.data);
    }
};
```

---

## 部署说明

### 环境要求
- Python 3.8+
- Flask
- 依赖包: flask-cors, requests, loguru, jieba, snownlp, numpy

### 启动步骤
```bash
cd /var/www/familystock/api
./start.sh
```

### 访问地址
- 前端: http://43.160.193.165/index_v3.html
- API: http://43.160.193.165:8080

---

## 与阿拉丁系统的对比

| 功能 | 阿拉丁 | FamilyStock V3 |
|------|--------|----------------|
| 实时风险监测 | ✅ | ✅ (5分钟周期) |
| 多资产关联分析 | ✅ | ✅ (4类资产) |
| 压力测试 | ✅ | ✅ (3种情景) |
| 自动化预警 | ✅ | ✅ (SSE推送) |
| 风险敞口分析 | ✅ | ✅ (VaR/Beta) |
| 组合优化 | ✅ | ⚠️ (简化版) |
| 历史回测 | ✅ | ❌ |
| 全球数据覆盖 | ✅ | ⚠️ (主要市场) |

---

## 未来扩展

1. **机器学习模型** - 用深度学习替代规则检测
2. **历史回测** - 验证预警准确性
3. **组合优化** - 基于风险的投资建议
4. **更多数据源** - 卫星数据、供应链数据
5. **可视化大屏** - 专业级风险监控界面
