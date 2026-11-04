"""滑动窗口熔断与指数退避重试。"""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from harness.resilience import (
    CircuitOpenError,
    CircuitState,
    SlidingWindowCircuitBreaker,
    backoff_seconds,
    call_with_retry,
    is_transient_llm_error,
)


class BackoffTest(unittest.TestCase):
    def test_exponential_cap(self) -> None:
        self.assertEqual(backoff_seconds(0), 0.5)
        self.assertEqual(backoff_seconds(1), 1.0)
        self.assertEqual(backoff_seconds(2), 2.0)
        self.assertEqual(backoff_seconds(3), 4.0)
        self.assertEqual(backoff_seconds(10), 4.0)


class TransientLlmTest(unittest.TestCase):
    def test_timeout_not_retryable(self) -> None:
        self.assertFalse(is_transient_llm_error(RuntimeError("LLM timeout after 40.0s")))
        self.assertFalse(is_transient_llm_error(CircuitOpenError("open")))

    def test_http_5xx_retryable(self) -> None:
        self.assertTrue(is_transient_llm_error(RuntimeError("LLM HTTP 503: busy")))
        self.assertTrue(is_transient_llm_error(RuntimeError("LLM HTTP 429: rate")))


class CircuitBreakerTest(unittest.TestCase):
    def test_trip_after_window_over_threshold(self) -> None:
        cb = SlidingWindowCircuitBreaker(
            window_size=10,
            error_threshold=0.5,
            open_seconds=30.0,
            name="t",
        )
        # 5 成 5 败 → 50% 不触发（需 > 50%）
        for _ in range(5):
            cb.record_success()
        for _ in range(5):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.CLOSED)

        # 再失败挤掉一个成功 → 窗口内 6 败 4 成 = 60%
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        with self.assertRaises(CircuitOpenError):
            cb.guard()

    def test_half_open_recover(self) -> None:
        cb = SlidingWindowCircuitBreaker(
            window_size=4,
            error_threshold=0.5,
            open_seconds=0.0,
            half_open_successes=1,
            name="t",
        )
        for _ in range(4):
            cb.record_failure()
        # open_seconds=0 → 读 state 即进入半开
        self.assertEqual(cb.state, CircuitState.HALF_OPEN)
        cb.guard()
        cb.record_success()
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_half_open_failure_reopens(self) -> None:
        cb = SlidingWindowCircuitBreaker(
            window_size=4,
            error_threshold=0.5,
            open_seconds=30.0,
            name="t",
        )
        for _ in range(4):
            cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        cb._state = CircuitState.HALF_OPEN
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        with self.assertRaises(CircuitOpenError):
            cb.guard()


class CallWithRetryTest(unittest.IsolatedAsyncioTestCase):
    async def test_retries_then_succeeds(self) -> None:
        fn = AsyncMock(side_effect=[RuntimeError("LLM HTTP 503: x"), "ok"])
        out = await call_with_retry(
            fn,
            max_attempts=2,
            is_retryable=is_transient_llm_error,
            label="t",
        )
        self.assertEqual(out, "ok")
        self.assertEqual(fn.await_count, 2)

    async def test_timeout_no_retry(self) -> None:
        fn = AsyncMock(side_effect=RuntimeError("LLM timeout after 1.0s"))
        with self.assertRaises(RuntimeError):
            await call_with_retry(
                fn,
                max_attempts=3,
                is_retryable=is_transient_llm_error,
                label="t",
            )
        self.assertEqual(fn.await_count, 1)

    async def test_breaker_blocks(self) -> None:
        cb = SlidingWindowCircuitBreaker(window_size=2, error_threshold=0.5, open_seconds=30)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.state, CircuitState.OPEN)
        fn = AsyncMock(return_value="ok")
        with self.assertRaises(CircuitOpenError):
            await call_with_retry(
                fn,
                max_attempts=2,
                breaker=cb,
                is_retryable=is_transient_llm_error,
                label="t",
            )
        fn.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
