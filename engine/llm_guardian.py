"""
LLM Guardian - 统一LLM调用层 + 限流保护 + 自动fallback
Fallback链: MiniMax-M2.7-highspeed → DeepSeek → SiliconFlow
熔断器: 同一provider连续N次失败则跳过N分钟
"""
import os
import time
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ============================================================
# Provider 配置
# ============================================================
PROVIDERS = {
    'minimax': {
        'name': 'MiniMax-M2.7-highspeed',
        'endpoint': 'https://api.minimaxi.com/v1/chat/completions',
        'model': 'MiniMax-M2.7-highspeed',
        'timeout': 60,
        'cooldown': 120,      # 2分钟冷却
        'max_retries': 2,
    },
    'deepseek': {
        'name': 'DeepSeek',
        'endpoint': 'https://api.deepseek.com/v1/chat/completions',
        'model': 'deepseek-v4-pro',
        'timeout': 60,
        'cooldown': 60,       # 1分钟冷却
        'max_retries': 2,
    },
    'siliconflow': {
        'name': 'SiliconFlow',
        'endpoint': 'https://api.siliconflow.cn/v1/chat/completions',
        'model': 'deepseek-ai/DeepSeek-V3',
        'timeout': 60,
        'cooldown': 180,      # 3分钟冷却
        'max_retries': 1,
    },
}

# 从环境变量获取keys
def _get_key(provider: str) -> Optional[str]:
    env_map = {
        'minimax': 'MINIMAX_API_KEY',
        'deepseek': 'DEEPSEEK_API_KEY',
        'siliconflow': 'SILICONFLOW_API_KEY',
    }
    return os.environ.get(env_map.get(provider, ''))

# ============================================================
# 熔断器状态
# ============================================================
class CircuitBreaker:
    def __init__(self):
        # {provider: {'failures': N, 'cooldown_until': timestamp}}
        self._state: dict = {p: {'failures': 0, 'cooldown_until': 0} for p in PROVIDERS}
    
    def is_open(self, provider: str) -> bool:
        """熔断器是否开启"""
        s = self._state.get(provider, {})
        if s.get('cooldown_until', 0) > time.time():
            return True
        return False
    
    def record_failure(self, provider: str, cooldown: int):
        """记录一次失败，触发熔断"""
        s = self._state[provider]
        s['failures'] += 1
        if s['failures'] >= 3:  # 连续3次失败才熔断
            s['cooldown_until'] = time.time() + cooldown
            s['failures'] = 0
            logger.warning(f"[LLM Guardian] Circuit breaker OPEN for {provider} for {cooldown}s")
    
    def record_success(self, provider: str):
        """成功调用，重置失败计数"""
        self._state[provider]['failures'] = 0
    
    def get_available_providers(self, preference: str = 'minimax') -> list:
        """返回可用provider列表（按偏好排序）"""
        order = ['minimax', 'deepseek', 'siliconflow']
        # 把偏好provider放最前
        if preference in order:
            order.remove(preference)
            order.insert(0, preference)
        
        result = []
        for p in order:
            key = _get_key(p)
            if key and not self.is_open(p):
                result.append(p)
        return result


_circuit_breaker = CircuitBreaker()


# ============================================================
# 限流检测
# ============================================================
def _is_rate_limit(resp: requests.Response) -> bool:
    """判断是否是限流错误"""
    if resp.status_code in (429, 529):
        return True
    try:
        data = resp.json()
        err = data.get('error', {})
        if isinstance(err, dict):
            msg = str(err.get('message', '')).lower()
            code = str(err.get('code', ''))
            if any(x in msg for x in ['rate', 'limit', 'quota', 'overload', 'too many', '429', '529']):
                return True
            if code in ('1001', 'rate_limit', '429', '529'):
                return True
    except:
        pass
    return False


