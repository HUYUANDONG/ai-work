"""
指数退避重试（对齐参考项目：500ms 起跳、上限 4s、有限次数）。

只重试瞬时故障；超时 / 业务 4xx / 熔断开闸不重试。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from harness.resilience.circuit import CircuitOpenError, SlidingWindowCircuitBreaker

logger = logging.getLogger(__name__)

T = TypeVar("T")


def backoff_seconds(attempt: int, *, multiplier: float = 0.5, cap: float = 4.0) -> float:
    """
    第 ``attempt`` 次失败后的等待秒数（0-based）。

    Args:
        attempt: 已失败次数下标（0 → 0.5s，1 → 1s，2 → 2s…）。
        multiplier: 基数。
        cap: 上限秒。

    Returns:
        float: sleep 秒数。
    """
    return min(cap, multiplier * (2**attempt))


def is_transient_llm_error(exc: BaseException) -> bool:
    """LLM 侧是否值得重试（超时 / 熔断 / 明确 4xx 除外）。"""
    if isinstance(exc, CircuitOpenError):
        return False
    if isinstance(exc, (APITimeoutError, TimeoutError, asyncio.TimeoutError)):
        return False
    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIConnectionError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code == 429 or exc.status_code >= 500
    # LlmClient 会把 SDK 异常包成 RuntimeError
    msg = str(exc)
    if "LLM timeout" in msg:
        return False
    if "LLM HTTP 429" in msg or "LLM HTTP 5" in msg:
        return True
    return False


def is_transient_http_error(exc: BaseException) -> bool:
    """Java HTTP / httpx 瞬时故障。"""
    if isinstance(exc, CircuitOpenError):
        return False
    if isinstance(exc, (httpx.TimeoutException, TimeoutError, asyncio.TimeoutError)):
        return False
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or code >= 500
    return False


def http_status_is_transient(status_code: int) -> bool:
    """响应码是否视为下游不健康且可重试。"""
    return status_code == 429 or status_code >= 500


async def call_with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_attempts: int = 2,
    breaker: SlidingWindowCircuitBreaker | None = None,
    is_retryable: Callable[[BaseException], bool] | None = None,
    label: str = "call",
) -> T:
    """
    带熔断守卫与指数退避的调用壳。

    每次 attempt 都会 ``guard`` + 按成败 ``record_*``；
    ``max_attempts=2`` 表示最多 2 次请求（与参考 BaseAgent 一致）。

    Args:
        fn: 无参异步调用。
        max_attempts: 总尝试次数。
        breaker: 可选熔断器。
        is_retryable: 异常是否可重试；默认不重试。
        label: 日志标签。

    Returns:
        T: ``fn`` 成功结果。

    Raises:
        BaseException: 最终失败或不可重试异常。
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1")
    retryable = is_retryable or (lambda _exc: False)
    last_exc: BaseException | None = None

    for attempt in range(max_attempts):
        if breaker is not None:
            breaker.guard()
        try:
            result = await fn()
            if breaker is not None:
                breaker.record_success()
            return result
        except BaseException as exc:
            last_exc = exc
            if breaker is not None and not isinstance(exc, CircuitOpenError):
                breaker.record_failure()
            can_retry = attempt + 1 < max_attempts and retryable(exc)
            if not can_retry:
                raise
            delay = backoff_seconds(attempt)
            logger.warning(
                "%s attempt %s/%s failed (%s); retry in %.1fs",
                label,
                attempt + 1,
                max_attempts,
                type(exc).__name__,
                delay,
            )
            await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc
