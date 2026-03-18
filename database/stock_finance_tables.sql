-- 财务指标表
CREATE TABLE IF NOT EXISTS stock_finance_indicator (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    end_date VARCHAR(10) NOT NULL COMMENT '报告期',
    pe DECIMAL(10,2) COMMENT '市盈率',
    pb DECIMAL(10,2) COMMENT '市净率',
    roe DECIMAL(10,4) COMMENT '净资产收益率',
    roa DECIMAL(10,4) COMMENT '总资产收益率',
    gross_margin DECIMAL(10,4) COMMENT '毛利率',
    net_margin DECIMAL(10,4) COMMENT '净利率',
    revenue_growth DECIMAL(10,4) COMMENT '营收增长率',
    profit_growth DECIMAL(10,4) COMMENT '净利润增长率',
    debt_ratio DECIMAL(10,4) COMMENT '资产负债率',
    current_ratio DECIMAL(10,4) COMMENT '流动比率',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_code_end_date (ts_code, end_date),
    INDEX idx_ts_code (ts_code),
    INDEX idx_end_date (end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='财务指标表';

-- 龙虎榜表
CREATE TABLE IF NOT EXISTS stock_top_list (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    trade_date VARCHAR(10) NOT NULL COMMENT '交易日期',
    name VARCHAR(50) COMMENT '股票名称',
    close DECIMAL(10,2) COMMENT '收盘价',
    pct_change DECIMAL(10,4) COMMENT '涨跌幅',
    turnover_rate DECIMAL(10,4) COMMENT '换手率',
    amount DECIMAL(18,2) COMMENT '成交额',
    buy_amount DECIMAL(18,2) COMMENT '买入金额',
    sell_amount DECIMAL(18,2) COMMENT '卖出金额',
    net_amount DECIMAL(18,2) COMMENT '净买入额',
    reason VARCHAR(200) COMMENT '上榜原因',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='龙虎榜表';

-- 北向资金持仓表
CREATE TABLE IF NOT EXISTS stock_hsgt_hold (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    trade_date VARCHAR(10) NOT NULL COMMENT '交易日期',
    hold_amount DECIMAL(18,2) COMMENT '持股数量',
    hold_ratio DECIMAL(10,4) COMMENT '持股占比',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ts_code_trade_date (ts_code, trade_date),
    INDEX idx_ts_code (ts_code),
    INDEX idx_trade_date (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='北向资金持仓表';

-- 公司公告表
CREATE TABLE IF NOT EXISTS stock_announcement (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    ts_code VARCHAR(20) NOT NULL COMMENT '股票代码',
    ann_date VARCHAR(10) NOT NULL COMMENT '公告日期',
    ann_title VARCHAR(500) COMMENT '公告标题',
    ann_content TEXT COMMENT '公告内容',
    ann_type VARCHAR(50) COMMENT '公告类型',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ts_code (ts_code),
    INDEX idx_ann_date (ann_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公司公告表';
