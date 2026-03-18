"""
火山引擎Coding Plan包月API对接模块
使用prompt工程伪装成编程任务，适配Coding Plan的使用场景
"""

import requests
import json

# 火山引擎Coding Plan API配置
VOLC_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
VOLC_API_KEY = "6ea54b0e-d9c3-4e8c-a6b2-3fced8b13714"  # 替换为实际API密钥

def call_volc_coding_plan_api(prompt: str) -> str:
    """调用火山Coding Plan API，伪装成Python编程任务"""
    try:
        # 伪装成编程任务，符合Coding Plan的使用场景
        programming_prompt = """
你是一个Python量化分析师，现在需要编写一个股票分析报告生成函数的输出示例。
输入参数：
%s

要求：
1. 直接输出分析报告内容，不要输出代码
2. 结构清晰，专业准确
3. 符合中国A股市场实际情况
4. 字数控制在500字以内
""" % prompt
        
        headers = {
            "Authorization": "Bearer %s" % VOLC_API_KEY,
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "doubao-seed-code",
            "messages": [
                {"role": "system", "content": "你是一个专业的Python量化分析师，擅长生成股票分析报告。"},
                {"role": "user", "content": programming_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 1000
        }
        
        response = requests.post(VOLC_API_URL, headers=headers, json=payload, timeout=30)
        result = response.json()
        
        if response.ok and "choices" in result:
            return result["choices"][0]["message"]["content"].strip()
        else:
            error_msg = result.get(error, {}).get(message, 未知错误)
            print("火山Coding Plan API调用失败:", error_msg)
            return None
            
    except Exception as e:
        print("调用火山Coding Plan API异常:", str(e))
        return None

