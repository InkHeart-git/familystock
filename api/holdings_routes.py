"""
MiniRock持仓管理API路由
提供持仓的增删改查接口
"""

from flask import Blueprint, request, jsonify, g
from auth import verify_token
from database import (
    add_holding, get_user_holdings, update_holding, delete_holding,
    cache_stock_data, get_cached_stock
)
from tushare_helper import get_tushare_stock_quote

# 创建蓝图
holdings_bp = Blueprint('holdings', __name__, url_prefix='/api/v3/holdings')


def login_required(f):
    """登录验证装饰器"""
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'success': False, 'error': '缺少Token'}), 401
        
        user_id = verify_token(token)
        if not user_id:
            return jsonify({'success': False, 'error': 'Token无效或过期'}), 401
        
        g.user_id = user_id
        return f(*args, **kwargs)
    
    decorated.__name__ = f.__name__
    return decorated


@holdings_bp.route('', methods=['GET'])
@login_required
def get_holdings():
    """获取用户所有持仓"""
    holdings = get_user_holdings(g.user_id)
    
    result = []
    for h in holdings:
        qty = float(h['quantity'])
        avg_cost = float(h['avg_cost'])
        current_price = float(h['current_price']) if h['current_price'] else avg_cost
        
        # 计算盈亏
        cost_total = qty * avg_cost
        market_value = qty * current_price
        profit = market_value - cost_total
        profit_pct = (profit / cost_total * 100) if cost_total > 0 else 0
        
        result.append({
            'id': h['id'],
            'symbol': h['symbol'],
            'name': h['name'],
            'market': h['market'],
            'currency': h['currency'],
            'quantity': qty,
            'avg_cost': avg_cost,
            'current_price': current_price,
            'market_value': round(market_value, 2),
            'profit': round(profit, 2),
            'profit_pct': round(profit_pct, 2),
            'ai_score': h['ai_score'] if h['ai_score'] else 50
        })
    
    return jsonify({
        'success': True,
        'holdings': result,
        'count': len(result)
    })


@holdings_bp.route('', methods=['POST'])
@login_required
def add_holding_api():
    """添加/更新持仓"""
    data = request.json
    
    symbol = data.get('symbol')
    quantity = data.get('quantity')
    avg_cost = data.get('avg_cost')
    
    if not all([symbol, quantity, avg_cost]):
        return jsonify({'success': False, 'error': '缺少必要参数'}), 400
    
    # 尝试从Tushare获取股票信息
    try:
        stock_info = get_tushare_stock_quote(symbol)
        name = stock_info.get('ts_code', symbol) if stock_info else symbol
    except:
        name = symbol
    
    # 添加持仓
    success = add_holding(
        user_id=g.user_id,
        symbol=symbol,
        name=name,
        quantity=float(quantity),
        avg_cost=float(avg_cost)
    )
    
    if success:
        return jsonify({'success': True, 'message': '持仓添加成功'})
    else:
        return jsonify({'success': False, 'error': '添加失败'}), 500


@holdings_bp.route('/<symbol>', methods=['PUT'])
@login_required
def update_holding_api(symbol):
    """更新持仓"""
    data = request.json
    quantity = data.get('quantity')
    avg_cost = data.get('avg_cost')
    
    if quantity is None or avg_cost is None:
        return jsonify({'success': False, 'error': '缺少必要参数'}), 400
    
    success = update_holding(
        user_id=g.user_id,
        symbol=symbol,
        quantity=float(quantity),
        avg_cost=float(avg_cost)
    )
    
    if success:
        return jsonify({'success': True, 'message': '持仓更新成功'})
    else:
        return jsonify({'success': False, 'error': '更新失败'}), 500


@holdings_bp.route('/<symbol>', methods=['DELETE'])
@login_required
def delete_holding_api(symbol):
    """删除持仓"""
    success = delete_holding(g.user_id, symbol)
    
    if success:
        return jsonify({'success': True, 'message': '持仓删除成功'})
    else:
        return jsonify({'success': False, 'error': '删除失败'}), 500


@holdings_bp.route('/summary', methods=['GET'])
@login_required
def get_portfolio_summary():
    """获取投资组合摘要"""
    holdings = get_user_holdings(g.user_id)
    
    total_cost = 0
    total_value = 0
    sectors = {}
    
    for h in holdings:
        qty = float(h['quantity'])
        avg_cost = float(h['avg_cost'])
        current_price = float(h['current_price']) if h['current_price'] else avg_cost
        
        cost = qty * avg_cost
        value = qty * current_price
        
        total_cost += cost
        total_value += value
        
        # 按市场分类
        market = h['market'] or '其他'
        if market not in sectors:
            sectors[market] = {'value': 0, 'count': 0}
        sectors[market]['value'] += value
        sectors[market]['count'] += 1
    
    total_profit = total_value - total_cost
    total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0
    
    # 计算市场占比
    for market in sectors:
        sectors[market]['pct'] = round(sectors[market]['value'] / total_value * 100, 2) if total_value > 0 else 0
    
    return jsonify({
        'success': True,
        'summary': {
            'total_cost': round(total_cost, 2),
            'total_value': round(total_value, 2),
            'total_profit': round(total_profit, 2),
            'total_profit_pct': round(total_profit_pct, 2),
            'holdings_count': len(holdings),
            'sectors': sectors
        }
    })
