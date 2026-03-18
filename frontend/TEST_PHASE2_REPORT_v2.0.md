# MiniRock Phase 2 前端测试报告（重跑）

**测试时间**: 2026-03-15  
**测试工程师**: 小七 (灵犀)  
**测试范围**: TC-AI-001 ~ TC-AI-005 (AI个股诊断、组合分析、情景推演、新闻关联、API测试)  
**测试环境**: http://43.160.193.165/frontend/

---

## 执行摘要

本次重跑测试发现 **5 个 Bug**（2 个 P0 阻塞级）。主要问题集中在：
1. 后端路由配置遗漏（`stock_detail` 未注册）
2. 前端 API 路径前缀不匹配
3. 情景推演 API 数据异常（current_price=0）

---

## 详细测试结果

### TC-AI-001: AI 个股诊断页面
**状态**: ❌ **失败（P0/阻塞）**

**测试步骤**:
1. 访问 `stock-detail.html?code=000001.SZ`
2. 页面加载后重定向到登录页
3. 需登录后才能访问个股详情

**发现的问题**:
- **AI-BUG-005 (P0)**: `stock_detail` 路由未在 `main.py` 中注册
  - 后端代码存在 `/stock/basic/{ts_code}` 等路由
  - 但 `main.py` 未 `include_router(stock_detail.router_stock_detail)`
  - 导致所有 `/stock/*` API 返回 404
  
- **AI-BUG-006 (P1)**: 前端 API 路径前缀不匹配
  - 前端配置: `baseURL: '/api'`
  - 后端路由: `/stock/*`, `/ai/*`, `/portfolio/*`（无 `/api` 前缀）
  - 仅 `/api/ai/*` 和 `/api/portfolio/*` 有 `/api` 前缀

**期望结果**: 页面正常加载股票详情  
**实际结果**: 页面重定向到登录页，API 404

---

### TC-AI-002: 组合分析页面
**状态**: ⚠️ **部分通过**

**测试步骤**:
1. 测试 `/portfolio/holdings` API

**验证结果**:
```json
{
  "user_id": "demo_user",
  "holdings": [{
    "symbol": "600519",
    "name": "贵州茅台",
    "quantity": 100,
    "current_price": 1413.64,
    "profit_percent": -5.76,
    "health_score": 55
  }],
  "total_value": 141364.0,
  "health_score": 45
}
```

**问题**:
- AI-BUG-002 (P1): demo_user 持仓数据已存在 ✅ **已修复**

---

### TC-AI-003: 情景推演
**状态**: ⚠️ **部分通过**

**API 测试**:
```bash
curl 'http://localhost:8000/ai/scenario/000001.SZ?scenario=bullish&magnitude=5'
```

**返回结果**:
```json
{
  "symbol": "000001.SZ",
  "name": "",
  "current_price": 0.0,  // ❌ 异常
  "scenarios": {
    "optimistic": {"change_percent": 15, "projected_price": 0.0},
    "neutral": {"change_percent": 5, "projected_price": 0.0},
    "pessimistic": {"change_percent": -15, "projected_price": 0.0}
  }
}
```

**问题**:
- **AI-BUG-003 (P2)**: `current_price=0`, `name=""`, `projected_price=0`
- 情景数据已返回，但缺少基础股票数据

---

### TC-AI-004: 新闻关联
**状态**: ⏸️ **未执行**

**阻塞原因**: 依赖 TC-AI-001 修复（需要股票详情页面加载）

**注意前端代码问题**: 
```javascript
// stock-detail.html 第 565 行
const response = await fetch(`${API_CONFIG.baseURL}/api/ai/news-related/...`);
// 结果: /api/api/ai/news-related/ (重复 /api)
```

---

### TC-AI-005: API 接口测试
**状态**: ⚠️ **部分通过（4/5）**

| API 端点 | 方法 | 状态 | 响应时间 | 备注 |
|----------|------|------|----------|------|
| `/portfolio/holdings` | GET | ✅ 正常 | <100ms | 数据完整 |
| `/tushare/quote/{code}` | GET | ✅ 正常 | <500ms | 行情数据正常 |
| `/ai/analyze-stock` | POST | ✅ 正常 | ~15s | Kimi分析成功 |
| `/ai/scenario/{code}` | GET | ⚠️ 部分 | <1s | current_price=0 |
| `/stock/basic/{code}` | GET | ❌ 404 | N/A | 路由未注册 |

**AI 分析 API 响应示例**:
```json
{
  "symbol": "000001.SZ",
  "name": "平安银行",
  "analysis": "**【技术面分析】**...",
  "summary": "**【技术面分析】**...",
  "related_news": [...]
}
```

---

## Bug 汇总

| 编号 | 优先级 | 模块 | 问题描述 | 修复建议 |
|------|--------|------|----------|----------|
| AI-BUG-005 | **P0** | 后端 | `stock_detail` 路由未在 `main.py` 注册 | 添加 `include_router(stock_detail.router_stock_detail)` |
| AI-BUG-006 | **P1** | 前端 | API 路径前缀不匹配 | 统一前端 `baseURL` 或后端路由前缀 |
| AI-BUG-003 | P2 | 后端 | 情景推演 `current_price=0` | 补充股票基础数据查询 |
| AI-BUG-007 | P2 | 前端 | `/api/api/ai/news-related` 重复路径 | 修复为 `/api/ai/news-related` |

---

## 修复建议

### 后端修复 (灵犀)

**1. 修复路由注册** (`/var/www/familystock/api/app/main.py`):
```python
from app.routers import stock_detail  # 添加导入

app.include_router(stock_detail.router_stock_detail)  # 添加注册
```

**2. 修复情景推演数据** (`/var/www/familystock/api/app/routers/ai_analysis.py`):
- 补充 `current_price` 和 `name` 字段查询逻辑

### 前端修复 (玲珑)

**1. 统一 API 路径** (`stock-detail.html`):
```javascript
// 当前配置
const API_CONFIG = { baseURL: '/api', timeout: 10000 };

// 建议修改为与后端匹配
const API_CONFIG = { baseURL: '', timeout: 10000 };
// 或后端统一添加 /api 前缀
```

**2. 修复重复路径** (第 565 行):
```javascript
// 修复前
`${API_CONFIG.baseURL}/api/ai/news-related/`

// 修复后
`${API_CONFIG.baseURL}/ai/news-related/`
```

---

## 待验证项

修复后需要重新测试：
- [ ] TC-AI-001 个股诊断页面加载
- [ ] TC-AI-003 情景推演功能
- [ ] TC-AI-004 新闻关联功能
- [ ] 性能测试 (API <1秒, 页面 <2秒)

---

## 附录

### 测试命令

```bash
# 持仓查询
curl http://localhost:8000/portfolio/holdings

# 股票行情
curl http://localhost:8000/tushare/quote/000001.SZ

# AI分析
curl -X POST http://localhost:8000/ai/analyze-stock \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"000001.SZ","name":"平安银行","current_price":10.76,"avg_cost":10.50,"quantity":100,"change_percent":-0.55,"profit_percent":2.48,"market":"A股"}'

# 情景推演
curl 'http://localhost:8000/ai/scenario/000001.SZ?scenario=bullish&magnitude=5'
```

### 文件位置

- 后端主文件: `/var/www/familystock/api/app/main.py`
- 前端文件: `/var/www/familystock/frontend/stock-detail.html`
- AI路由: `/var/www/familystock/api/app/routers/ai_analysis.py`
- 个股路由: `/var/www/familystock/api/app/routers/stock_detail.py`

---

*报告生成时间: 2026-03-15 20:15*
