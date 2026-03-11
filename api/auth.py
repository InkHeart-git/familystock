"""
MiniRock用户认证模块
提供登录、注册、密码验证等功能
"""

import hashlib
import secrets
import time
from datetime import datetime, timedelta
from database import (
    create_user, get_user_by_phone, get_user_by_id,
    update_user_quota, add_holding, get_user_holdings
)

# 简单的token存储（生产环境应使用Redis）
token_store = {}


def hash_password(password):
    """密码哈希"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password, password_hash):
    """验证密码"""
    return hash_password(password) == password_hash


def generate_token(user_id):
    """生成访问令牌"""
    token = secrets.token_urlsafe(32)
    token_store[token] = {
        'user_id': user_id,
        'created_at': datetime.now(),
        'expires_at': datetime.now() + timedelta(days=7)
    }
    return token


def verify_token(token):
    """验证令牌"""
    if token not in token_store:
        return None
    
    token_data = token_store[token]
    if datetime.now() > token_data['expires_at']:
        del token_store[token]
        return None
    
    return token_data['user_id']


def register(phone, password, name='投资者'):
    """用户注册"""
    # 检查用户是否已存在
    existing = get_user_by_phone(phone)
    if existing:
        return {'success': False, 'error': '用户已存在'}
    
    # 创建用户
    password_hash = hash_password(password)
    user = create_user(phone, password_hash, name)
    
    if user:
        token = generate_token(user['id'])
        return {
            'success': True,
            'user': {
                'id': user['id'],
                'phone': user['phone'],
                'name': user['name'],
                'quota': user['quota_remaining']
            },
            'token': token
        }
    else:
        return {'success': False, 'error': '创建用户失败'}


def login(phone, password):
    """用户登录"""
    user = get_user_by_phone(phone)
    if not user:
        return {'success': False, 'error': '用户不存在'}
    
    if not verify_password(password, user['password_hash']):
        return {'success': False, 'error': '密码错误'}
    
    token = generate_token(user['id'])
    return {
        'success': True,
        'user': {
            'id': user['id'],
            'phone': user['phone'],
            'name': user['name'],
            'quota': user['quota_remaining']
        },
        'token': token
    }


def get_user_info(user_id):
    """获取用户信息"""
    user = get_user_by_id(user_id)
    if not user:
        return None
    
    # 获取持仓
    holdings = get_user_holdings(user_id)
    
    # 计算总资产
    total_asset = 0
    for h in holdings:
        qty = float(h['quantity'])
        price = float(h['current_price']) if h['current_price'] else float(h['avg_cost'])
        total_asset += qty * price
    
    return {
        'id': user['id'],
        'phone': user['phone'],
        'name': user['name'],
        'quota': user['quota_remaining'],
        'total_asset': round(total_asset, 2),
        'holdings_count': len(holdings),
        'created_at': user['created_at'].isoformat() if user['created_at'] else None
    }


def check_quota(user_id):
    """检查用户额度"""
    user = get_user_by_id(user_id)
    if not user:
        return {'has_quota': False, 'remaining': 0}
    
    remaining = user['quota_remaining']
    return {
        'has_quota': remaining > 0,
        'remaining': remaining
    }


def consume_quota(user_id, amount=1):
    """消耗额度"""
    user = get_user_by_id(user_id)
    if not user:
        return False
    
    remaining = user['quota_remaining'] - amount
    if remaining < 0:
        return False
    
    return update_user_quota(user_id, remaining)


# ==================== 测试代码 ====================

if __name__ == '__main__':
    print("测试用户认证模块...")
    
    # 测试注册
    result = register('18651993693', 'Wym626509', '测试用户')
    print(f"注册结果: {result}")
    
    # 测试登录
    result = login('18651993693', 'Wym626509')
    print(f"登录结果: {result}")
    
    if result['success']:
        token = result['token']
        user_id = verify_token(token)
        print(f"Token验证: user_id={user_id}")
        
        info = get_user_info(user_id)
        print(f"用户信息: {info}")
