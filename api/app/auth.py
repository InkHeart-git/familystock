"""
用户认证路由
提供用户注册、登录、Token验证等功能
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import jwt
import re
import psycopg2

router = APIRouter(prefix="/auth", tags=["用户认证"])

# JWT配置
JWT_SECRET = "minirock-secret-key-2024"
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7

# 数据库配置
DB_CONFIG = {
    'host': 'localhost',
    'database': 'minirock',
    'user': 'minirock',
    'password': 'minirock123',
    'port': 5432
}

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('UTF8')
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def create_token(user_id: str) -> str:
    """创建JWT Token"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(days=JWT_EXPIRATION_DAYS),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> Optional[str]:
    """验证JWT Token"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get('user_id')
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# ==================== 请求模型 ====================

class RegisterRequest(BaseModel):
    phone: str
    password: str
    name: Optional[str] = None

class LoginRequest(BaseModel):
    phone: str
    password: str

class TokenResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None
    user: Optional[dict] = None

# ==================== API路由 ====================

@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """用户注册"""
    # 验证手机号格式
    if not re.match(r'^1[3-9]\d{9}$', request.phone):
        return TokenResponse(success=False, message="手机号格式不正确")
    
    # 验证密码长度
    if len(request.password) < 6:
        return TokenResponse(success=False, message="密码长度不能少于6位")
    
    conn = get_db_connection()
    if not conn:
        return TokenResponse(success=False, message="数据库连接失败")
    
    try:
        with conn.cursor() as cur:
            # 创建用户表（如果不存在）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    phone VARCHAR(20) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(100) DEFAULT '投资者',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 检查手机号是否已注册
            cur.execute("SELECT id FROM users WHERE phone = %s", (request.phone,))
            if cur.fetchone():
                return TokenResponse(success=False, message="该手机号已注册")
            
            # 插入新用户（明文密码，实际应使用哈希）
            user_name = request.name or f"用户{request.phone[-4:]}"
            cur.execute("""
                INSERT INTO users (phone, password_hash, name)
                VALUES (%s, %s, %s)
                RETURNING id, phone, name
            """, (request.phone, request.password, user_name))
            
            user = cur.fetchone()
            conn.commit()
            
            # 创建Token
            token = create_token(request.phone)
            
            return TokenResponse(
                success=True,
                message="注册成功",
                token=token,
                user={
                    'id': user[0],
                    'phone': user[1],
                    'name': user[2]
                }
            )
    except Exception as e:
        conn.rollback()
        print(f"注册失败: {e}")
        return TokenResponse(success=False, message=f"注册失败: {str(e)}")
    finally:
        conn.close()

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """用户登录"""
    # 验证手机号格式
    if not re.match(r'^1[3-9]\d{9}$', request.phone):
        return TokenResponse(success=False, message="手机号格式不正确")
    
    conn = get_db_connection()
    if not conn:
        return TokenResponse(success=False, message="数据库连接失败")
    
    try:
        with conn.cursor() as cur:
            # 创建用户表（如果不存在）
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    phone VARCHAR(20) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    name VARCHAR(100) DEFAULT '投资者',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            
            # 查询用户
            cur.execute("""
                SELECT id, phone, name, password_hash FROM users WHERE phone = %s
            """, (request.phone,))
            user = cur.fetchone()
            
            if not user:
                return TokenResponse(success=False, message="用户不存在")
            
            # 验证密码（明文比对，实际应使用哈希）
            if user[3] != request.password:
                return TokenResponse(success=False, message="密码错误")
            
            # 创建Token
            token = create_token(request.phone)
            
            return TokenResponse(
                success=True,
                message="登录成功",
                token=token,
                user={
                    'id': user[0],
                    'phone': user[1],
                    'name': user[2]
                }
            )
    except Exception as e:
        print(f"登录失败: {e}")
        return TokenResponse(success=False, message=f"登录失败: {str(e)}")
    finally:
        conn.close()

@router.get("/verify")
async def verify_token_endpoint(token: str):
    """验证Token是否有效"""
    user_id = verify_token(token)
    if user_id:
        return {"valid": True, "user_id": user_id}
    return {"valid": False, "message": "Token无效或已过期"}

@router.get("/profile")
async def get_profile(phone: str):
    """获取用户信息"""
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="数据库连接失败")
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, phone, name, created_at FROM users WHERE phone = %s
            """, (phone,))
            user = cur.fetchone()
            
            if not user:
                raise HTTPException(status_code=404, detail="用户不存在")
            
            return {
                'id': user[0],
                'phone': user[1],
                'name': user[2],
                'created_at': user[3]
            }
    finally:
        conn.close()
