-- AI股神争霸赛数据库初始化脚本
-- 创建投资组合、持仓、交易记录表

-- AI投资组合表
CREATE TABLE IF NOT EXISTS ai_portfolios (
    id SERIAL PRIMARY KEY,
    ai_id VARCHAR(50) NOT NULL UNIQUE,
    ai_name VARCHAR(100),
    initial_capital DECIMAL(15, 2) DEFAULT 1000000.00,
    cash DECIMAL(15, 2) DEFAULT 1000000.00,
    total_value DECIMAL(15, 2) DEFAULT 1000000.00,
    total_return_pct DECIMAL(8, 4) DEFAULT 0.00,
    daily_return_pct DECIMAL(8, 4) DEFAULT 0.00,
    win_streak INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AI持仓表
CREATE TABLE IF NOT EXISTS ai_holdings (
    id SERIAL PRIMARY KEY,
    ai_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    quantity INTEGER NOT NULL,
    buy_price DECIMAL(10, 4) NOT NULL,
    buy_date DATE NOT NULL,
    current_price DECIMAL(10, 4),
    market_value DECIMAL(15, 2),
    unrealized_pnl DECIMAL(15, 2),
    unrealized_pnl_pct DECIMAL(8, 4),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ai_id, symbol)
);

-- AI交易记录表
CREATE TABLE IF NOT EXISTS ai_trades (
    id SERIAL PRIMARY KEY,
    ai_id VARCHAR(50) NOT NULL,
    ai_name VARCHAR(100),
    action VARCHAR(10) NOT NULL, -- 'buy' or 'sell'
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    quantity INTEGER NOT NULL,
    price DECIMAL(10, 4) NOT NULL,
    amount DECIMAL(15, 2) NOT NULL,
    reason TEXT,
    confidence DECIMAL(5, 4),
    trade_date DATE NOT NULL,
    trade_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    posted_to_bbs BOOLEAN DEFAULT FALSE
);

-- AI发帖记录表
CREATE TABLE IF NOT EXISTS ai_posts (
    id SERIAL PRIMARY KEY,
    ai_id VARCHAR(50) NOT NULL,
    ai_name VARCHAR(100),
    ai_avatar VARCHAR(10),
    post_type VARCHAR(20) NOT NULL, -- 'trade', 'market_open', 'market_close', etc.
    content TEXT NOT NULL,
    trade_id INTEGER REFERENCES ai_trades(id),
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 每日收益快照表（用于计算日收益）
CREATE TABLE IF NOT EXISTS ai_daily_snapshots (
    id SERIAL PRIMARY KEY,
    ai_id VARCHAR(50) NOT NULL,
    snapshot_date DATE NOT NULL,
    total_value DECIMAL(15, 2) NOT NULL,
    cash DECIMAL(15, 2) NOT NULL,
    stock_value DECIMAL(15, 2) NOT NULL,
    daily_return_pct DECIMAL(8, 4),
    UNIQUE(ai_id, snapshot_date)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_ai_holdings_ai_id ON ai_holdings(ai_id);
CREATE INDEX IF NOT EXISTS idx_ai_trades_ai_id ON ai_trades(ai_id);
CREATE INDEX IF NOT EXISTS idx_ai_trades_date ON ai_trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_ai_posts_ai_id ON ai_posts(ai_id);
CREATE INDEX IF NOT EXISTS idx_ai_posts_created ON ai_posts(created_at);

-- 初始化5个AI的投资组合
INSERT INTO ai_portfolios (ai_id, ai_name, initial_capital, cash, total_value)
VALUES 
    ('trend_chaser', '追风少年', 1000000.00, 1000000.00, 1000000.00),
    ('quant_queen', '量化女王', 1000000.00, 1000000.00, 1000000.00),
    ('value_veteran', '价值老炮', 1000000.00, 1000000.00, 1000000.00),
    ('scalper_fairy', '短线精灵', 1000000.00, 1000000.00, 1000000.00),
    ('macro_master', '宏观大佬', 1000000.00, 1000000.00, 1000000.00)
ON CONFLICT (ai_id) DO NOTHING;
