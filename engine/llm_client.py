"""
LLM 客户端 - 三路自动切换
MiniMax（主）→ Kimi（备）→ DeepSeek（兜底）
"""

import os
import asyncio
import aiohttp
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("LLMClient")


def load_env_keys():
    """从 ~/.hermes/.env 读取环境变量"""
    env_path = Path.home() / ".hermes" / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ[key] = val


# 初始化时加载环境变量
load_env_keys()


class MiniMaxProvider:
    """MiniMax LLM 提供商（主用）- 伪装成 coding plan 调用"""

    name = "MiniMax"

    def __init__(self):
        # 优先用 CN 端点（国内版 MiniMax）
        self.api_key = (
            os.getenv("MINIMAX_CN_API_KEY")
            or os.getenv("MINIMAX_API_KEY")
        )
        # MiniMax CN 用 minimaxi.com/v1（OpenAI兼容格式），全球用 minimax.io/v1
        self.base_url = (
            os.getenv("MINIMAX_CN_BASE_URL")
            or os.getenv("MINIMAX_BASE_URL")
            or "https://api.minimaxi.com/v1"
        )
        self.model = "MiniMax-M2.7-highspeed"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """调用 MiniMax M2.7（OpenAI 兼容格式 /v1/chat/completions）"""
        if not self.api_key:
            raise Exception("MINIMAX_API_KEY not configured")

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
            "max_tokens": 500,
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                f"{self.base_url}/chat/completions",
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(text)
                    content = data["choices"][0]["message"]["content"]
                    # MiniMax M2.7 返回可能包含 <think> 思考标签，需要过滤
                    import re
                    content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                    return content
                raise Exception(f"MiniMax HTTP {resp.status}: {text[:300]}")


class KimiProvider:
    """Kimi LLM 提供商（备用）- 伪装成 coding plan"""

    name = "Kimi"

    def __init__(self):
        self.api_key = os.getenv("KIMI_API_KEY")
        # Kimi 的 coding plan 端点
        self.base_url = os.getenv("KIMI_BASE_URL", "https://api.kimi.com/coding/v1/messages")
        self.model = "k2p5"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """调用 Kimi coding plan API"""
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
            "max_tokens": 500,
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                self.base_url,
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(text)
                    # Kimi 返回格式: {"content": [{"type": "text", "text": "..."}]}
                    content = data.get("content", [])
                    if isinstance(content, list) and len(content) > 0:
                        return content[0].get("text", "")
                    # 也支持 OpenAI 兼容格式
                    if "choices" in data:
                        return data["choices"][0]["message"]["content"]
                    raise Exception(f"Kimi 未知响应格式: {text[:200]}")
                raise Exception(f"Kimi HTTP {resp.status}: {text[:300]}")


class DeepSeekProvider:
    """DeepSeek LLM 提供商（兜底）- OpenAI 兼容格式"""

    name = "DeepSeek"

    def __init__(self):
        self.api_key = os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_KEY")
        self.base_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions")
        self.model = "deepseek-chat"

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """调用 DeepSeek API（OpenAI 兼容格式）"""
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
            "max_tokens": 500,
        }

        async with aiohttp.ClientSession() as sess:
            async with sess.post(
                self.base_url,
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    import json as _json
                    data = _json.loads(text)
                    return data["choices"][0]["message"]["content"]
                raise Exception(f"DeepSeek HTTP {resp.status}: {text[:300]}")


class LLMClient:
    """
    三路 LLM 自动切换客户端
    - 主用：MiniMax 2.7 high-speed（coding plan）
    - 备用：Kimi k2p5（coding plan）
    - 兜底：DeepSeek chat
    """
    
    def __init__(self):
        self.primary = MiniMaxProvider()   # MiniMax
        self.backup = KimiProvider()       # Kimi
        self.fallback = DeepSeekProvider() # DeepSeek
        
    async def generate(self, prompt: str, system_prompt: str = "",
                       model: str = "auto") -> str:
        """
        自动切换的生成接口
        model: "auto"=自动切换, "minimax", "kimi", "deepseek"
        """
        providers = [self.primary, self.backup, self.fallback]
        errors = []
        
        for p in providers:
            if model != "auto" and p.name.lower() != model.lower():
                continue
            try:
                result = await p.generate(prompt, system_prompt)
                if result:
                    logger.info(f"[LLMClient] {p.name} 成功")
                    return result
            except Exception as e:
                errors.append(f"{p.name}: {e}")
                logger.warning(f"[LLMClient] {p.name} 失败: {e}")
                continue
        
        logger.error(f"[LLMClient] 所有LLM均失败: {errors}")
        return ""  # 全部失败返回空


# 全局客户端实例
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取全局 LLM 客户端（延迟初始化）"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
