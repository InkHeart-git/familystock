"""
Kimi API 集成模块
"""
import requests

# Kimi API 配置
KIMI_API_URL = "https://api.moonshot.cn/v1/chat/completions"
KIMI_API_KEY = "sk-ba29925a6dc84f6da02ac006a2fc93f2"

def call_kimi_api(prompt, model="moonshot-v1-8k"):
    try:
        headers = {
            "Authorization": f"Bearer {KIMI_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "你是资深股票分析师，提供专业投资建议。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }
        response = requests.post(KIMI_API_URL, headers=headers, json=payload, timeout=30)
        result = response.json()
        if response.ok and "choices" in result:
            return result["choices"][0]["message"]["content"].strip()
        return None
    except Exception as e:
        print("Kimi API错误:", str(e))
        return None

