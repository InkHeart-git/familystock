# 灵犀数据同步任务清单

**任务编号**: DATA-SYNC-20260320  
**负责人**: @灵犀  
**优先级**: P0（指数同步）/ P1（日K同步）  
**预计时间**: 指数同步2小时 / 日K同步4-6小时（晚间进行）

---

## 任务一：测试环境指数数据同步（今天完成）

### 目标
将指数数据同步到测试环境 SQLite 数据库，确保大盘指数显示正确。

### 当前状态
```bash
# 测试环境指数表为空
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  "SELECT COUNT(*) FROM index_quotes;"
# 返回: 0

# 生产环境有6条数据
sqlite3 /var/www/familystock/api/data/family_stock.db \
  "SELECT COUNT(*) FROM index_quotes;"
# 返回: 6
```

### 同步方案（推荐方案A：从生产环境复制）

#### 方案A：直接从生产环境复制（最快）

```bash
# 1. 登录服务器
ssh ubuntu@43.160.193.165

# 2. 复制生产环境数据到测试环境
sudo sqlite3 /var/www/familystock/api/data/family_stock.db \
  ".dump index_quotes" | sudo sqlite3 /var/www/familystock-test/api/data/family_stock.db

# 3. 或者使用SQL导出导入
sudo sqlite3 /var/www/familystock/api/data/family_stock.db <<EOF
.headers on
.mode csv
.output /tmp/index_quotes.csv
SELECT * FROM index_quotes;
.quit
EOF

# 4. 清空测试环境表并导入
sudo sqlite3 /var/www/familystock-test/api/data/family_stock.db <<EOF
DELETE FROM index_quotes;
.mode csv
.import /tmp/index_quotes.csv index_quotes
.quit
EOF
```

#### 方案B：从Tushare重新同步（数据最新）

```bash
# 1. 创建Python同步脚本
cat > /tmp/sync_index_test.py << 'PYEOF'
import sqlite3
import requests
import json
from datetime import datetime, timedelta

# Tushare配置
TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"
DB_PATH = "/var/www/familystock-test/api/data/family_stock.db"

# 指数列表
INDEX_LIST = [
    ("000001.SH", "上证指数", "A股"),
    ("399001.SZ", "深证成指", "A股"),
    ("399006.SZ", "创业板指", "A股"),
    ("000688.SH", "科创50", "A股"),
    ("000300.SH", "沪深300", "A股"),
    ("000016.SH", "上证50", "A股"),
]

def get_index_data(ts_code):
    """从Tushare获取指数数据"""
    url = "https://api.tushare.pro"
    params = {
        "api_name": "index_daily",
        "token": TUSHARE_TOKEN,
        "params": {"ts_code": ts_code, "limit": 1},
        "fields": "ts_code,trade_date,open,high,low,close,pre_close,change,pct_chg,vol,amount"
    }
    
    try:
        response = requests.post(url, json=params, timeout=30)
        data = response.json()
        if data.get("data"):
            return data["data"][0]
    except Exception as e:
        print(f"获取{ts_code}失败: {e}")
    return None

def init_table():
    """创建表结构"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS index_quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts_code VARCHAR(20) NOT NULL,
            symbol VARCHAR(20),
            name VARCHAR(50),
            market VARCHAR(20),
            trade_date VARCHAR(8),
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            pre_close REAL,
            change REAL,
            pct_chg REAL,
            vol REAL,
            amount REAL,
            source VARCHAR(20) DEFAULT 'Tushare',
            UNIQUE(ts_code, trade_date)
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ 表结构初始化完成")

def sync_data():
    """同步数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for ts_code, name, market in INDEX_LIST:
        data = get_index_data(ts_code)
        if data:
            symbol = ts_code.split('.')[0]
            cursor.execute("""
                INSERT OR REPLACE INTO index_quotes 
                (ts_code, symbol, name, market, trade_date, open, high, low, close, 
                 pre_close, change, pct_chg, vol, amount, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data[0], symbol, name, market, data[1], data[2], data[3], 
                data[4], data[5], data[6], data[7], data[8], data[9], data[10], "Tushare"
            ))
            print(f"✅ {name}({ts_code}) 同步完成")
        else:
            print(f"❌ {name}({ts_code}) 同步失败")
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_table()
    sync_data()
    print("\n同步完成！")
PYEOF

# 2. 运行脚本
python3 /tmp/sync_index_test.py
```

