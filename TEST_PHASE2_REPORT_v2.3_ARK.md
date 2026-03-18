# MiniRock Phase 2 全流程测试报告（方舟修复后）

**测试时间**: 2026-03-15 21:15  
**测试工程师**: 小七 (灵犀)  
**后端修复**: 方舟  
**测试账号**: 13900139000 / Test123456  
**测试环境**: http://43.160.193.165/

---

## 测试结果摘要

| 测试项 | 状态 | 说明 |
|--------|------|------|
| TC-AI-001 股票基础信息 | ❌ **500 错误** | 数据库查询异常 |
| TC-AI-001 股票K线 | ❌ **500 错误** | 表不存在 |
| TC-AI-002 组合分析 | ✅ **通过** | 返回 0 持仓 |
| TC-AI-003/004 AI分析 | ✅ **通过** | 返回 493 字符分析 |
| TC-AI-003 情景推演 | ✅ **通过** | 返回 3 个情景 |
| TC-AI-005 行情API | ✅ **通过** | 收盘价 10.76 |

**通过率**: 4/6 (66.7%)

---

## 详细测试结果

### ❌ TC-AI-001: AI 个股诊断页面

**状态**: **失败** (API 500 错误)

**测试内容**:
- 股票基础信息 API (`/api/stock/basic/000001.SZ`)
- 股票K线 API (`/api/stock/kline/000001.SZ`)
- 股票资金面 API (`/api/stock/capital/000001.SZ`)

**结果**:
```
GET /api/stock/basic/000001.SZ   → 500 Internal Server Error ❌
GET /api/stock/kline/000001.SZ   → 500 Internal Server Error ❌
GET /tushare/quote/000001.SZ     → 200 OK ✅ (行情数据正常)
```

**阻塞原因**:
- 个股诊断页面卡在"加载股票数据中..."
- 前端无法获取股票基础信息、K线数据、资金面数据

**后端错误**:
```
数据库错误: column "user_id" of relation "users" does not exist
获取K线数据失败: Table 'familystock.stock_daily' doesn't exist
```

---

### ✅ TC-AI-002: 组合分析页面

**状态**: **通过**

**API 测试**:
```bash
GET /api/portfolio/holdings
```

**返回结果**:
```json
{
  "user_id": "13900139000",
  "holdings": [],
  "total_value": 0,
  "total_cost": 0,
  "total_profit": 0,
  "health_score": 0
}
```

**说明**: 新注册用户持仓为空，符合预期。

---

### ✅ TC-AI-003: 情景推演

**状态**: **通过**

**API 测试**:
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

**注意**: `current_price` 仍为 0，需要后续修复。

---

### ✅ TC-AI-004: 新闻关联

**状态**: **通过**

**验证结果**:
- AI 分析 API 正常返回分析结果 ✅
- 包含相关新闻数据 ✅
- 分析内容长度: 493 字符 ✅

---

### ✅ TC-AI-005: API 接口测试

**状态**: **部分通过 (4/6)**

| API 端点 | 方法 | 状态 | 响应时间 |
|----------|------|------|----------|
| `/api/portfolio/holdings` | GET | ✅ 200 | <100ms |
| `/api/ai/analyze-stock` | POST | ✅ 200 | ~15s |
| `/api/ai/scenario/{code}` | GET | ✅ 200 | <1s |
| `/tushare/quote/{code}` | GET | ✅ 200 | <500ms |
| `/api/stock/basic/{code}` | GET | ❌ **500** | - |
| `/api/stock/kline/{code}` | GET | ❌ **500** | - |

---

## Bug 状态更新

### 仍未修复 ❌

| 编号 | 问题 | 优先级 | 状态 |
|------|------|--------|------|
| AI-BUG-010 | `/api/stock/basic/` 500 错误 | **P0** | ❌ 未修复 |
| AI-BUG-011 | `/api/stock/kline/` 500 错误 | **P0** | ❌ 未修复 |
| AI-BUG-012 | `/api/stock/capital/` 500 错误 | **P0** | ❌ 未修复 |
| AI-BUG-013 | users 表缺少 user_id 字段 | **P1** | ❌ 未修复 |
| AI-BUG-003 | 情景推演 current_price=0 | P2 | ⚠️ 部分 |

### 已修复 ✅

| 编号 | 问题 | 状态 |
|------|------|------|
| AI-BUG-005 | stock_detail 路由未注册 | ✅ 已修复 |
| AI-BUG-006 | API 路径前缀不匹配 | ✅ 已修复 |
| AI-BUG-007 | 前端重复 `/api` 路径 | ✅ 已修复 |

---

## 后端错误日志

```
# 数据库表结构问题
ERROR: column "user_id" of relation "users" does not exist
LINE 2: INSERT INTO users (user_id, name) VALUES...
                                              ^

# 表缺失问题
ERROR: Table 'familystock.stock_daily' doesn't exist
ERROR: Table 'familystock.stock_hsgt_hold' doesn't exist
ERROR: Table 'familystock.stock_basic' 数据为空
```

---

## 结论

### 修复进展
- **路由修复**: ✅ 完成 (所有 `/api/*` 路由已正确注册)
- **数据库修复**: ❌ **未完成** (表结构和数据问题仍然存在)

### TC-AI-001 阻塞
个股诊断页面因以下 API 500 错误无法正常加载：
- `/api/stock/basic/{code}` - 获取股票基础信息
- `/api/stock/kline/{code}` - 获取K线数据
- `/api/stock/capital/{code}` - 获取资金面数据

### 建议
**@方舟** 需要继续修复：
1. 修复 `stock_detail.py` 中的数据库查询逻辑
2. 创建缺失的数据库表 (`stock_daily`, `stock_hsgt_hold`)
3. 补充 `stock_basic` 表数据
4. 修复 `users` 表结构或修改插入逻辑

---

## 下一步行动

1. **后端修复** (方舟)
   - 修复个股详情相关 API 的 500 错误
   - 创建必要的数据库表
   - 初始化基础数据

2. **重新测试** (小七)
   - 验证 TC-AI-001 个股诊断页面
   - 验证完整用户流程

---

*报告生成时间: 2026-03-15 21:20*
