# MiniRock主站回归测试报告
**时间**: 2026-04-21 17:49-17:55 (北京时间)
**测试人**: 灵犀
**状态**: ⚠️ 部分异常

---

## 一、AI股神争霸 ✅

| 检查项 | 结果 |
|--------|------|
| 后端服务 (18085) | ✅ 运行中 |
| AI Characters API | ✅ 10个AI正常 |
| Rankings API | ✅ 排行榜正常 |
| Posts API | ✅ 帖子正常（最新17:46） |
| Nginx代理 | ✅ 正常 |

**最新帖子时间**: 2026-04-21 17:46:47

---

## 二、MiniRock主站

### ✅ 正常功能

| 功能 | API端点 | 结果 |
|------|---------|------|
| 个股分析 | `POST /api/ymos/stock/analyze` | ✅ 正常（返回评分39分/卖出） |
| 市场分析 | `GET /api/ymos/market/analysis` | ✅ 正常（情绪46中性偏谨慎） |
| 市场情绪 | `GET /api/ymos/eyes/market/sentiment` | ✅ 正常 |
| 添加个股 | `POST /api/watchlist/` | ✅ 成功 |
| 自选股列表 | `GET /api/watchlist/` | ✅ 正常 |
| 北向资金 | `GET /api/northbound/flow` | ✅ 有数据(20260420) |

### ⚠️ 有问题的功能

| 功能 | API端点 | 问题 |
|------|---------|------|
| **持仓分析** | `POST /api/ai/analyze-portfolio` | ⚠️ 接口存在但需要特定参数(holdings/total_value/total_profit) |
| **AI排行榜** | `GET /api/ai/rankings` | ❌ 数据库错误：`column p.total_return does not exist` |

### ⚠️ 数据过期问题

| 数据项 | 最新日期 | 天数 |
|--------|----------|------|
| YMOS市场缓存 | 2026-04-19 | 2天前 |
| YMOS个股缓存 | 2026-04-19 | 2天前 |

---

## 三、待修复问题

1. **AI排行榜数据库结构错误**
   - 错误: `column p.total_return does not exist`
   - 需要检查ai_god.db的表结构

2. **YMOS缓存数据过期**
   - 市场缓存2天未更新
   - 需要检查定时更新任务是否正常

---

*报告生成时间: 2026-04-21T09:55:00Z*
