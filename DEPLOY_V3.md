# FamilyStock AI推演预警系统 - 部署说明

## 系统架构

### 全自动流水线
```
新闻采集 → NLP分析 → 黑天鹅识别 → AI推演 → 预警生成
```

### 新增功能模块
1. **风险热力图** - 实时显示全球风险热力分布
2. **投资组合风险敞口** - 分析各资产/行业敞口
3. **压力测试情景** - 模拟不同情景下的组合表现
4. **实时P&L影响分析** - 计算潜在盈亏影响

## 文件说明

### API文件
- `pipeline.py` - 全自动AI推演流水线核心
- `server_v3.py` - API服务器V3

### 前端文件
- `index.html` - 主页面（保持原有布局）
- `familystock-v3.html` - 增强版（新增AI推演面板）

## 部署步骤

### 1. 安装依赖
```bash
cd /var/www/familystock/api
pip install -r requirements.txt
```

### 2. 启动API服务
```bash
python3 server_v3.py
```

### 3. 访问页面
- 原页面: http://43.160.193.165/familystock-unified-v2.html
- 增强版: http://43.160.193.165/familystock-v3.html

## API端点

### 流水线状态
```
GET /api/v3/pipeline/status
```

### 预警列表
```
GET /api/v3/alerts
GET /api/v3/alerts/active
```

### 风险仪表盘
```
GET /api/v3/dashboard
```

### 新闻分析
```
GET /api/v3/news
GET /api/v3/news/analysis
```

### AI推演结果
```
GET /api/v3/simulation
```

## 使用说明

### 股票分析
1. 在选股页面输入股票代码
2. 系统自动触发AI推演
3. 显示风险热力图和P&L分析

### 风险监控
1. 首页风险仪表盘实时更新
2. 预警面板自动显示新预警
3. 点击预警查看详细推演结果

## 技术特点

- **全自动运行**: 无需手动输入，系统自动采集分析
- **实时更新**: SSE推送新预警，无需刷新页面
- **参考阿拉丁**: 风险指标、压力测试、情景分析
- **模块化设计**: 新增功能以面板形式集成，不影响原有布局