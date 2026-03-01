-- FamilyStock 数据库初始化脚本

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'member',
    family_group_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建家庭组表
CREATE TABLE IF NOT EXISTS family_groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    created_by INTEGER REFERENCES users(id),
    invite_code VARCHAR(20) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 添加外键约束
ALTER TABLE users ADD CONSTRAINT fk_users_family_group 
    FOREIGN KEY (family_group_id) REFERENCES family_groups(id);

-- 创建股票基础表
CREATE TABLE IF NOT EXISTS stocks (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    market VARCHAR(20) NOT NULL,
    industry VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建自选股表
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    stock_id INTEGER REFERENCES stocks(id) ON DELETE CASCADE,
    note TEXT,
    alert_price_high DECIMAL(10, 2),
    alert_price_low DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, stock_id)
);

-- 创建股票日数据表
CREATE TABLE IF NOT EXISTS stock_daily_data (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    trade_date DATE NOT NULL,
    open_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    volume BIGINT,
    amount DECIMAL(15, 2),
    pe_ratio DECIMAL(10, 2),
    pb_ratio DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_id, trade_date)
);

-- 创建财务数据表
CREATE TABLE IF NOT EXISTS financial_reports (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    report_type VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    revenue DECIMAL(15, 2),
    net_profit DECIMAL(15, 2),
    eps DECIMAL(10, 2),
    roe DECIMAL(10, 2),
    debt_ratio DECIMAL(5, 2),
    ai_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建新闻情绪表
CREATE TABLE IF NOT EXISTS news_sentiment (
    id SERIAL PRIMARY KEY,
    stock_id INTEGER REFERENCES stocks(id),
    title VARCHAR(255),
    source VARCHAR(100),
    publish_date TIMESTAMP,
    sentiment_score DECIMAL(3, 2),
    sentiment_label VARCHAR(20),
    ai_analysis TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建操作日志表
CREATE TABLE IF NOT EXISTS operation_logs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    action VARCHAR(50) NOT NULL,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_watchlist_user ON watchlist(user_id);
CREATE INDEX IF NOT EXISTS idx_daily_data_stock ON stock_daily_data(stock_id);
CREATE INDEX IF NOT EXISTS idx_daily_data_date ON stock_daily_data(trade_date);
CREATE INDEX IF NOT EXISTS idx_financial_stock ON financial_reports(stock_id);
CREATE INDEX IF NOT EXISTS idx_news_stock ON news_sentiment(stock_id);

-- 插入默认管理员账户（密码需要在应用层哈希）
-- INSERT INTO users (username, password_hash, role) VALUES ('admin', 'HASH_HERE', 'admin');
