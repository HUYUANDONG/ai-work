"""
OpenAI 官方 SDK 客户端（默认对接阿里云百炼 compatible-mode）。

用于爆品报表 / 会签 JSON / 投放建议；无 Key 时调用方应走模板降级。
正式分禁止由本客户端计算。
支持非流式与 SSE token 流。
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from openai import APIStatusError, APITimeoutError, AsyncOpenAI

from harness.resilience import (
    CircuitOpenError,
    SlidingWindowCircuitBreaker,
    call_with_retry,
    is_transient_llm_error,
)

logger = logging.getLogger("uvicorn.error")

_DUMP_DIR = Path("tmp/llm")


def _content_to_text(content: Any) -> str:
    """把 message.content / delta.content 收成纯文本。"""
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(
            str(part.get("text") or "") if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)


def _message_text(message: Any) -> str:
    """从 SDK message 取出助手正文（兼容百炼 reasoning_content）。"""
    text = _content_to_text(getattr(message, "content", None)).strip()
    if not text:
        text = str(getattr(message, "reasoning_content", None) or "").strip()
    if not text:
        raise RuntimeError(f"LLM empty content: {message!r}"[:800])
    return text


def dump_llm_request(*, model: str, timeout: float, system: str, user: str) -> Path:
    """
    把本轮发给模型的 system/user 落到磁盘，并打到日志。

    Args:
        model: 模型名。
        timeout: 超时秒。
        system: 系统提示。
        user: 用户内容。

    Returns:
        Path: last_chat.json 路径。
    """
    _DUMP_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "timeout": timeout,
        "system_chars": len(system or ""),
        "user_chars": len(user or ""),
        "system": system,
        "user": user,
    }
    path = _DUMP_DIR / "last_chat.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    text_body = (
        f"model={model} timeout={timeout}s\n"
        f"system_chars={record['system_chars']} user_chars={record['user_chars']}\n"
        f"===== system =====\n{system}\n"
        f"===== user =====\n{user}\n"
    )
    (_DUMP_DIR / "last_chat.txt").write_text(text_body, encoding="utf-8")
    preview = (user or "")[:2000]
    if len(user or "") > 2000:
        preview += "\n...[truncated, see last_chat.txt]"
    logger.warning(
        "LLM request model=%s timeout=%ss system_chars=%s user_chars=%s dump=%s\n"
        "===== LLM system =====\n%s\n===== LLM user preview =====\n%s",
        model,
        timeout,
        record["system_chars"],
        record["user_chars"],
        path.resolve(),
        system,
        preview,
    )
    return path


class LlmClient:
    """
    百炼官方推荐写法：``AsyncOpenAI(base_url=compatible-mode/v1)``。

    Attributes:
        base_url: 如 https://dashscope.aliyuncs.com/compatible-mode/v1
        api_key: Bearer Token。
        model: 模型名。
        timeout: 秒。
        max_attempts: 瞬时故障总尝试次数（含首次；默认 2）。
        breaker: 滑动窗口熔断器。
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 40.0,
        max_attempts: int = 2,
        breaker: SlidingWindowCircuitBreaker | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self.breaker = breaker or SlidingWindowCircuitBreaker(name="llm")
        self._client: AsyncOpenAI | None = None
        if self.enabled:
            # trust_env=False：不走系统代理，避免本地代理把百炼请求弄挂
            # max_retries=0：重试交给 call_with_retry，避免与 SDK 叠床架屋
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=self.timeout,
                max_retries=0,
                http_client=httpx.AsyncClient(trust_env=False, timeout=self.timeout),
            )

    @property
    def enabled(self) -> bool:
        """是否配置了可用的 API Key。"""
        return bool(self.api_key.strip())

    def _create_kwargs(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool,
        stream: bool,
    ) -> dict[str, Any]:
        """组装 chat.completions.create 参数（含百炼 extra_body）。"""
        kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.3,
            "max_tokens": 2048,
            "stream": stream,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            # 百炼扩展字段走 extra_body，避免 SDK 校验未知参数
            "extra_body": {"enable_thinking": False},
        }
        # 百炼要求：json_object 时 messages 里须出现 json 字样；散文建议关闭
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs

    async def chat(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = True,
    ) -> str:
        """
        一次对话补全，返回助手文本。

        Args:
            system: 系统提示。
            user: 用户内容。
            json_mode: True 时强制 JSON Object（会签用）；散文建议用 False。

        Returns:
            str: 模型回复正文。

        Raises:
            RuntimeError: 未配置 Key 或 HTTP/解析失败。
        """
        if not self.enabled or self._client is None:
            raise RuntimeError("LLM API key is not configured")

        dump_llm_request(
            model=self.model,
            timeout=self.timeout,
            system=system,
            user=user,
        )
        started = time.monotonic()

        async def _once() -> str:
            assert self._client is not None
            try:
                completion = await self._client.chat.completions.create(
                    **self._create_kwargs(
                        system=system, user=user, json_mode=json_mode, stream=False
                    )
                )
            except APITimeoutError as exc:
                elapsed = time.monotonic() - started
                raise RuntimeError(
                    f"LLM timeout after {elapsed:.1f}s "
                    f"(limit={self.timeout}s) model={self.model} "
                    f"user_chars={len(user)}"
                ) from exc
            except APIStatusError as exc:
                raise RuntimeError(
                    f"LLM HTTP {exc.status_code}: {exc.message[:400]}"
                ) from exc
            if not completion.choices:
                raise RuntimeError(f"unexpected LLM response: {completion!r}"[:800])
            return _message_text(completion.choices[0].message)

        try:
            text = await call_with_retry(
                _once,
                max_attempts=self.max_attempts,
                breaker=self.breaker,
                is_retryable=is_transient_llm_error,
                label="llm.chat",
            )
        except CircuitOpenError:
            raise
        elapsed = time.monotonic() - started
        logger.warning(
            "LLM response OK in %.1fs model=%s user_chars=%s json_mode=%s",
            elapsed,
            self.model,
            len(user),
            json_mode,
        )
        return text

    async def chat_stream(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
    ) -> AsyncIterator[str]:
        """
        SSE token 流：逐段 yield content delta。

        Args:
            system: 系统提示。
            user: 用户内容。
            json_mode: 是否强制 JSON（一般流式散文为 False）。

        Yields:
            str: 增量文本。
        """
        if not self.enabled or self._client is None:
            raise RuntimeError("LLM API key is not configured")

        # 流式不重试（半截 token 无法幂等回放）；仍过熔断守卫
        self.breaker.guard()
        dump_llm_request(
            model=self.model,
            timeout=self.timeout,
            system=system,
            user=user,
        )
        started = time.monotonic()
        chars = 0
        try:
            stream = await self._client.chat.completions.create(
                **self._create_kwargs(
                    system=system, user=user, json_mode=json_mode, stream=True
                )
            )
            async for chunk in stream:
                if not chunk.choices:
                    continue
                text = _content_to_text(chunk.choices[0].delta.content)
                if text:
                    chars += len(text)
                    yield text
        except APITimeoutError as exc:
            self.breaker.record_failure()
            elapsed = time.monotonic() - started
            raise RuntimeError(
                f"LLM stream timeout after {elapsed:.1f}s "
                f"(limit={self.timeout}s) model={self.model}"
            ) from exc
        except APIStatusError as exc:
            self.breaker.record_failure()
            raise RuntimeError(
                f"LLM HTTP {exc.status_code}: {exc.message[:400]}"
            ) from exc
        except Exception:
            self.breaker.record_failure()
            raise
        self.breaker.record_success()
        elapsed = time.monotonic() - started
        logger.warning(
            "LLM stream done in %.1fs model=%s out_chars=%s json_mode=%s",
            elapsed,
            self.model,
            chars,
            json_mode,
        )
