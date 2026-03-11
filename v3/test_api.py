#!/usr/bin/env python3
"""
FamilyStock V3 测试脚本
"""

import requests
import json
import sys

BASE_URL = "http://43.160.193.165:8080"

def test_endpoint(name, method, endpoint, data=None):
    """测试API端点"""
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=10)
        else:
            response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            print(f"✅ {name}: 通过")
            return response.json()
        else:
            print(f"❌ {name}: 失败 (状态码 {response.status_code})")
            return None
    except Exception as e:
        print(f"❌ {name}: 错误 - {e}")
        return None

def main():
    print("=" * 60)
    print("FamilyStock V3 API 测试")
    print("=" * 60)
    print()
    
    # 测试根路径
    test_endpoint("根路径", "GET", "/")
    
    # 测试流水线状态
    test_endpoint("流水线状态", "GET", "/api/v3/pipeline/status")
    
    # 测试预警列表
    alerts_data = test_endpoint("预警列表", "GET", "/api/v3/alerts")
    if alerts_data:
        print(f"   获取到 {alerts_data.get('count', 0)} 条预警")
    
    # 测试活跃预警
    test_endpoint("活跃预警", "GET", "/api/v3/alerts/active")
    
    # 测试仪表盘
    dashboard_data = test_endpoint("风险仪表盘", "GET", "/api/v3/dashboard")
    if dashboard_data:
        data = dashboard_data.get('data', {})
        print(f"   风险分数: {data.get('risk_score', 'N/A')}")
        print(f"   活跃预警: {data.get('active_alerts', {}).get('total', 0)}")
    
    # 测试新闻
    test_endpoint("新闻列表", "GET", "/api/v3/news")
    
    # 测试股票分析
    stock_data = test_endpoint("股票分析", "POST", "/api/v3/stock/analyze", {"symbol": "600519"})
    if stock_data:
        data = stock_data.get('data', {})
        print(f"   AI评分: {data.get('ai_score', 'N/A')}")
        print(f"   建议: {data.get('recommendation', 'N/A')}")
    
    # 测试运行流水线
    test_endpoint("运行流水线", "POST", "/api/v3/pipeline/run")
    
    print()
    print("=" * 60)
    print("测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()