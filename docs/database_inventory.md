# FamilyStock 数据库清单

生成时间：2026-03-18

## 架构说明

FamilyStock 采用**双数据库架构**：
- MySQL：存储基础数据（股票列表、新闻）
- PostgreSQL：存储用户数据、缓存、业务数据

---

## MySQL 数据库 (`familystock`)

| 表名 | 用途 | 存储内容 |
|------|------|----------|
| `stocks` | 股票基础列表 | A股/美股/ETF 的代码、名称、市场分类、上市日期 |
| `news` | 财经新闻 | 新闻标题、内容、来源、发布时间 |

**连接配置：**
```
host: localhost
user: familystock
password: Familystock@2026
database: familystock
charset: utf8mb4
```

---

## PostgreSQL 数据库 (`minirock`)

| 表名 | 用途 | 存储内容 |
|------|------|----------|
| `users` | 用户认证 | 用户手机号、名称、密码哈希 |
| `user_tokens` | Token 管理 | Token 黑名单、过期时间、吊销状态 |
| `holdings` | 用户持仓 | 用户持仓股票、数量、平均成本、市场、币种 |
| `stock_cache` | 实时行情缓存 | 最新价、开盘/高/低、涨跌幅、成交量、成交额、AI评分 |
| `exchange_rates` | 汇率缓存 | 外币兑换汇率、更新时间 |
| `ai_analysis_reports` | AI 分析报告 | 生成的分析报告、风险等级、评分、创建时间 |
| `news` | 财经新闻（优化版）| 标题、内容、来源、URL、分类、情感分数、关键词、发布时间 |

**连接配置：**
```
host: localhost
database: minirock
user: minirock
password: minirock123
port: 5432
```

---

## 数据流转

1. **基础数据同步** → Tushare Pro → MySQL `stocks`/`news`
2. **实时行情** → API 拉取 → PostgreSQL `stock_cache` 缓存
3. **用户数据** → 前端操作 → PostgreSQL `users`/`holdings`
4. **AI 分析** → 生成报告 → PostgreSQL `ai_analysis_reports`
5. **汇率转换** → 缓存 → PostgreSQL `exchange_rates`

---

*文件生成：灵犀（新加坡节点）*
