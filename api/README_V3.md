# FamilyStock AI推演预警系统 V3
# 参考贝莱德阿拉丁(Aladdin)系统设计

## 系统架构

### 全自动流水线
```
新闻采集 → NLP分析 → 黑天鹅识别 → AI推演 → 预警生成
```

### 核心组件

1. **pipeline.py** - 全自动AI推演流水线
   - NewsCrawler: 新闻采集器
   - NLPAnalyzer: NLP分析器
   - BlackSwanDetector: 黑天鹅事件检测器
   - AISimulator: AI推演引擎
   - AlertGenerator: 预警生成器

2. **server_v3.py** - API服务器
   - RESTful API
   - SSE实时预警流
   - 风险仪表盘数据

3. **index_v3.html** - 前端页面
   - 实时预警面板
   - 风险仪表盘(类似阿拉丁)
   - 资产敞口分析
   - 情景分析
   - 自动滚动新闻

## API端点

### 流水线API
- `GET /api/v3/pipeline/status` - 流水线状态
- `POST /api/v3/pipeline/run` - 手动触发流水线
- `POST /api/v3/pipeline/start` - 启动持续运行模式
- `POST /api/v3/pipeline/stop` - 停止流水线

### 预警API
- `GET /api/v3/alerts` - 获取预警列表
- `GET /api/v3/alerts/active` - 获取有效预警
- `GET /api/v3/alerts/stream` - SSE实时预警流
- `GET /api/v3/alerts/<id>` - 获取预警详情

### 仪表盘API
- `GET /api/v3/dashboard` - 风险仪表盘数据
- `GET /api/v3/dashboard/risk-metrics` - 风险指标详情

### 新闻API
- `GET /api/v3/news` - 新闻列表
- `GET /api/v3/news/analysis` - 新闻分析结果

### 推演API
- `GET /api/v3/simulation` - AI推演结果
- `GET /api/v3/simulation/scenarios` - 情景分析

## 启动方式

```bash
cd /var/www/familystock/api
./start.sh
```

或手动启动:
```bash
python3 server_v3.py
```

## 访问系统

- 前端页面: http://43.160.193.165/index_v3.html
- API服务: http://43.160.193.165:8080

## 参考贝莱德阿拉丁系统特点

1. **实时风险监测** - 流水线每5分钟自动运行
2. **多资产类别关联分析** - 股票、债券、商品、现金敞口分析
3. **压力测试和情景分析** - 基准/乐观/悲观三种情景
4. **自动化预警推送** - 实时SSE流推送预警
5. **投资组合风险敞口分析** - VaR、Beta、波动率等指标

## 预警等级

- 🔴 **严重(CRITICAL)** - 紧急度≥95%，需立即关注
- 🟠 **警告(WARNING)** - 紧急度≥85%，需密切关注
- 🟡 **注意(CAUTION)** - 紧急度≥70%，需留意
- 🔵 **信息(INFO)** - 一般性提示

## 文件结构

```
/var/www/familystock/
├── index_v3.html          # 前端页面
├── api/
│   ├── server_v3.py       # API服务器
│   ├── pipeline.py        # 全自动流水线
│   ├── start.sh           # 启动脚本
│   └── logs/              # 日志目录
```
