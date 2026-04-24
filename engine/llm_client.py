"""
LLM 客户端 - 全局并发控制 + 指数退避重试 + 429 冷却
修复目标：防止 MiniMax 等 provider 的瞬时并发超限导致 429 限流
"""

import asyncio
import logging
import os
import random
import time
from typing import Optional

import aiohttp

logger = logging.getLogger("LLMClient")


# ==================== 全局并发信号量 ====================
# 限制同时在飞的 LLM 请求数，防止瞬时并发击穿限流阈值
_MAX_CONCURRENT = 3
_llm_semaphore: Optional[asyncio.Semaphore] = None


def _get_semaphore() -> asyncio.Semaphore:
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    return _llm_semaphore


# ==================== Provider 429 冷却追踪 ====================
# 记录每个 provider 触发 429 的时间，冷却期内不切换回去
_PROVIDER_COOLDOWN: dict = {}   # provider_name -> timestamp
_PROVIDER_COOLDOWN_SEC = 300    # 5分钟冷却


def _is_provider_cooling(name: str) -> bool:
    """检查 provider 是否在 429 冷却期内"""
    last_429 = _PROVIDER_COOLDOWN.get(name, 0)
    if last_429 == 0:
        return False
    if time.time() - last_429 > _PROVIDER_COOLDOWN_SEC:
        # 冷却已过，清除记录
        _PROVIDER_COOLDOWN.pop(name, None)
        return False
    remaining = _PROVIDER_COOLDOWN_SEC - (time.time() - last_429)
    logger.debug(f"[LLMClient] {name} 冷却中，剩余 {remaining:.0f}s")
    return True


def _mark_429(name: str):
    """标记 provider 触发了 429"""
    _PROVIDER_COOLDOWN[name] = time.time()
    logger.warning(f"[LLMClient] {name} 触发429，标记冷却 {_PROVIDER_COOLDOWN_SEC}s")


def _clear_429(name: str):
    """清除 429 标记（成功时调用）"""
    _PROVIDER_COOLDOWN.pop(name, None)


# ==================== MiniMax Provider ====================