# ============================================================
# 单Provider调用
# ============================================================
def _call_provider(provider: str, messages: list, temperature: float = 0.7,
                   max_tokens: int = 2048) -> tuple:
    """
    调用单个provider，返回 (success, content_or_error, used_provider)
    """
    cfg = PROVIDERS[provider]
    api_key = _get_key(provider)
    
    if not api_key:
        return False, f"No API key for {provider}", provider
    
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    
    payload = {
        'model': cfg['model'],
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    
    try:
        resp = requests.post(
            cfg['endpoint'],
            headers=headers,
            json=payload,
            timeout=cfg['timeout'],
        )
        
        if resp.status_code == 200:
            data = resp.json()
            content = data['choices'][0]['message']['content']
            # 过滤MiniMax思考标签
            content = content.replace('<think>】，', '').replace('</think>', '')
            return True, content.strip(), provider
        
        if _is_rate_limit(resp):
            return False, f"Rate limit: {resp.status_code}", provider
        
        return False, f"HTTP {resp.status_code}: {resp.text[:200]}", provider
        
    except requests.exceptions.Timeout:
        return False, "Timeout", provider
    except Exception as e:
        return False, str(e), provider


# ============================================================
# 主入口
# ============================================================
def call(prompt: str,
         system: str = '',
         model_preference: str = 'minimax',
         temperature: float = 0.7,
         max_tokens: int = 2048,
         retry_count: int = 0) -> tuple:
    """
    统一LLM调用入口。
    
    Returns: (success: bool, content_or_error: str, provider_used: str)
    
    用法:
        ok, content, provider = call("hello", system="you are a helpful assistant")
    """
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    
    providers = _circuit_breaker.get_available_providers(model_preference)
    
    if not providers:
        all_cooldown = {p: _circuit_breaker._state[p]['cooldown_until'] > time.time() 
                        for p in PROVIDERS}
        logger.error(f"[LLM Guardian] All providers unavailable. Cooldowns: {all_cooldown}")
        return False, "All LLM providers are in cooldown", "none"
    
    tried = []
    for provider in providers:
        cfg = PROVIDERS[provider]
        
        ok, result, used = _call_provider(provider, messages, temperature, max_tokens)
        tried.append(provider)
        
        if ok:
            _circuit_breaker.record_success(provider)
            logger.info(f"[LLM Guardian] Success via {provider}")
            return True, result, provider
        
        logger.warning(f"[LLM Guardian] {provider} failed: {result}")
        _circuit_breaker.record_failure(provider, cfg['cooldown'])
        
        # 如果是被动限流(529)，立即跳过不重试
        if 'Rate limit' in result or '529' in result or '429' in result:
            logger.warning(f"[LLM Guardian] {provider} hit rate limit - skipping to next provider")
    
    # 所有provider都失败
    providers_str = ','.join(tried)
    return False, f"All providers failed after tried: {providers_str}", providers_str


# ============================================================
# 兼容旧llm_client.py的接口
# ============================================================
def chat(prompt: str, system: str = '', model: str = '') -> str:
    """兼容旧接口"""
    ok, content, _ = call(prompt, system=system, model_preference='minimax')
    if ok:
        return content
    # fallback to error string
    return f"[LLM Error] {content}"


# ============================================================
# 健康检查
# ============================================================
def health_check() -> dict:
    """检查所有provider状态"""
    result = {}
    for p in PROVIDERS:
        cfg = PROVIDERS[p]
        key = _get_key(p)
        result[p] = {
            'configured': bool(key),
            'available': not _circuit_breaker.is_open(p),
            'in_cooldown': _circuit_breaker.is_open(p),
            'cooldown_remaining': max(0, _circuit_breaker._state[p]['cooldown_until'] - time.time()),
            'failure_count': _circuit_breaker._state[p]['failures'],
            'model': cfg['model'],
        }
    return result


if __name__ == '__main__':
    # 快速测试
    import json
    print("=== LLM Guardian Health Check ===")
    print(json.dumps(health_check(), indent=2))
    print("\n=== Testing MiniMax ===")
    ok, content, prov = call("用一句话说今天的日期", model_preference='minimax')
    print(f"Provider: {prov}, Success: {ok}")
    if ok:
        print(f"Response: {content[:200]}")
    else:
        print(f"Error: {content}")