### 验证步骤

```bash
# 1. 检查数据量
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  "SELECT COUNT(*) FROM index_quotes;"
# 预期: 6

# 2. 检查数据内容
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  "SELECT ts_code, name, close, pct_chg FROM index_quotes;"
# 预期: 显示6条指数数据，close > 0

# 3. 测试API
curl -s http://localhost:8001/api/tushare/index | python3 -m json.tool
# 预期: 返回JSON数组，包含上证指数等数据

# 4. 浏览器验证
# 访问: http://43.160.193.165:8080/stock-detail.html?code=000001
# 检查大盘指数区域是否显示正确数值（非0）
```

---

## 任务二：日K历史数据同步（今晚闲时进行）

### 目标
同步A股历史日K线数据到 `stock_daily` 表，用于技术分析和历史回测。

### 当前状态
```bash
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  "SELECT COUNT(*) FROM stock_daily;"
# 返回: 5（严重不足）

# 预期数据量: 约125万条 (5000只股票 × 250交易日)
```

### 表结构确认

```bash
# 检查表结构
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  ".schema stock_daily"

# 预期结构:
# CREATE TABLE stock_daily (
#     id INTEGER PRIMARY KEY,
#     ts_code TEXT,
#     trade_date TEXT,
#     open REAL,
#     high REAL,
#     low REAL,
#     close REAL,
#     vol REAL,
#     amount REAL,
#     UNIQUE(ts_code, trade_date)
# );
```

### 同步脚本

```bash
# 创建日K同步脚本
cat > /tmp/sync_stock_daily.py << 'PYEOF'
import sqlite3
import requests
import time
from datetime import datetime, timedelta

TUSHARE_TOKEN = "f4ba795df2475484a98087c15dc0fe5050c7197a9358d7edc044b735"
DB_PATH = "/var/www/familystock-test/api/data/family_stock.db"
BATCH_SIZE = 100  # 每批处理100只股票

def get_stock_list():
    """获取所有股票列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT ts_code, symbol FROM stock_basic OR SELECT ts_code FROM stocks")
    stocks = cursor.fetchall()
    conn.close()
    return [s[0] for s in stocks]

def get_daily_data(ts_code, start_date, end_date):
    """获取日K数据"""
    url = "https://api.tushare.pro"
    params = {
        "api_name": "daily",
        "token": TUSHARE_TOKEN,
        "params": {
            "ts_code": ts_code,
            "start_date": start_date,
            "end_date": end_date
        },
        "fields": "ts_code,trade_date,open,high,low,close,vol,amount"
    }
    
    try:
        response = requests.post(url, json=params, timeout=30)
        data = response.json()
        if data.get("data"):
            return data["data"]
    except Exception as e:
        print(f"获取{ts_code}失败: {e}")
    return []

def sync_daily_data():
    """同步日K数据"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 计算日期范围（最近1年）
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")
    
    # 获取股票列表
    cursor.execute("SELECT DISTINCT ts_code FROM stock_basic")
    stocks = cursor.fetchall()
    
    total = len(stocks)
    print(f"开始同步 {total} 只股票的日K数据...")
    
    for idx, (ts_code,) in enumerate(stocks, 1):
        # 检查是否已存在
        cursor.execute(
            "SELECT COUNT(*) FROM stock_daily WHERE ts_code = ? AND trade_date >= ?",
            (ts_code, start_date)
        )
        if cursor.fetchone()[0] > 200:  # 已有200天以上数据，跳过
            continue
        
        # 获取数据
        data = get_daily_data(ts_code, start_date, end_date)
        
        for row in data:
            cursor.execute("""
                INSERT OR REPLACE INTO stock_daily 
                (ts_code, trade_date, open, high, low, close, vol, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, row)
        
        if idx % 10 == 0:
            print(f"进度: {idx}/{total} ({idx/total*100:.1f}%)")
            conn.commit()
            time.sleep(1)  # 限速，避免API限制
    
    conn.commit()
    conn.close()
    print("✅ 日K数据同步完成！")

if __name__ == "__main__":
    sync_daily_data()
PYEOF
```

