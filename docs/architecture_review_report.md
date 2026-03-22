# MiniRock 架构整改汇总报告

**报告生成时间**: 2026-03-20 10:40  
**检查范围**: 前端 + 后端API + 数据库架构  
**对照文档**: 贝莱德阿拉丁系统对标分析和开发计划

---

## 一、当前架构现状

### 1.1 数据层架构

| 数据库 | 表名 | 状态 | 说明 |
|--------|------|------|------|
| **SQLite** | `stocks` | ✅ | 个股基础信息 (5,490条) |
| | `stock_quotes` | ✅ | 个股行情快照 (6,810条) |
| | `stock_daily` | ⚠️ | 日K历史数据 (仅5条) |
| | `index_quotes` | ✅ | **新增-大盘指数专用** (8条) |
| | `news` | ✅ | 新闻数据 (800条) |
| | `articles` | ❌ | 空表 |
| | `stock_basic` | ❌ | 空表(备用) |
| | `stock_hsgt_hold` | ❌ | 空表(北向资金) |
| **PostgreSQL** | `users` | ✅ | 用户表 |
| | `holdings` | ✅ | 持仓表 |
| | `index_cache` | ⚠️ | 灵犀维护(生产环境) |

**评价**: 
- ✅ 个股/指数数据已分离 (`index_quotes`表)
- ⚠️ 日K历史数据严重不足 (仅5条)
- ❌ 缺少组合持仓历史、交易记录表

---

### 1.2 API层架构

| 功能模块 | API端点 | 状态 | 备注 |
|---------|---------|------|------|
| **用户认证** | | | |
| | POST `/auth/login` | ✅ | 登录 |
| | POST `/auth/register` | ✅ | 注册 |
| | GET `/auth/verify` | ✅ | 验证 |
| | GET `/auth/profile` | ✅ | 用户信息 |
| **个股数据** | | | |
| | GET `/stock/basic/{code}` | ✅ | 基础信息 |
| | GET `/stock/kline/{code}` | ✅ | K线数据 |
| | GET `/stock/finance/{code}` | ✅ | 财务数据 |
| | GET `/stock/capital/{code}` | ⚠️ | 资金流向(可能mock) |
| | GET `/stock/news/{code}` | ✅ | 个股新闻 |
| **行情服务** | | | |
| | GET `/tushare/quote/{ts_code}` | ✅ | 实时行情 |
| | GET `/tushare/search` | ✅ | 股票搜索 |
| | GET `/tushare/index` | ✅ | **已整改-从index_quotes读取** |
| | GET `/tushare/batch` | ✅ | 批量行情 |
| | GET `/tushare/news` | ✅ | 新闻列表 |
| **持仓组合** | | | |
| | GET `/portfolio/holdings` | ✅ | 持仓列表 |
| | POST `/portfolio/holdings` | ✅ | 添加持仓 |
| | DELETE `/portfolio/holdings/{symbol}` | ✅ | 删除持仓 |
| | GET `/portfolio/list` | ✅ | 组合列表 |
| **AI分析** | | | |
| | POST `/ai/analyze-stock` | ✅ | 个股AI分析 |
| | POST `/ai/analyze-portfolio` | ✅ | 组合AI分析 |
| | GET `/ai/fundamental/{ts_code}` | ⚠️ | 基本面分析 |
| | GET `/ai/technical/{ts_code}` | ⚠️ | 技术面分析 |
| | GET `/ai/risk/{ts_code}` | ⚠️ | 风险分析 |
| | GET `/ai/valuation/{ts_code}` | ⚠️ | 估值分析 |
| **组合分析(高级)** | | | |
| | GET `/portfolio/analysis` | ✅ | 组合分析 |
| | GET `/portfolio/analysis/demo` | ✅ | Demo数据 |
| | GET `/portfolio/correlation/matrix` | ⚠️ | 相关性矩阵 |
| | GET `/portfolio/allocation/recommend` | ❌ | 资产配置建议 |
| | GET `/portfolio/allocation/demo` | ❌ | Demo |
| **风险预警** | | | |
| | GET `/risk/alerts` | ⚠️ | 风险预警 |
| | GET `/risk/zones` | ⚠️ | 风险区域 |
| | GET `/risk/zones/{name}` | ⚠️ | 特定区域 |
| | GET `/risk/scenario/{symbol}` | ⚠️ | 情景分析 |

