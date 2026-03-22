# 后端任务单 - 数据库架构整改

**任务编号**: BE-ARCH-001  
**优先级**: 🔥 高  
**预计时间**: 15分钟  
**创建时间**: 2026-03-20  
**执行人**: @方舟  
**验收人**: @玲珑

---

## 任务概述

将测试环境已完成的架构整改同步到生产环境：
1. 创建 `index_quotes` 表（专门存储大盘指数）
2. 修改指数API，从 `index_quotes` 表读取
3. 重启API服务

**目的**: 解决"上证指数显示10.88元"的问题，实现个股/指数数据分离。

---

## 前置条件

- SSH访问: `ubuntu@43.160.193.165`
- 权限: sudo
- 测试环境已完成整改（参考）

---

## 任务1: 创建 index_quotes 表

### 目标环境
- **服务器**: 新加坡生产环境 (43.160.193.165)
- **数据库**: `/var/www/familystock/api/data/family_stock.db`

### 执行命令

```bash
# 1. SSH登录
ssh -i ~/.ssh/tenclaw_key ubuntu@43.160.193.165

# 2. 创建表和索引
sqlite3 /var/www/familystock/api/data/family_stock.db << 'EOF'
CREATE TABLE IF NOT EXISTS index_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    market TEXT,
    trade_date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    pre_close REAL,
    change REAL,
    pct_chg REAL,
    vol REAL,
    amount REAL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ts_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_index_ts_code ON index_quotes(ts_code);
CREATE INDEX IF NOT EXISTS idx_index_trade_date ON index_quotes(trade_date);
CREATE INDEX IF NOT EXISTS idx_index_market ON index_quotes(market);

-- 初始化主要指数
INSERT OR IGNORE INTO index_quotes (ts_code, symbol, name, market, trade_date, close, pct_chg) VALUES
('000001.SH', '000001', '上证指数', 'A股', '20260320', 0, 0),
('399001.SZ', '399001', '深证成指', 'A股', '20260320', 0, 0),
('399006.SZ', '399006', '创业板指', 'A股', '20260320', 0, 0),
('000688.SH', '000688', '科创50', 'A股', '20260320', 0, 0),
('HSI', 'HSI', '恒生指数', '港股', '20260320', 0, 0),
('DJI', 'DJI', '道琼斯工业', '美股', '20260320', 0, 0),
('IXIC', 'IXIC', '纳斯达克', '美股', '20260320', 0, 0),
('SPX', 'SPX', '标普500', '美股', '20260320', 0, 0);
EOF
```

### 验证命令

```bash
# 检查表是否存在
sqlite3 /var/www/familystock/api/data/family_stock.db '.tables' | grep index

# 检查记录数（应该是8条）
sqlite3 /var/www/familystock/api/data/family_stock.db 'SELECT COUNT(*) FROM index_quotes;'

# 查看表结构
sqlite3 /var/www/familystock/api/data/family_stock.db '.schema index_quotes'
```

### 预期输出
```
index_quotes
8
CREATE TABLE index_quotes (...);
```

---

## 任务2: 修改指数API

### 目标环境
- **文件**: `/var/www/familystock/api/app/routers/tushare.py`

### 执行步骤

```bash
# 1. SSH登录（如已登录可跳过）
ssh -i ~/.ssh/tenclaw_key ubuntu@43.160.193.165

# 2. 备份原文件
cp /var/www/familystock/api/app/routers/tushare.py \
   /var/www/familystock/api/app/routers/tushare.py.bak.$(date +%H%M%S)

# 3. 复制测试环境的修复脚本到生产环境
sudo cp /var/www/familystock-test/api/app/routers/fix_index_api.py \
        /var/www/familystock/api/app/routers/

# 4. 执行修改脚本
cd /var/www/familystock/api/app/routers
sudo python3 fix_index_api.py

# 5. 修复文件权限
sudo chown ubuntu:ubuntu tushare.py
```

### 验证修改

```bash
# 检查API是否使用 index_quotes 表
grep 'FROM index_quotes' /var/www/familystock/api/app/routers/tushare.py

# 应该输出包含以下内容的行:
# SELECT * FROM index_quotes WHERE ts_code = ?
```

---

## 任务3: 重启API服务

### 执行步骤

```bash
# 1. 查找API进程
ps aux | grep uvicorn | grep -v grep

# 2. 停止旧进程
sudo pkill -f "uvicorn.*8000"

# 3. 启动新进程
cd /var/www/familystock/api
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/api.log 2>&1 &

# 4. 等待3秒启动
sleep 3

# 5. 检查进程是否运行
ps aux | grep uvicorn | grep -v grep
```

### 验证API

```bash
# 测试指数API
curl -s http://localhost:8000/api/tushare/index | python3 -m json.tool

# 或者直接访问
# http://43.160.193.165/api/tushare/index
```

### 预期输出
```json
[
  {
    "name": "上证指数",
    "ts_code": "000001.SH",
    "close": 0,
    "pct_chg": 0,
    "source": "unavailable"
  },
  {
    "name": "深证成指",
    "ts_code": "399001.SZ",
    ...
  },
  {
    "name": "创业板指",
    "ts_code": "399006.SZ",
    ...
  }
]
```

**注意**: 此时 `close` 为0是正常的，因为灵犀还没同步数据。关键是API能正常工作，不再显示个股价格。

---

## 文件路径对照表

| 项目 | 测试环境路径 | 生产环境路径 |
|------|-------------|-------------|
| SQLite数据库 | `/var/www/familystock-test/api/data/family_stock.db` | `/var/www/familystock/api/data/family_stock.db` |
| 指数API文件 | `/var/www/familystock-test/api/app/routers/tushare.py` | `/var/www/familystock/api/app/routers/tushare.py` |
| 修复脚本 | `/var/www/familystock-test/api/app/routers/fix_index_api.py` | `/var/www/familystock/api/app/routers/fix_index_api.py` |
| API端口 | 8001 | 8000 |

---

## 验收检查清单

- [ ] 任务1: `index_quotes` 表在生产环境数据库中存在
- [ ] 任务1: 表中有8条初始指数记录
- [ ] 任务2: API文件已备份
- [ ] 任务2: `grep 'FROM index_quotes'` 有输出
- [ ] 任务3: API进程在运行 (ps aux能看到uvicorn)
- [ ] 任务3: `curl /api/tushare/index` 返回JSON数据

---

## 故障排除

### 问题1: sqlite3 命令不存在
```bash
sudo apt-get update && sudo apt-get install -y sqlite3
```

### 问题2: 权限拒绝
```bash
sudo chown -R ubuntu:ubuntu /var/www/familystock/api/
```

### 问题3: API启动失败
```bash
# 查看错误日志
cat /tmp/api.log

# 检查端口占用
sudo lsof -i :8000
sudo kill -9 <PID>
```

---

## 完成后通知

执行完成后，在群里 @玲珑 通知验收。

验收URL: http://43.160.193.165/api/tushare/index