### 执行命令

```bash
# 1. 在screen或tmux中运行（防止SSH断开）
screen -S sync_daily

# 2. 运行脚本
python3 /tmp/sync_stock_daily.py

# 3. 按 Ctrl+A, D  detach，脚本会在后台继续运行
```

### 验证步骤

```bash
# 1. 检查数据量
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  "SELECT COUNT(*) FROM stock_daily;"
# 预期: > 100万条

# 2. 检查最新日期
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  "SELECT MAX(trade_date) FROM stock_daily;"
# 预期: 20260319 或最新交易日

# 3. 检查某只股票的数据完整性
sqlite3 /var/www/familystock-test/api/data/family_stock.db \
  "SELECT COUNT(*) FROM stock_daily WHERE ts_code = '600519.SH';"
# 预期: 约250条（1年数据）

# 4. 测试K线API
curl -s "http://localhost:8001/api/stock/kline/600519" | python3 -m json.tool | head -20
# 预期: 返回日K数据数组
```

---

## 任务三：生产环境数据维护（日常）

### 每日收盘后同步脚本

```bash
# 创建每日同步脚本
cat > /var/www/familystock/api/sync_daily.sh << 'EOF'
#!/bin/bash
# 每日收盘后数据同步
# 建议添加到crontab: 0 19 * * 1-5 /var/www/familystock/api/sync_daily.sh

echo "[$(date)] 开始每日数据同步..."

# 1. 同步个股行情
cd /var/www/familystock/api
python3 -c "
from app.routers.tushare import sync_stock_quotes
sync_stock_quotes()
" 2>/dev/null || echo "个股行情同步失败"

# 2. 同步指数数据
python3 /var/www/familystock/api/sync_index_cache.py 2>/dev/null || echo "指数同步失败"

echo "[$(date)] 同步完成"
EOF

chmod +x /var/www/familystock/api/sync_daily.sh
```

### 添加到定时任务

```bash
# 编辑crontab
crontab -e

# 添加行（每周一到周五，晚上7点执行）
0 19 * * 1-5 /var/www/familystock/api/sync_daily.sh >> /var/log/familystock_sync.log 2>&1
```

---

## 常见问题

### Q1: Tushare API限制
```
问题: 调用频率限制，每分钟最多X次
解决: 脚本中已添加 time.sleep(1)，如仍限制可增加间隔
```

### Q2: 内存不足
```
问题: 同步大量数据时内存不足
解决: 已使用分批处理，每10只股票commit一次
```

### Q3: 数据重复
```
问题: 重复运行导致数据重复
解决: SQL使用 INSERT OR REPLACE，唯一索引自动去重
```

### Q4: SSH断开
```
问题: 长时间同步时SSH断开
解决: 使用 screen 或 nohup 在后台运行
```

---

## 验收标准

| 任务 | 验收项 | 通过标准 |
|------|--------|----------|
| 任务一 | index_quotes表 | 6-8条记录，close>0 |
| 任务一 | API测试 | curl返回正确JSON |
| 任务二 | stock_daily表 | >100万条记录 |
| 任务二 | 单只股票数据 | 每只股票约250条 |
| 任务二 | K线API | 返回完整日K数据 |

---

**任务文档完成**  
**在线访问**: http://43.160.193.165/docs/data_sync_tasks_for_灵犀.md

如有问题随时联系 @玲珑 或 @奚文祺