**API统计**: 51个端点
- ✅ 已实现: 约35个
- ⚠️ 部分实现/mock: 约12个
- ❌ 未实现: 约4个

---

### 1.3 前端页面架构

| 页面 | 文件名 | 状态 | 功能覆盖 | 问题 |
|------|--------|------|---------|------|
| **登录/注册** | `minirock-auth.html` | ✅ | 登录、注册 | 无 |
| **主页v1** | `minirock.html` | ⚠️ | 市场概览、持仓 | 品牌名不一致 |
| **主页v2** | `minirock-v2.html` | ⚠️ | 市场概览、持仓 | **当前入口页** |
| **个股详情** | `stock-detail.html` | ✅ | 行情、AI分析、K线 | 品牌名"灵犀" |
| **组合分析** | `portfolio-analysis.html` | ✅ | 组合分析、资产配置 | 部分功能mock |
| **我的持仓** | `portfolio.html` | ✅ | 持仓管理 | 无 |
| **自选股** | `watchlist.html` | ✅ | 自选股列表 | 无 |
| **市场行情** | `market.html` | ⚠️ | 市场数据 | 功能较简单 |
| **入口页** | `index.html` | ❌ | 跳转页 | 应该删除 |

**前端问题汇总**:
1. **品牌名不统一**: ministone / MiniRock / 灵犀 混用
2. **多个主页版本**: minirock.html / minirock-v2.html / index.html 并存
3. **缺少功能页面**:
   - 风险预警中心
   - 情景模拟/压力测试
   - 资产配置优化器
   - 绩效归因分析
   - 多因子风险分析

---

## 二、对照需求文档的差距分析

### 2.1 阿拉丁核心功能矩阵对照

| 阿拉丁能力 | 需求阶段 | MiniRock现状 | 差距 |
|-----------|---------|-------------|------|
| **投资组合分析** | | | |
| 多维度风险分析 | Phase 1 | 基础风险指标 | ⚠️ 缺少VaR、夏普比率等 |
| 情景模拟 | Phase 2 | 有API端点 | ❌ 前端无界面 |
| 压力测试 | Phase 2 | 有API端点 | ❌ 前端无界面 |
| 因子暴露分析 | Phase 2 | ❌ 未实现 | ❌ 完全缺失 |
| **风险管理** | | | |
| 实时风险监控 | Phase 1 | 基础预警 | ⚠️ 缺少实时计算 |
| VaR计算 | Phase 2 | ❌ 未实现 | ❌ 完全缺失 |
| 尾部风险分析 | Phase 2 | ❌ 未实现 | ❌ 完全缺失 |
| 合规预警 | Phase 1 | ⚠️ 部分实现 | ⚠️ 规则简单 |
| **绩效归因** | | | |
| Brinson归因 | Phase 2 | ❌ 未实现 | ❌ 完全缺失 |
| 因子归因 | Phase 2 | ❌ 未实现 | ❌ 完全缺失 |
| 交易成本分析 | Phase 2 | ❌ 未实现 | ❌ 完全缺失 |
| **资产配置** | | | |
| 优化器 | Phase 2 | ❌ API未实现 | ❌ 完全缺失 |
| 多资产配置 | Phase 1 | ⚠️ 部分支持 | ⚠️ 仅A股 |
| 目标导向投资 | Phase 2 | ❌ 未实现 | ❌ 完全缺失 |
| **数据中台** | | | |
| 统一数据模型 | Phase 1 | ⚠️ 刚整改 | ⚠️ 部分统一 |
| 市场数据 | Phase 1 | ✅ A股完整 | ⚠️ 缺少港股美股实时 |
| 参考数据 | Phase 1 | ✅ 基础信息 | ✅ 较完整 |
| 另类数据 | Phase 3 | ❌ 未实现 | ❌ 完全缺失 |

---

## 三、关键问题清单

### 🔴 P0-紧急问题

1. **日K历史数据不足**
   - 现状: `stock_daily` 表仅5条数据
   - 影响: 无法计算技术指标、历史回测
   - 整改: 灵犀同步日K数据到 `stock_daily`

