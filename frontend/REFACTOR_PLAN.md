# MiniRock 前端重构计划

**制定日期**: 2026-03-10  
**负责人**: 玲珑 & 灵犀  
**目标**: 将单体 HTML 重构为模块化、可维护的现代前端架构

---

## 📊 现状分析

### 当前问题

| 问题 | 影响 | 优先级 |
|------|------|--------|
| **单体文件** | minirock.html 1500+行，HTML/CSS/JS混杂 | P0 |
| **API混乱** | 8080端口和8006端口混用，路径不统一 | P0 |
| **无模块化** | 全局变量污染，代码难以复用 | P1 |
| **假数据残留** | _getMockData() 函数仍存在于部分代码 | P1 |
| **硬编码配置** | API地址、Token等分散在各文件中 | P1 |

### 当前文件结构

```
/var/www/familystock/frontend/
├── minirock.html              # 1500+行单体文件 ⚠️
├── minirock-stock-service.js  # 股票数据服务
├── minirock-ai-service.js     # AI分析服务
├── minirock-ai-analysis.js    # AI分析详细逻辑
├── minirock-alert-system.js   # 预警系统
├── stock_database.js          # 股票数据库（7368只）
└── stock_database_full.js     # 完整数据库
```

---

## 🎯 重构目标

1. **模块化架构** - 按功能拆分为独立模块
2. **统一API层** - 所有请求通过统一的 API client
3. **配置集中化** - API地址、密钥等配置统一管理
4. **移除假数据** - 彻底清理所有 mock 逻辑
5. **代码可测试** - 支持单元测试

---

## 📐 新架构设计

### 目录结构

```
/var/www/familystock/frontend/
├── index.html                 # 入口 HTML（精简版）
├── src/
│   ├── config/
│   │   └── index.js          # 全局配置（API地址、Token等）
│   ├── api/
│   │   ├── client.js         # 统一 API client
│   │   ├── stock.js          # 股票相关 API
│   │   ├── ai.js             # AI分析 API
│   │   └── news.js           # 新闻 API
│   ├── services/
│   │   ├── stockService.js   # 股票数据服务
│   │   ├── aiService.js      # AI分析服务
│   │   ├── alertService.js   # 预警服务
│   │   └── storageService.js # 本地存储服务
│   ├── components/
│   │   ├── StockCard.js      # 股票卡片组件
│   │   ├── AIReport.js       # AI报告组件
│   │   ├── AlertPanel.js     # 预警面板组件
│   │   ├── SearchBox.js      # 搜索框组件
│   │   └── Navigation.js     # 导航组件
│   ├── utils/
│   │   ├── formatters.js     # 格式化工具
│   │   ├── validators.js     # 验证工具
│   │   └── helpers.js        # 辅助函数
│   ├── styles/
│   │   ├── variables.css     # CSS变量
│   │   ├── components.css    # 组件样式
│   │   └── pages.css         # 页面样式
│   └── app.js                # 应用入口
├── assets/
│   ├── images/
│   └── icons/
└── data/
    └── stock_database.js     # 股票数据库
```

---

## 📝 重构任务清单

### Phase 1: 基础设施 (Day 1)

| # | 任务 | 负责人 | 验收标准 |
|---|------|--------|----------|
| 1.1 | 创建新目录结构 | 玲珑 | `src/` 目录创建完成 |
| 1.2 | 提取全局配置 | 玲珑 | `config/index.js` 包含所有配置项 |
| 1.3 | 创建统一 API Client | 玲珑 | 支持拦截器、错误处理 |
| 1.4 | 备份原文件 | 玲珑 | 所有原文件 `.bak` 备份 |

### Phase 2: API 层重构 (Day 1-2)

| # | 任务 | 负责人 | 验收标准 |
|---|------|--------|----------|
| 2.1 | 统一 API 路径 | 玲珑 | 所有请求使用 `localhost:8006/api` |
| 2.2 | 创建 stock.js API | 玲珑 | 封装 `/tushare/*` 接口 |
| 2.3 | 创建 ai.js API | 玲珑 | 封装 AI 分析接口 |
| 2.4 | 移除假数据逻辑 | 玲珑 | 删除所有 `_getMockData` 函数 |

### Phase 3: 服务层重构 (Day 2)

| # | 任务 | 负责人 | 验收标准 |
|---|------|--------|----------|
| 3.1 | 重构 stockService | 灵犀 | 使用新 API client |
| 3.2 | 重构 aiService | 灵犀 | 使用新 API client |
| 3.3 | 重构 alertService | 灵犀 | 使用新 API client |
| 3.4 | 创建 storageService | 灵犀 | 封装 localStorage 操作 |

### Phase 4: 组件层重构 (Day 3)

| # | 任务 | 负责人 | 验收标准 |
|---|------|--------|----------|
| 4.1 | 创建 StockCard 组件 | 灵犀 | 可复用的股票卡片 |
| 4.2 | 创建 SearchBox 组件 | 灵犀 | 搜索功能封装 |
| 4.3 | 创建 AIReport 组件 | 灵犀 | AI报告展示 |
| 4.4 | 创建 AlertPanel 组件 | 灵犀 | 预警面板 |

