-- 股票基础信息表
CREATE TABLE IF NOT EXISTS stock_basic (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL UNIQUE COMMENT "股票代码（带后缀）",
    symbol VARCHAR(10) NOT NULL COMMENT "股票代码（不带后缀）",
    name VARCHAR(50) NOT NULL COMMENT "股票名称",
    area VARCHAR(20) COMMENT "地域",
    industry VARCHAR(50) COMMENT "行业",
    market VARCHAR(10) COMMENT "市场类型",
    list_date VARCHAR(10) COMMENT "上市日期",
    is_active BOOLEAN DEFAULT TRUE COMMENT "是否上市交易",
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_symbol (symbol),
    INDEX idx_name (name),
    INDEX idx_industry (industry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT="股票基础信息表";

-- 股票日线行情表
CREATE TABLE IF NOT EXISTS stock_daily (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT "股票代码",
    trade_date VARCHAR(10) NOT NULL COMMENT "交易日期",
    open DECIMAL(10,2) COMMENT "开盘价",
    high DECIMAL(10,2) COMMENT "最高价",
    low DECIMAL(10,2) COMMENT "最低价",
    close DECIMAL(10,2) COMMENT "收盘价",
    pre_close DECIMAL(10,2) COMMENT "前收盘价",
     DECIMAL(10,2) COMMENT "涨跌额",
    pct_chg DECIMAL(10,4) COMMENT "涨跌幅",
    vol DECIMAL(15,2) COMMENT "成交量",
    amount DECIMAL(18,2) COMMENT "成交额",
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_code_trade_date (ts_code, trade_date),
    INDEX idx_trade_date (trade_date),
    INDEX idx_ts_code (ts_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT="股票日线行情表";

-- 同步任务日志表
CREATE TABLE IF NOT EXISTS sync_task_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    task_name VARCHAR(50) NOT NULL COMMENT "任务名称",
    status VARCHAR(20) NOT NULL COMMENT "执行状态：success/failed",
    start_time TIMESTAMP NOT NULL COMMENT "开始时间",
    end_time TIMESTAMP COMMENT "结束时间",
    record_count INT DEFAULT 0 COMMENT "同步记录数",
    error_msg TEXT COMMENT "错误信息",
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_task_name (task_name),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT="同步任务日志表";