2. **品牌名不统一**
   - 现状: ministone / MiniRock / 灵犀 混用
   - 影响: 用户体验混乱
   - 整改: 统一为 "MiniRock"

3. **多版本主页并存**
   - 现状: 3个主页版本
   - 影响: 维护困难
   - 整改: 保留一个，删除其他

### 🟡 P1-高优先级

4. **缺少风险计算引擎**
   - VaR、夏普比率、最大回撤等未实现
   - 整改: 开发风险指标计算模块

5. **缺少绩效归因**
   - Brinson归因、因子归因未实现
   - 整改: 开发归因分析API和页面

6. **资产配置优化器缺失**
   - 马科维茨、风险平价模型未实现
   - 整改: 开发优化器API

7. **情景模拟/压力测试前端缺失**
   - 有API但无前端页面
   - 整改: 开发情景模拟页面

### 🟢 P2-中优先级

8. **港股美股数据接入**
   - 仅A股完整，港股美股仅占位
   - 整改: 接入雅虎财经或同花顺API

9. **用户数据表扩展**
   - 缺少: 交易记录、组合历史、风险偏好问卷
   - 整改: 扩展PostgreSQL表结构

10. **实时行情推送**
    - 当前轮询，无WebSocket
    - 整改: 接入WebSocket行情

---

## 四、架构整改建议

### 4.1 数据层优化

```
当前架构:               建议架构:
┌─────────────┐        ┌─────────────┬─────────────┐
│   SQLite    │        │   SQLite    │  PostgreSQL │
│  (所有数据)  │   →    │  (市场数据)  │  (用户数据) │
├─────────────┤        ├─────────────┼─────────────┤
│ stocks      │        │ stocks      │ users       │
│ stock_quotes│        │ stock_quotes│ holdings    │
│ stock_daily │        │ stock_daily │ portfolios  │
│ index_quotes│        │ index_quotes│ transactions│ ←新增
│ news        │        │ news        │ risk_profiles│ ←新增
└─────────────┘        └─────────────┴─────────────┘
```

**建议新增表**:
1. `transactions` - 交易记录
2. `portfolio_history` - 组合历史净值
3. `risk_profiles` - 用户风险偏好
4. `alerts` - 预警记录

### 4.2 计算层优化

当前: 所有计算在API层同步完成
建议: 复杂计算异步化

```
API层 → 任务队列(Redis/Celery) → 计算节点 → 结果缓存
```

**需要异步化的计算**:
- VaR风险价值
- 组合优化
- 压力测试
- 绩效归因

### 4.3 前端架构优化

**页面合并计划**:
- 删除: `index.html`, `minirock.html`
- 保留: `minirock-v2.html` (作为主入口)
- 重命名: `minirock-auth.html` → `auth.html`

**新增页面**:
- `risk-center.html` - 风险监控中心
- `scenario-lab.html` - 情景模拟实验室
- `allocation-optimizer.html` - 资产配置优化器
- `performance-attribution.html` - 绩效归因分析

---

## 五、整改优先级排序

### Phase 1 (1-2周): 基础整改
1. ✅ 数据层分离 (已完成)
2. 🔴 统一品牌名
3. 🔴 清理多版本页面
4. 🔴 同步日K历史数据

### Phase 2 (1个月): 核心功能
5. 🟡 开发风险指标计算引擎
6. 🟡 实现绩效归因API
7. 🟡 开发情景模拟前端

### Phase 3 (2个月): 专业功能
8. 🟢 开发资产配置优化器
9. 🟢 接入港股美股数据
10. 🟢 实现压力测试引擎

### Phase 4 (3个月+): 生态建设
11. 开放API平台
12. 多资产类别支持
13. 机构级功能

---

## 六、验收标准

### 当前已完成的整改
- ✅ 个股/指数数据分离
- ✅ 测试/生产环境隔离
- ✅ API基础功能完整

### 待验收的整改
- [ ] 日K历史数据 > 1000条/股
- [ ] 品牌名100%统一
- [ ] 风险指标计算准确
- [ ] 情景模拟可交互
- [ ] 资产配置优化器可用

---

**报告完成**  
**建议下一步**: 开始Phase 1基础整改（品牌统一、页面清理、日K数据同步）
