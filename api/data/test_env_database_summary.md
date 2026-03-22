# 测试环境数据库汇总

**数据库路径：`/var/www/familystock-test/api/data/family_stock.db`
**文件大小：5.3MB

## 表结构和数据量

| 表名 | 行数 | 用途 | 说明 |
|------|------|------|------|
| **stocks** | 5490 | 股票基础信息 | A股股票列表，包含代码、名称、行业、市场分类 |
| **stock_basic** | 0 | 备用基础信息表 | 空表，尚未使用 |
| **stock_daily** | 5 | 日线行情（测试） | 仅有少量测试数据 |
| **stock_quotes** | 6810 | 最新行情快照 | 保存最新的日线行情数据，用于前端展示 |
| **stock_hsgt_hold** | 0 | 北向持股数据 | 空表，尚未启用 |
| **news** | 800 | 新闻列表 | 新闻标题、内容、链接、情感标签 |
| **articles** | 0 | 深度文章 | 空表，尚未使用 |

## 各表详细结构

### stocks

```sql
CREATE TABLE stocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    area TEXT,
    industry TEXT,
    market TEXT,
    list_date TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### stock_daily

```sql
CREATE TABLE stock_daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts_code TEXT,
        trade_date TEXT,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        pre_close REAL,
        change REAL,
        pct_chg REAL,
        vol REAL,
        amount REAL,
        UNIQUE(ts_code, trade_date)
);
```

### stock_quotes

```sql
CREATE TABLE stock_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_code TEXT NOT NULL,
    symbol TEXT NOT NULL,
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
CREATE INDEX idx_quotes_ts_code ON stock_quotes(ts_code);
CREATE INDEX idx_quotes_trade_date ON stock_quotes(trade_date);
```

### news

```sql
CREATE TABLE news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    source TEXT,
    url TEXT,
    category TEXT,
    sentiment TEXT,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 同步计划

- **自动同步**：每日 18:00 从生产环境同步最新行情
- **数据来源**：生产环境 PostgreSQL `stock_cache` 表
- **保留独立数据库**：不影响生产环境数据

## 生成信息

- 生成时间：2026-03-20
- 生成者：灵犀
