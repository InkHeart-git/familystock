-- 用户认证系统数据库初始化脚本
-- 执行时间: 2026-03-15

-- 创建用户表
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 创建用户Token表（用于Token黑名单或刷新）
CREATE TABLE IF NOT EXISTS user_tokens (
    id SERIAL PRIMARY KEY,
    user_phone VARCHAR(20) NOT NULL REFERENCES users(phone) ON DELETE CASCADE,
    token_jti VARCHAR(36) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_revoked BOOLEAN DEFAULT FALSE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_user_tokens_jti ON user_tokens(token_jti);
CREATE INDEX IF NOT EXISTS idx_user_tokens_user_phone ON user_tokens(user_phone);

-- 修改portfolio表，添加user_phone字段关联用户
ALTER TABLE portfolio ADD COLUMN IF NOT EXISTS user_phone VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_portfolio_user_phone ON portfolio(user_phone);

-- 注释说明
COMMENT ON TABLE users IS '用户基本信息表';
COMMENT ON TABLE user_tokens IS '用户Token管理表';
COMMENT ON COLUMN users.phone IS '用户手机号，唯一标识';
COMMENT ON COLUMN users.password_hash IS 'bcrypt加密的密码哈希';
COMMENT ON COLUMN portfolio.user_phone IS '关联的用户手机号';