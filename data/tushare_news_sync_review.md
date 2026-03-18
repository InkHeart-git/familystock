# Tushare 新闻同步方式审查

**审查时间**: 2026-03-16 08:23
**审查人**: 灵犀

---

## 当前实现方式

### 1. 主同步脚本: `sync_news.py`

#### 多数据源策略
脚本采用**三层冗余策略**获取新闻：

1. **QVeris（优先）**
   - 工具ID: `finnhub.market.news.list.v1`
   - Discovery ID: `5f4c4b41-589f-49aa-b312-33f06211d39f`
   - 参数: `{"category":"general"}`
   - 限制: 最多200条
   - API Key: `sk-3JgIUg70yvI2zvedHKUqWy4BRNRN_XCsPsMqhiWQjiw`

2. **Tushare Pro（主要）**
   - Token: `f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735`
   - 时间范围: 昨日 00:00:00 - 今日 23:59:59
   - 限制: 最多1000条
   - ⚠️ **权限限制**: 每天最多调用2次

3. **东方财富网（备用）**
   - URL: `https://finance.eastmoney.com/news/cgjxw.html`
   - 触发条件: 总新闻数 < 50 时启用
   - 限制: 最多50条
   - 方式: HTML 解析 + 网页抓取

#### 数据处理流程
```
多数据源聚合 → 标题去重 → 数据库批量插入
```

---

### 2. 全市场同步脚本: `sync_all_markets.py`

#### 同步逻辑
```python
df = pro.news(
    start_time=start_date,  # 默认昨日
    end_time=end_date,      # 默认今日
    limit=500
)
```

#### 定时任务
- **频率**: 每天 01:00
- **Cron**: `0 1 * * * cd /var/www/familystock/api && python3 sync_all_markets.py`
- **日志**: `/var/log/familystock/sync_all.log`

---

## 当前问题分析

### ❌ Tushare 权限限制
```
抱歉，您每天最多访问该接口2次，权限的具体详情访问：
https://tushare.pro/document/1?doc_id=108
```

**影响**:
- 每天只能调用2次 `pro.news()`
- 当前配置每天01:00调用1次
- 手动调用时可能超出限额

**根本原因**:
- 当前 Tushare 账户权限为**基础会员**
- `pro.news()` 接口需要**高级会员**或**专业版**

---

### ❌ 定时任务未启用 `sync_news.py`

**发现**:
- `sync_news.py` 存在但**未被定时任务调用**
- 目前只有 `sync_all_markets.py` 被执行
- `cron_sync.sh` 也未被 crontab 调用

**当前 Cron 配置**:
```bash
*/5 * * * * flock -xn /tmp/stargate.lock -c '/usr/local/qcloud/stargate/admin/start.sh > /dev/null 2>&1 &'
*/15 * * * * /var/www/familystock/api/check_new_tasks.sh
0 1 * * * cd /var/www/familystock/api && python3 sync_all_markets.py >> /var/log/familystock/sync_all.log 2>&1
```

---

## 历史工作方式推断

基于代码结构和文件命名，推断历史方案：

### 方案A: 每小时同步（已废弃）
```bash
# cron_sync.sh 设计目标
python3 sync_tushare_pro.py  # 股票数据
python3 -c "pro.news(...)"   # 新闻数据
```
**废弃原因**: Tushare 新闻接口调用频率限制

### 方案B: 每日批量同步（当前方案）
```bash
# 当前运行
python3 sync_all_markets.py  # 股票 + 新闻
```
**问题**: 超出 Tushare 新闻接口权限

---

## 优化建议

### 方案1: 完全移除 Tushare 新闻调用
**优点**:
- 避免 API 限制问题
- 减少不必要的调用

**修改**:
```python
# sync_all_markets.py
# 注释掉以下代码
# df = pro.news(...)
# print(f"获取到 {len(df)} 条新闻")
```

---

### 方案2: 启用多层备用数据源
**优点**:
- 依靠 QVeris 和 东方财富网
- 保证新闻数据持续更新

**修改**:
- 将 `sync_news.py` 加入定时任务
- 频率: 每4小时（06:00, 10:00, 14:00, 18:00, 22:00）

**Cron 配置**:
```bash
0 6,10,14,18,22 * * * cd /var/www/familystock/api && python3 sync_news.py >> /var/log/familystock/sync_news.log 2>&1
```

---

### 方案3: 升级 Tushare 会员等级
**成本**:
- 高级会员: 未知
- 专业版: 未知

**可行性**:
- 需要评估预算
- 需要评估实际新闻需求

---

## 推荐方案

**立即执行**:
1. ✅ 移除 `sync_all_markets.py` 中的 Tushare 新闻调用
2. ✅ 启用 `sync_news.py` 定时任务（每4小时）
3. ✅ 依赖 QVeris 和 东方财富网获取新闻

**长期优化**:
- 监控 QVeris API 稳定性
- 评估 Tushare 会员升级必要性
- 考虑增加其他新闻数据源（如新浪财经、和讯网）

---

## 文件清单

### 核心脚本
- `/var/www/familystock/api/sync_news.py` - 新闻同步主脚本
- `/var/www/familystock/api/sync_all_markets.py` - 全市场同步脚本
- `/var/www/familystock/api/cron_sync.sh` - 废弃的定时脚本

### 日志文件
- `/var/log/familystock/sync_all.log` - 全市场同步日志
- `/var/log/familystock/sync_news.log` - 新闻同步日志（当前为空）

### 配置文件
- `/var/www/familystock/data/tushare_credentials.md` - Tushare 凭证

---

*审查完成时间: 2026-03-16 08:25*
