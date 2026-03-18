# MiniRock 修复任务单 (合并版)

**生成时间**: 2026-03-16  
**基于测试报告**: 
- Phase 2 v2.3 (2026-03-15 后端修复后)
- 2026-03-16 浏览器全流程测试

---

## 🔴 后端任务 (@方舟)

### P0 - 阻塞性问题（需立即修复）

| 编号 | 任务 | 问题描述 | 验收标准 |
|------|------|----------|----------|
| BE-001 | 修复 `/api/stock/basic/{code}` | 500 错误，数据库查询异常 | GET 请求返回 200，包含股票基础信息 |
| BE-002 | 修复 `/api/stock/kline/{code}` | 500 错误，stock_daily 表不存在 | GET 请求返回 200，包含K线数据 |
| BE-003 | 修复 `/api/stock/capital/{code}` | 500 错误，stock_hsgt_hold 表不存在 | GET 请求返回 200，包含资金面数据 |
| BE-004 | 修复用户认证系统 | users 表缺少 user_id 字段导致注册/登录失败 | 注册/登录 API 返回 200，正常创建用户 |

### P1 - 高优先级

| 编号 | 任务 | 问题描述 | 验收标准 |
|------|------|----------|----------|
| BE-005 | 创建 stock_daily 表 | K线数据表缺失 | 表结构正确，能存储日K数据 |
| BE-006 | 创建 stock_hsgt_hold 表 | 北向资金表缺失 | 表结构正确，能存储北向持仓 |
| BE-007 | 补充 stock_basic 表数据 | 股票基础信息表为空 | 至少包含沪深300成分股数据 |
| BE-008 | 修复情景推演 current_price | API 返回 current_price=0 | 返回正确的当前价格 |

### P2 - 中优先级

| 编号 | 任务 | 问题描述 | 验收标准 |
|------|------|----------|----------|
| BE-009 | 添加持仓 API 端点 | `/api/portfolio/add` 返回 404 | 能正常添加持仓到用户账户 |
| BE-010 | 数据库连接池优化 | 高并发下连接数耗尽 | 支持 50+ 并发连接 |

### 技术参考
```
后端路径: /var/www/familystock/api/app/routers/
数据库: PostgreSQL (host: localhost, db: minirock)
```

---

## 🟡 前端任务 (@玲珑)

### P0 - 阻塞性问题

| 编号 | 任务 | 问题描述 | 验收标准 |
|------|------|----------|----------|
| FE-001 | 个股详情页 loading 状态优化 | 股票数据 500 错误时无限转圈 | API 错误时显示友好提示，允许重试 |
| FE-002 | 登录/注册失败提示 | 只显示"登录失败"/"注册失败" | 显示具体错误原因（网络/账号/密码） |

### P1 - 高优先级

| 编号 | 任务 | 问题描述 | 验收标准 |
|------|------|----------|----------|
| FE-003 | 添加持仓失败处理 | API 404 时无错误提示 | 显示错误提示，引导用户登录 |
| FE-004 | 组合分析页 loading 优化 | 数据加载中无超时处理 | 添加 10s 超时，显示"数据加载失败" |
| FE-005 | 股票搜索无结果提示 | 搜索"茅台"返回"未找到该股票" | 检查搜索逻辑，确保中文名称可搜索 |
| FE-006 | 持仓区域状态同步 | 未登录时显示"暂无持仓" | 未登录时显示"请登录后查看持仓" |

### P2 - 中优先级

| 编号 | 任务 | 问题描述 | 验收标准 |
|------|------|----------|----------|
| FE-007 | 添加"忘记密码"入口 | 目前无密码找回功能 | 登录页显示"忘记密码"链接 |
| FE-008 | 注册表单增加姓名字段 | 目前只收集手机号+密码 | 添加姓名输入框，注册时提交 |
| FE-009 | 行情页风险提示持久化 | 每次刷新都弹出风险提示 | 使用 localStorage 记录已同意状态 |

### 文件位置
```
前端路径: /var/www/familystock/frontend/
主要文件:
- minirock-v2.html (首页/持仓)
- minirock-auth.html (登录/注册)
- stock-detail.html (个股详情)
- portfolio-analysis.html (组合分析)
- watchlist.html (自选股)
- market.html (行情)
```

---

## 📋 数据库修复脚本 (供 BE 参考)

### 1. 修复 users 表结构
```sql
-- 检查现有 users 表结构
\d users

-- 如果缺少 phone 字段，需要重建表
DROP TABLE IF EXISTS users CASCADE;
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name VARCHAR(100) DEFAULT '投资者',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 插入测试账号
INSERT INTO users (phone, password_hash, name) VALUES 
('13900139000', 'Test123456', '测试用户');
```

### 2. 创建缺失的股票数据表
```sql
-- K线数据表
CREATE TABLE IF NOT EXISTS stock_daily (
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    open DECIMAL(10,2),
    high DECIMAL(10,2),
    low DECIMAL(10,2),
    close DECIMAL(10,2),
    volume BIGINT,
    UNIQUE(ts_code, trade_date)
);

-- 北向资金表
CREATE TABLE IF NOT EXISTS stock_hsgt_hold (
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL,
    trade_date DATE NOT NULL,
    hold_amount BIGINT,
    hold_ratio DECIMAL(5,2),
    UNIQUE(ts_code, trade_date)
);

-- 股票基础信息表
CREATE TABLE IF NOT EXISTS stock_basic (
    id SERIAL PRIMARY KEY,
    ts_code VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100),
    industry VARCHAR(50),
    market VARCHAR(10)
);
```

### 3. 初始化基础数据
```sql
-- 插入平安银行测试数据
INSERT INTO stock_basic (ts_code, name, industry, market) VALUES
('000001.SZ', '平安银行', '银行', 'SZ'),
('600519.SH', '贵州茅台', '白酒', 'SH'),
('000858.SZ', '五粮液', '白酒', 'SZ')
ON CONFLICT (ts_code) DO NOTHING;
```

---

## ✅ 修复后验证清单

### 后端验证 (@方舟)
- [ ] `curl http://localhost:8000/api/stock/basic/000001.SZ` → 200
- [ ] `curl http://localhost:8000/api/stock/kline/000001.SZ` → 200
- [ ] `curl http://localhost:8000/api/stock/capital/000001.SZ` → 200
- [ ] 注册新用户成功 → 200
- [ ] 登录成功 → 返回 token

### 前端验证 (@玲珑)
- [ ] 个股详情页正常加载，不转圈
- [ ] 登录/注册显示具体错误信息
- [ ] 添加持仓有明确的登录引导
- [ ] 股票搜索支持中文名称

### 全流程验证 (@小七)
- [ ] 注册 → 登录 → 添加自选股 → 查看详情 → 组合分析

---

## 📞 协作说明

1. **后端优先修复 BE-001~BE-004**，这是前端功能正常的前提
2. **前端可先修复 FE-002/FE-003**（错误提示优化），不依赖后端
3. **每日同步**：修复完成后在群里 @小七 进行验证测试

**测试环境**: http://43.160.193.165/  
**测试账号**: 13900139000 / Test123456  
**API文档**: http://43.160.193.165:8006/docs
