# FamilyStock 股票详情页

家庭股票投资管理工具的前端页面。

## 文件说明

| 文件 | 说明 |
|------|------|
| `stock-detail.html` | 股票详情页主页面 |
| `stock-data.js` | 前端数据获取与处理脚本 |
| `stock-api.js` | Node.js 后端 API 服务（可选） |

## 功能特性

### 1. 股票搜索
- 支持按股票代码搜索（6位数字）
- 支持按股票名称搜索
- 实时显示搜索结果列表

### 2. 股票详情展示
- **公司基本信息**：名称、代码、所属市场、行业、概念
- **实时行情**：最新价、涨跌幅、更新时间
- **主营业务**：业务描述、公司简介
- **收入构成**：饼图展示 + 表格数据
- **财务指标**：市值、市盈率、市净率、换手率等
- **价格走势**：近期K线图表

### 3. 数据来源
- 腾讯财经 API（实时行情）
- 东方财富 API（搜索、K线、财务数据）

## 使用方法

### 纯前端方式
直接在浏览器中打开 `stock-detail.html`：
```bash
# 使用 Python 简单启动一个HTTP服务器
cd /var/www/familystock
python3 -m http.server 8080

# 然后访问 http://localhost:8080/stock-detail.html
```

### 配合后端 API
启动 Node.js API 服务以获取真实数据：
```bash
cd /var/www/familystock
npm install  # 如需额外依赖
node stock-api.js

# API 服务运行在 http://localhost:3000
```

## API 端点

| 端点 | 说明 | 示例 |
|------|------|------|
| `GET /api/search?q=关键词` | 搜索股票 | `/api/search?q=茅台` |
| `GET /api/stock/:code` | 股票详情 | `/api/stock/600519` |
| `GET /api/batch?codes=` | 批量行情 | `/api/batch?codes=600519,000001` |
| `GET /api/kline/:code` | K线数据 | `/api/kline/600519?count=30` |

## 技术栈

- **HTML5** - 页面结构
- **Tailwind CSS** - 样式框架（CDN引入）
- **JavaScript** - 交互逻辑
- **Chart.js** - 图表展示（CDN引入）

## 注意事项

1. 由于浏览器跨域限制，前端直接调用部分 API 可能会受限
2. 生产环境建议配合后端代理使用 `stock-api.js`
3. 当前版本包含模拟数据用于演示，真实数据需通过后端 API 获取

## 股票代码规则

| 开头数字 | 市场 | 示例 |
|----------|------|------|
| 600/601/603/688 | 上海主板/科创板 | 600519 贵州茅台 |
| 000/001/002/003 | 深圳主板/中小板 | 000001 平安银行 |
| 300/301 | 创业板 | 300750 宁德时代 |
| 8/4 | 北交所 | 835305 云创数据 |
