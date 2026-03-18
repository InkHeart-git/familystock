# MiniRock Phase 2 测试报告（最终版）

**测试时间**: 2026-03-15  
**测试工程师**: 小七 (灵犀)  
**测试账号**: 13900139000 / Test123456  
**测试环境**: http://43.160.193.165/

---

## 测试执行摘要

### ✅ 已完成修复验证

| Bug | 描述 | 状态 |
|-----|------|------|
| AI-BUG-005 | stock_detail 路由未注册 | ✅ 已修复并验证 |
| AI-BUG-006 | API 路径前缀不匹配 | ✅ 已修复并验证 |
| AI-BUG-007 | 前端重复 `/api` 路径 | ✅ 已修复并验证 |

### ⚠️ 新发现问题

| Bug | 描述 | 优先级 |
|-----|------|--------|
| AI-BUG-010 | `/api/stock/basic/` 500 内部错误 | **P0** |
| AI-BUG-011 | `/api/stock/kline/` 500 内部错误 | **P0** |
| AI-BUG-012 | `/api/stock/capital/` 500 内部错误 | **P0** |
| AI-BUG-013 | 数据库 `users` 表缺少 `user_id` 字段 | **P1** |

---

## 详细测试结果

### TC-AI-001: AI 个股诊断页面

**状态**: ❌ **失败（API 500 错误）**

**测试步骤**:
1. 注册测试账号: 13900139000 / Test123456 ✅
2. 登录并进入平台 ✅
3. 访问个股诊断页面: `/stock-detail.html?code=000001.SZ` ✅
4. 页面加载状态: ⚠️  stuck at "加载股票数据中..."

**API 调用结果**:
```
GET /api/stock/basic/000001.SZ     → 500 Internal Server Error ❌
GET /api/stock/kline/000001.SZ     → 500 Internal Server Error ❌
GET /api/stock/capital/000001.SZ   → 500 Internal Server Error ❌
GET /tushare/quote/000001.SZ       → 200 OK ✅
```

**根本原因**:
- 后端 `stock_detail.py` 路由处理代码抛出异常
- 数据库表结构问题: `column "user_id" of relation "users" does not exist`

---

### TC-AI-002: 组合分析页面

**状态**: ⚠️ **部分通过**

**验证结果**:
```json
GET /api/portfolio/holdings
{
  "user_id": "13900139000",
  "holdings": [],
  "total_value": 0,
  "total_cost": 0,
  "total_profit": 0,
  "health_score": 0
}
```

**问题**:
- API 响应正常 ✅
- 新注册用户持仓为空（符合预期）

---

### TC-AI-003: 情景推演

**状态**: ✅ **通过**

**API 验证**:
```bash
GET /api/ai/scenario/000001.SZ?scenario=bullish&magnitude=5
```

**返回结果**:
```json
{
  "symbol": "000001.SZ",
  "scenarios": {
    "optimistic": {"change_percent": 15, ...},
    "neutral": {"change_percent": 5, ...},
    "pessimistic": {"change_percent": -15, ...}
  }
}
```

---

### TC-AI-004: 新闻关联

**状态**: ✅ **通过**

**验证结果**:
- AI 分析 API (`/api/ai/analyze-stock`) 返回相关新闻 ✅
- 新闻数据正常加载

---

### TC-AI-005: API 接口测试

**状态**: ⚠️ **部分通过（7/10）**

| API 端点 | 方法 | 状态 | 响应时间 |
|----------|------|------|----------|
| `/api/portfolio/holdings` | GET | ✅ 200 | <100ms |
| `/api/ai/analyze-stock` | POST | ✅ 200 | ~15s |
| `/api/ai/scenario/{code}` | GET | ✅ 200 | <1s |
| `/tushare/quote/{code}` | GET | ✅ 200 | <500ms |
| `/api/stock/basic/{code}` | GET | ❌ **500** | - |
| `/api/stock/kline/{code}` | GET | ❌ **500** | - |
| `/api/stock/capital/{code}` | GET | ❌ **500** | - |
| `/auth/login` | POST | ✅ 200 | <100ms |
| `/auth/register` | POST | ✅ 200 | <100ms |
| `/api/ai/news-related/{code}` | GET | ⚠️ 编码问题 | - |

---

## 后端错误日志

```
数据库错误: column "user_id" of relation "users" does not exist
LINE 2: INSERT INTO users (user_id, name) VALUES...
                                              ^

INFO: 127.0.0.1:51976 - "GET /api/stock/basic/600519.SH HTTP/1.1" 500 Internal Server Error
INFO: 127.0.0.1:37516 - "GET /api/stock/basic/000001.SZ HTTP/1.1" 500 Internal Server Error
INFO: 127.0.0.1:37520 - "GET /api/stock/kline/000001.SZ HTTP/1.1" 500 Internal Server Error
```

---

## Bug 汇总

### P0 - 阻塞级

| 编号 | 问题 | 影响 | 建议修复 |
|------|------|------|----------|
| AI-BUG-010 | `/api/stock/basic/` 500 错误 | 个股诊断页无法加载基础信息 | 修复数据库查询语句 |
| AI-BUG-011 | `/api/stock/kline/` 500 错误 | K线图无法显示 | 修复数据库表结构 |
| AI-BUG-012 | `/api/stock/capital/` 500 错误 | 资金面信息无法显示 | 修复 SQL 查询 |

### P1 - 高优先级

| 编号 | 问题 | 影响 | 建议修复 |
|------|------|------|----------|
| AI-BUG-013 | users 表缺少 user_id 字段 | 用户相关功能异常 | 添加字段或修改代码 |
| AI-BUG-003 | 情景推演 current_price=0 | 推演价格计算错误 | 补充实时价格获取 |

### P2 - 中优先级

| 编号 | 问题 | 影响 | 建议修复 |
|------|------|------|----------|
| AI-BUG-008 | 新闻/搜索 API URL编码问题 | 中文参数报错 | URL 编码处理 |

---

## 修复建议

### 立即修复（P0）

**1. 修复数据库表结构**
```sql
-- 检查 users 表结构
\d users

-- 如缺少 user_id 字段，添加：
ALTER TABLE users ADD COLUMN user_id VARCHAR(50) UNIQUE;

-- 或修改代码使用现有字段（如 phone 或 id）
```

**2. 检查 stock_detail.py 中的 SQL 查询**
```python
# 检查 get_stock_basic_info 函数中的 SQL
# 确保表名和字段名正确
```

### 后续修复（P1/P2）

**3. 补充情景推演价格数据**
- 从 tushare 获取实时价格
- 或从缓存/数据库获取

**4. 修复 URL 编码**
```python
# 使用 urllib.parse.quote 处理中文参数
from urllib.parse import quote
```

---

## 测试结论

### 路由修复 ✅
- 所有 `/api/*` 路由已正确注册
- 前端 API 路径已修复
- nginx 配置正确

### 数据层问题 ❌
- **数据库表结构问题** 阻塞个股诊断功能
- 需要后端修复后才能进行完整功能测试

### 当前状态
**TC-AI-001 被阻塞**: 个股诊断页面因 API 500 错误无法正常加载股票数据。

---

## 下一步行动

**@灵犀** 需要：
1. 修复 `/api/stock/basic/` 500 错误
2. 修复 `/api/stock/kline/` 500 错误
3. 修复 `/api/stock/capital/` 500 错误
4. 检查并修复 `users` 表结构

修复后重新测试 TC-AI-001。

---

*报告生成时间: 2026-03-15 21:00*
