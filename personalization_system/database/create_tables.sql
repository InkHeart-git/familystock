-- 用户画像表
CREATE TABLE IF NOT EXISTS user_profile (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL UNIQUE COMMENT '用户ID，关联现有用户体系',
    age TINYINT COMMENT '年龄',
    occupation VARCHAR(50) COMMENT '职业',
    investment_experience TINYINT COMMENT '投资经验：1=新手，2=1-3年，3=3-5年，4=5年以上',
    risk_tolerance TINYINT COMMENT '风险偏好：1=保守，2=稳健，3=平衡，4=激进，5=非常激进',
    is_financial_professional BOOLEAN DEFAULT FALSE COMMENT '是否是金融从业者',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_valid BOOLEAN DEFAULT TRUE,
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户画像表';

-- 用户行为数据表
CREATE TABLE IF NOT EXISTS user_behavior (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL COMMENT '用户ID',
    behavior_type VARCHAR(50) NOT NULL COMMENT '行为类型：view_stock, search_stock, trade, click_analysis, feedback_useful, feedback_useless等',
    behavior_data JSON COMMENT '行为详细数据',
    device_type VARCHAR(20) COMMENT '设备类型：mobile, pc, tablet',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN DEFAULT TRUE,
    INDEX idx_user_id (user_id),
    INDEX idx_behavior_type (behavior_type),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户行为数据表';

-- 用户风格偏好表
CREATE TABLE IF NOT EXISTS style_preference (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL UNIQUE COMMENT '用户ID',
    preferred_style VARCHAR(20) NOT NULL DEFAULT 'warm' COMMENT '偏好风格：warm=温暖鼓励型, professional=专业数据型, minimal=极简高效型, aggressive=激进果断型',
    confidence_score FLOAT DEFAULT 0.5 COMMENT '识别置信度：0-1，越高越准确',
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_count INT DEFAULT 1 COMMENT '更新次数，用于置信度计算',
    is_valid BOOLEAN DEFAULT TRUE,
    INDEX idx_user_id (user_id),
    INDEX idx_preferred_style (preferred_style)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户风格偏好表';
