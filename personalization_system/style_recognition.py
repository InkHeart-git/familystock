"""
用户风格识别算法
基于用户行为数据自动识别偏好的话术风格
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

# 风格权重配置
STYLE_WEIGHTS = {
    warm: {
        behaviors: {
            feedback_useless_professional: 2,  # 觉得专业分析没用
            view_investment_guide: 3,        # 看投资指南类内容
            view_market_sentiment: 2,        # 看市场情绪类内容
            slow_trade_frequency: 3,         # 交易频率低（<1次/周）
            low_risk_preference: 3,          # 风险偏好低
            new_user: 2                      # 新用户（注册<30天）
        },
        threshold: 5
    },
    professional: {
        behaviors: {
            feedback_useful_professional: 3, # 觉得专业分析有用
            view_financial_report: 4,        # 看财报、研报
            view_technical_analysis: 3,      # 看技术分析内容
            search_financial_index: 3,       # 搜索财务指标
            high_investment_experience: 3,    # 投资经验>3年
            financial_professional: 4        # 金融从业者
        },
        threshold: 6
    },
    minimal: {
        behaviors: {
            feedback_too_long: 3,            # 反馈分析太长
            fast_page_turning: 2,            # 快速翻页，不看详细内容
            high_trade_frequency: 3,         # 交易频率高（>3次/周）
            young_user: 2,                   # 年龄<30岁
            short_session_duration: 3        # 每次使用时长<3分钟
        },
        threshold: 5
    },
    aggressive: {
        behaviors: {
            feedback_too_conservative: 3,    # 反馈建议太保守
            high_risk_preference: 4,         # 风险偏好高
            frequent_search_concept_stock: 3,# 经常搜索概念股、题材股
            high_position_ratio: 3,          # 仓位>80%
            prefer_short_term_trading: 4     # 偏好短线交易
        },
        threshold: 6
    }
}

def calculate_style_score(user_data: Dict, behavior_records: List[Dict]) -> Tuple[str, float]:
    """
    计算用户的风格得分，返回最匹配的风格和置信度
    :param user_data: 用户基本信息
    :param behavior_records: 近30天的行为记录
    :return: (preferred_style, confidence_score)
    """
    scores = {style: 0 for style in STYLE_WEIGHTS.keys()}
    
    # 1. 基于用户基本属性计算得分
    age = user_data.get(age, 0)
    investment_experience = user_data.get(investment_experience, 1)
    is_financial_professional = user_data.get(is_financial_professional, False)
    risk_tolerance = user_data.get(risk_tolerance, 2)
    register_days = user_data.get(register_days, 0)
    
    # 年龄因素
    if age < 30:
        scores[minimal] += STYLE_WEIGHTS[minimal][behaviors][young_user]
    elif age > 50:
        scores[warm] += STYLE_WEIGHTS[warm][behaviors][new_user]
    
    # 投资经验因素
    if investment_experience >= 3:
        scores[professional] += STYLE_WEIGHTS[professional][behaviors][high_investment_experience]
    
    # 职业因素
    if is_financial_professional:
        scores[professional] += STYLE_WEIGHTS[professional][behaviors][financial_professional]
    
    # 风险偏好因素
    if risk_tolerance >= 4:
        scores[aggressive] += STYLE_WEIGHTS[aggressive][behaviors][high_risk_preference]
    elif risk_tolerance <= 2:
        scores[warm] += STYLE_WEIGHTS[warm][behaviors][low_risk_preference]
    
    # 新用户因素
    if register_days < 30:
        scores[warm] += STYLE_WEIGHTS[warm][behaviors][new_user]
    
    # 2. 基于行为数据计算得分
    behavior_counts = {}
    session_durations = []
    trade_count = 0
    last_30_days = datetime.now() - timedelta(days=30)
    
    for behavior in behavior_records:
        behavior_type = behavior.get(behavior_type, )
        created_at = behavior.get(created_at, datetime.now())
        
        if created_at < last_30_days:
            continue
            
        # 统计行为次数
        behavior_counts[behavior_type] = behavior_counts.get(behavior_type, 0) + 1
        
        # 统计交易次数
        if behavior_type == trade:
            trade_count += 1
        
        # 统计会话时长
        if behavior_type == session_end:
            duration = behavior.get(behavior_data, {}).get(duration, 0)
            if duration > 0:
                session_durations.append(duration)
    
    # 交易频率因素
    if trade_count >= 12:  # >3次/周
        scores[minimal] += STYLE_WEIGHTS[minimal][behaviors][high_trade_frequency]
    elif trade_count <= 4:  # <1次/周
        scores[warm] += STYLE_WEIGHTS[warm][behaviors][slow_trade_frequency]
    
    # 会话时长因素
    if session_durations:
        avg_duration = sum(session_durations) / len(session_durations)
        if avg_duration < 180:  # <3分钟
            scores[minimal] += STYLE_WEIGHTS[minimal][behaviors][short_session_duration]
    
    # 反馈行为因素
    if behavior_counts.get(feedback_useful_professional, 0) >= 2:
        scores[professional] += STYLE_WEIGHTS[professional][behaviors][feedback_useful_professional]
    
    if behavior_counts.get(feedback_useless_professional, 0) >= 2:
        scores[warm] += STYLE_WEIGHTS[warm][behaviors][feedback_useless_professional]
    
    if behavior_counts.get(feedback_too_long, 0) >= 2:
        scores[minimal] += STYLE_WEIGHTS[minimal][behaviors][feedback_too_long]
    
    if behavior_counts.get(feedback_too_conservative, 0) >= 2:
        scores[aggressive] += STYLE_WEIGHTS[aggressive][behaviors][feedback_too_conservative]
    
    # 3. 计算最高得分的风格
    max_score = max(scores.values())
    total_score = sum(scores.values()) or 1
    confidence = max_score / total_score
    
    # 找到最高得分的风格
    preferred_style = max(scores, key=scores.get)
    
    # 如果置信度过低，返回默认风格
    if confidence < 0.4:
        preferred_style = warm
        confidence = 0.5
    
    return preferred_style, round(confidence, 2)

def update_user_style_preference(user_id: str, user_data: Dict, behavior_records: List[Dict]) -> Dict:
    """更新用户的风格偏好"""
    preferred_style, confidence = calculate_style_score(user_data, behavior_records)
    
    return {
        user_id: user_id,
        preferred_style: preferred_style,
        confidence_score: confidence,
        last_updated: datetime.now().isoformat()
    }
