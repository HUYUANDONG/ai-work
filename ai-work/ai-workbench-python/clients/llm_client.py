"""
OpenAI 兼容 Chat Completions 客户端（默认对接阿里云百炼）。

用于爆品报表 HTML 生成；无 Key 时调用方应走模板降级。
正式分禁止由本客户端计算。
"""

from __future__ import annotations

from typing import Any

import httpx


class LlmClient:
    """
    薄封装：POST {base}/chat/completions。

    Attributes:
        base_url: 如 https://dashscope.aliyuncs.com/compatible-mode/v1
        api_key: Bearer Token。
        model: 模型名。
        timeout: 秒。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        """是否配置了可用的 API Key。"""
        return bool(self.api_key.strip())

    async def chat(self, *, system: str, user: str) -> str:
        """
        一次对话补全，返回助手文本。

        Args:
            system: 系统提示。
            user: 用户内容。

        Returns:
            str: 模型回复正文。

        Raises:
            RuntimeError: 未配置 Key 或 HTTP/解析失败。
        """
        if not self.enabled:
            raise RuntimeError("LLM API key is not configured")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.3,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"unexpected LLM response shape: {data!r}") from exc

