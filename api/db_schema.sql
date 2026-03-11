-- MiniRock 持仓管理数据库表结构
-- 创建时间: 2026-03-10

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) DEFAULT '投资者',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 持仓表
CREATE TABLE IF NOT EXISTS holdings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0,
    avg_cost DECIMAL(10, 2) NOT NULL DEFAULT 0,
    market VARCHAR(20) DEFAULT 'A股',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, symbol)
);

-- 预警表
CREATE TABLE IF NOT EXISTS alerts (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,  -- profit_warning, price_alert, etc.
    severity VARCHAR(20) NOT NULL,    -- high, medium, low
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_holdings_user_id ON holdings(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_user_id ON alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);

-- 插入默认用户
INSERT INTO users (user_id, name) VALUES ('demo_user', '测试用户') ON CONFLICT DO NOTHING;

-- 插入初始持仓
INSERT INTO holdings (user_id, symbol, name, quantity, avg_cost, market) VALUES
('demo_user', '600519', '贵州茅台', 10, 1650.00, 'A股'),
('demo_user', '300750', '宁德时代', 50, 200.00, 'A股'),
('demo_user', '002594', '比亚迪', 30, 260.00, 'A股')
ON CONFLICT DO NOTHING;