class MiniMaxProvider:
    """MiniMax LLM 提供商（主力）- MiniMax-M2.7-highspeed"""

    name = "MiniMax"

    def __init__(self):
        self.api_key = os.getenv("MINIMAX_CN_API_KEY")
        self.base_url = os.getenv("MINIMAX_CN_BASE_URL", "https://api.minimaxi.com/v1")
        self.model = "MiniMax-M2.7-highspeed"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key:
            raise Exception("MINIMAX_CN_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,   # 降低 token 上限，减少单次消耗
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(text)
                    content = data["choices"][0]["message"]["content"]
                    # 过滤 MiniMax 思考标签
                    import re as _re
                    content = _re.sub(r'<\|妄想之海\|>.*?<\|/妄想之海\|>', '', content, flags=_re.DOTALL).strip()
                    _clear_429(self.name)
                    return content
                if resp.status == 429:
                    _mark_429(self.name)
                    raise Exception(f"MiniMax HTTP 429: rate limited")
                raise Exception(f"MiniMax HTTP {resp.status}: {text[:300]}")


# ==================== Kimi Provider ====================

class KimiProvider:
    """Kimi LLM 提供商（备用）"""

    name = "Kimi"

    def __init__(self):
        self.api_key = os.getenv("KIMI_API_KEY")
        self.base_url = os.getenv("KIMI_BASE_URL", "https://api.kimi.com/coding/v1/messages")
        self.model = "k2p5"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key:
            raise Exception("KIMI_API_KEY not configured")

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "Kimi Claw Plugin"
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                self.base_url,
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(text)
                    content = data.get("content", [])
                    if isinstance(content, list) and len(content) > 0:
                        result = content[0].get("text", "")
                        _clear_429(self.name)
                        return result
                    if "choices" in data:
                        _clear_429(self.name)
                        return data["choices"][0]["message"]["content"]
                    raise Exception(f"Kimi 未知响应格式: {text[:200]}")
                if resp.status == 429:
                    _mark_429(self.name)
                    raise Exception(f"Kimi HTTP 429: rate limited")
                raise Exception(f"Kimi HTTP {resp.status}: {text[:300]}")


# ==================== SiliconFlow Provider ====================

class SiliconFlowProvider:
    """硅基流动 LLM 提供商（兜底）- OpenAI 兼容格式"""

    name = "SiliconFlow"

    def __init__(self):
        self.api_key = os.getenv("SILICONFLOW_API_KEY", os.getenv("SF_API_KEY"))
        self.base_url = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
        self.model = "deepseek-ai/DeepSeek-V3"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key:
            raise Exception("SILICONFLOW_API_KEY not configured")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(text)
                    _clear_429(self.name)
                    return data["choices"][0]["message"]["content"]
                if resp.status == 429:
                    _mark_429(self.name)
                    raise Exception(f"SiliconFlow HTTP 429: rate limited")
                raise Exception(f"SiliconFlow HTTP {resp.status}: {text[:300]}")


# ==================== DeepSeek Provider ====================

class DeepSeekProvider:
    """DeepSeek LLM 提供商（兜底）- OpenAI 兼容格式"""

    name = "DeepSeek"

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")
        self.base_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
        self.model = "deepseek-v4-pro"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key:
            raise Exception("DEEPSEEK_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 300,
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                self.base_url,
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=20)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(text)
                    _clear_429(self.name)
                    return data["choices"][0]["message"]["content"]
                if resp.status == 429:
                    _mark_429(self.name)
                    raise Exception(f"DeepSeek HTTP 429: rate limited")
                raise Exception(f"DeepSeek HTTP {resp.status}: {text[:300]}")


# ==================== LLMClient 主入口 ====================

class LLMClient:
    """
    LLM 客户端 - 全局并发控制 + 指数退避重试 + 429 冷却
    修复要点：
    1. 全局信号量限制同时最多 3 个 LLM 请求
    2. 429 后指数退避（2s → 4s → 8s → 16s），最多重试 4 次
    3. 429 后 provider 进入 5 分钟冷却，不立即切回
    4. 跳过冷却中的 provider
    """

    def __init__(self):
        self.primary = MiniMaxProvider()
        self.fallback = DeepSeekProvider()

    async def generate(self, prompt: str, system_prompt: str = "",
                       model: str = "auto") -> str:
        """
        自动切换的生成接口，带并发控制和指数退避重试
        """
        providers = [self.primary, self.fallback, SiliconFlowProvider(), KimiProvider()]
        errors = []

        for attempt in range(4):   # 最多重试 4 次（含首次）
            # 过滤冷却中的 provider
            available = [p for p in providers
                         if model == "auto" or p.name.lower() == model.lower()
                         if not _is_provider_cooling(p.name)]

            if not available:
                logger.warning(f"[LLMClient] 所有 provider 都在冷却中，等待 10s...")
                await asyncio.sleep(10)
                available = [p for p in providers
                             if model == "auto" or p.name.lower() == model.lower()
                             if not _is_provider_cooling(p.name)]
                if not available:
                    errors.append("All providers cooling down")
                    break

            for p in available:
                try:
                    # ===== 核心修复：信号量限流 =====
                    async with _get_semaphore():
                        result = await p.generate(prompt, system_prompt)
                    if result:
                        logger.info(f"[LLMClient] {p.name} 成功 (attempt {attempt + 1})")
                        return result
                except Exception as e:
                    err_str = str(e)
                    errors.append(f"{p.name}: {err_str}")

                    # 429：指数退避后重试整个 provider 列表
                    if "429" in err_str or "rate limit" in err_str.lower():
                        backoff = 2 ** attempt + random.uniform(0, 2)
                        logger.warning(f"[LLMClient] {p.name} 429，指数退避 {backoff:.1f}s (attempt {attempt + 1}/4)")
                        await asyncio.sleep(backoff)
                        break   # 跳出当前 provider 循环，重试所有 provider

                    # 非 429 错误：尝试下一个 provider
                    logger.warning(f"[LLMClient] {p.name} 失败（非429）: {e}")
                    continue
            else:
                # for-else：所有 provider 都失败了
                if attempt < 3:
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(f"[LLMClient] 本轮所有 provider 失败，等待 {wait:.1f}s 后重试...")
                    await asyncio.sleep(wait)

        logger.error(f"[LLMClient] 所有 LLM 均失败（已重试 4 次）: {errors}")
        return ""


# 全局客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端（延迟初始化）"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
