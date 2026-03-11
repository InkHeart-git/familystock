# FamilyStock V3 - 部署和测试指南

## 系统概述

FamilyStock V3 是参考贝莱德阿拉丁(Aladdin)系统设计的全自动AI推演预警系统。

### 核心功能
1. **全自动流水线**: 新闻采集 → NLP分析 → 黑天鹅识别 → AI推演 → 预警生成
2. **风险热力图**: 实时显示各行业风险热力分布
3. **投资组合风险敞口**: 分析各资产/行业敞口
4. **压力测试情景**: 模拟乐观/基准/悲观情景下的P&L影响
5. **实时P&L分析**: 计算预期盈亏和风险价值(VaR)

## 文件结构

```
/var/www/familystock/v3/
├── index.html          # 前端页面（增强版）
├── server_v3.py        # API服务器
├── start.sh            # 启动脚本
├── test_api.py         # 测试脚本
└── logs/               # 日志目录
```

## 快速部署

### 1. 启动API服务器

```bash
cd /var/www/familystock/v3
chmod +x start.sh
./start.sh
```

或者手动启动:
```bash
cd /var/www/familystock/v3
pip3 install flask flask-cors logurer
python3 server_v3.py
```

### 2. 访问页面

- V3增强版: http://43.160.193.165/v3/
- API文档: http://43.160.193.165:8080/

## API端点

### 流水线
- `GET /api/v3/pipeline/status` - 获取流水线状态
- `POST /api/v3/pipeline/run` - 手动触发流水线

### 预警
- `GET /api/v3/alerts` - 获取预警列表
- `GET /api/v3/alerts/active` - 获取活跃预警
- `GET /api/v3/alerts/<id>` - 获取预警详情

### 仪表盘
- `GET /api/v3/dashboard` - 获取风险仪表盘数据

### 新闻
- `GET /api/v3/news` - 获取新闻列表

### 股票分析
- `POST /api/v3/stock/analyze` - 分析股票

## 测试

### 运行API测试
```bash
cd /var/www/familystock/v3
python3 test_api.py
```

### 手动测试
```bash
# 测试根路径
curl http://43.160.193.165:8080/

# 获取预警列表
curl http://43.160.193.165:8080/api/v3/alerts

# 获取仪表盘
curl http://43.160.193.165:8080/api/v3/dashboard

# 分析股票
curl -X POST http://43.160.193.165:8080/api/v3/stock/analyze \
  -H "Content-Type: application/json" \
  -d '{"symbol": "600519"}'
```

## 功能说明

### 1. 风险仪表盘
- 风险分数仪表盘（0-100）
- 风险等级显示（极低/低/中/高/严重）
- 风险热力图（8大行业）

### 2. 资产敞口分析
- 股票/债券/商品/现金配置比例
- 可视化条形图
- 悬停显示详细信息

### 3. 压力测试 & P&L影响
- 乐观情景（25%概率）
- 基准情景（50%概率）
- 悲观情景（25%概率）
- 预期P&L（加权平均）
- VaR(95%) 和最大回撤

### 4. AI选股
- 输入股票代码自动分析
- AI评分（0-100）
- 情景分析（乐观/基准/悲观）
- 风险指标（VaR、最大回撤）
- AI投资建议

### 5. 预警系统
- 实时预警面板
- 三级预警（🔴严重/🟠警告/🟡注意）
- 推送通知
- 预警详情抽屉

## 技术特点

- **全自动运行**: 无需手动输入，系统自动采集分析
- **实时更新**: 自动刷新数据，无需手动刷新页面
- **参考阿拉丁**: 风险指标、压力测试、情景分析
- **模块化设计**: 新增功能以面板形式集成，不影响原有布局

## 注意事项

1. API服务器默认运行在8080端口
2. 前端页面通过相对路径访问API
3. 首次加载可能需要等待AI推演完成
4. 建议定期运行测试脚本验证API状态