### Phase 5: 样式重构 (Day 3-4)

| # | 任务 | 负责人 | 验收标准 |
|---|------|--------|----------|
| 5.1 | 提取 CSS 变量 | 灵犀 | `variables.css` 包含主题色 |
| 5.2 | 重构组件样式 | 灵犀 | 使用 BEM 命名规范 |
| 5.3 | 移动端适配 | 灵犀 | 响应式布局完成 |

### Phase 6: 整合与测试 (Day 4)

| # | 任务 | 负责人 | 验收标准 |
|---|------|--------|----------|
| 6.1 | 创建新的入口文件 | 玲珑 | `app.js` 初始化完成 |
| 6.2 | 精简 index.html | 玲珑 | HTML 只包含基础结构 |
| 6.3 | 功能测试 | 灵犀 | 所有功能正常工作 |
| 6.4 | 部署到测试环境 | 玲珑 | 新加坡服务器可访问 |

---

## 🔧 API 路径对照表

| 功能 | 旧路径 | 新路径 | 状态 |
|------|--------|--------|------|
| 单只股票 | `:8080/api/v3/tushare/quote/:code` | `:8006/api/tushare/quote/:code` | 需统一 |
| 批量查询 | `:8080/api/v3/tushare/batch` | `:8006/api/tushare/batch` | 需统一 |
| 股票搜索 | `:8080/api/v3/tushare/search` | `:8006/api/tushare/search` | 需统一 |
| AI分析 | `:8080/api/v3/ai/analyze` | `:8006/api/ai/analyze` | 需创建 |

**注意**: 后端 API 服务在端口 8006，所有前端请求必须指向此端口。

---

## ⚙️ 配置项说明

### config/index.js 结构

```javascript
export const CONFIG = {
  // API 配置
  API: {
    BASE_URL: 'http://43.160.193.165:8006/api',
    TIMEOUT: 10000,
    RETRY_COUNT: 3
  },
  
  // Tushare 配置
  TUSHARE: {
    TOKEN: 'f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735'
  },
  
  // 应用配置
  APP: {
    NAME: 'MiniRock',
    VERSION: '2.0.0',
    UPDATE_INTERVAL: 30000  // 30秒刷新
  },
  
  // 预警配置
  ALERT: {
    CHECK_INTERVAL: 60000,   // 1分钟检查一次
    COOLDOWN: 300000,        // 5分钟冷却
    PRICE_DROP: -10,         // 跌幅10%预警
    PRICE_RISE: 20           // 涨幅20%预警
  }
};
```

---

## 🔄 开发工作流程

```
1. 本地开发 (KimiClaw)
   ↓
2. 本地测试 http://localhost:8000
   ↓
3. 提交到 Git
   ↓
4. 同步到 TenClaw
   ↓
5. 生产环境测试 http://43.160.193.165/minirock.html
   ↓
6. 全量验证
```

### 关键命令

```bash
# 本地启动测试服务器
cd /var/www/familystock/frontend && python3 -m http.server 8000

# 同步到新加坡服务器
scp -i ~/.ssh/tenclaw_key -r src/ root@43.160.193.165:/var/www/familystock/frontend/

# 备份原文件
cp minirock.html minirock.html.bak.$(date +%Y%m%d_%H%M%S)
```

---

## ⚠️ 风险与回滚

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 重构引入 Bug | 高 | 每阶段完成后立即测试 |
| API 路径错误 | 高 | 统一配置文件，全局搜索验证 |
| 功能缺失 | 中 | 对照原文件功能清单逐一验证 |
| 部署失败 | 中 | 保留原文件备份，随时可回滚 |

**回滚方案**:
```bash
# 紧急回滚
mv minirock.html.new minirock.html.rework
mv minirock.html.bak.20260310_083000 minirock.html
```

---

## 📅 时间计划

| 阶段 | 预计时间 | 交付物 |
|------|----------|--------|
| Phase 1 | 0.5天 | 目录结构、配置文件 |
| Phase 2 | 1天 | API层完成 |
| Phase 3 | 1天 | 服务层完成 |
| Phase 4 | 1天 | 组件层完成 |
| Phase 5 | 1天 | 样式重构完成 |
| Phase 6 | 0.5天 | 整合测试、部署 |
| **总计** | **5天** | **v2.0 重构版** |

---

## ✅ 验收标准

重构完成需满足以下条件：

1. ✅ 所有功能与原版本一致
2. ✅ 代码行数减少 30% 以上（去除重复代码）
3. ✅ 无假数据残留
4. ✅ API 路径统一
5. ✅ 移动端适配正常
6. ✅ 加载速度提升（按需加载）
7. ✅ 通过功能测试清单

---

**文档版本**: v1.0  
**最后更新**: 2026-03-10 08:45  
**状态**: 🚧 计划中
