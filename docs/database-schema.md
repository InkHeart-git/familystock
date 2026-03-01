# FamilyStock 数据库设计

## 表结构

### 1. 用户表 (users)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'member', -- admin, member
    family_group_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. 家庭组表 (family_groups)
```sql
CREATE TABLE family_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    invite_code VARCHAR(20) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. 股票基础表 (stocks)
```sql
CREATE TABLE stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL, -- 股票代码
    name VARCHAR(100) NOT NULL, -- 股票名称
    market VARCHAR(20) NOT NULL, -- SH/SZ/BJ
    industry VARCHAR(50), -- 行业
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. 自选股表 (watchlist)
```sql
CREATE TABLE watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    note TEXT, -- 备注
    alert_price_high DECIMAL(10, 2), -- 高价提醒
    alert_price_low DECIMAL(10, 2), -- 低价提醒
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, stock_id)
);
```

### 5. 股票日数据表 (stock_daily_data)
```sql
CREATE TABLE stock_daily_data (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    trade_date DATE NOT NULL,
    open_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    volume BIGINT,
    amount DECIMAL(15, 2),
    pe_ratio DECIMAL(10, 2), -- 市盈率
    pb_ratio DECIMAL(10, 2), -- 市净率
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, trade_date)
);
```

### 6. 财务数据表 (financial_reports)
```sql
CREATE TABLE financial_reports (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    report_type VARCHAR(20) NOT NULL, -- annual/quarterly
    report_date DATE NOT NULL,
    revenue DECIMAL(15, 2), -- 营业收入
    net_profit DECIMAL(15, 2), -- 净利润
    eps DECIMAL(10, 2), -- 每股收益
    roe DECIMAL(10, 2), -- 净资产收益率
    debt_ratio DECIMAL(5, 2), -- 资产负债率
    ai_summary TEXT, -- AI生成的摘要
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 7. 新闻情绪表 (news_sentiment)
```sql
CREATE TABLE news_sentiment (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    title VARCHAR(255),
    source VARCHAR(100),
    publish_date TIMESTAMP,
    sentiment_score DECIMAL(3, 2), -- -1 到 1
    sentiment_label VARCHAR(20), -- positive/negative/neutral
    ai_analysis TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 8. 操作日志表 (operation_logs)
```sql
CREATE TABLE operation_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL, -- add_watchlist/remove_watchlist/etc
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 索引设计

```sql
-- 自选股索引
CREATE INDEX idx_watchlist_user ON watchlist(user_id);

-- 股票日数据索引
CREATE INDEX idx_daily_data_stock ON stock_daily_data(stock_id);
CREATE INDEX idx_daily_data_date ON stock_daily_data(trade_date);

-- 财务报告索引
CREATE INDEX idx_financial_stock ON financial_reports(stock_id);

-- 新闻索引
CREATE INDEX idx_news_stock ON news_sentiment(stock_id);
CREATE INDEX idx_news_date ON news_sentiment(publish_date);
```