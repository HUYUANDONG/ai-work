"""
滑动窗口熔断器（对齐参考项目 architecture 5.3 设计稿并真正落地）。

窗口: 最近 N 次调用
阈值: 错误率 > threshold 则 OPEN
恢复: open_seconds 后半开；半开成功 half_open_successes 次则 CLOSED
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Deque


class CircuitState(str, Enum):
    """熔断状态。"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(RuntimeError):
    """熔断开闸，拒绝调用下游。"""


@dataclass
class SlidingWindowCircuitBreaker:
    """
    基于最近 ``window_size`` 次成败的熔断器。

    Attributes:
        window_size: 滑动窗口长度（默认 10）。
        error_threshold: 错误率阈值，严格大于则开闸（默认 0.5）。
        open_seconds: OPEN 后多久进入半开（默认 30s）。
        half_open_successes: 半开需连续成功次数（默认 1）。
    """

    window_size: int = 10
    error_threshold: float = 0.5
    open_seconds: float = 30.0
    half_open_successes: int = 1
    name: str = "default"
    _outcomes: Deque[bool] = field(default_factory=deque)
    _state: CircuitState = CircuitState.CLOSED
    _opened_at: float = 0.0
    _half_open_ok: int = 0

    def __post_init__(self) -> None:
        if self.window_size < 1:
            raise ValueError("window_size must be >= 1")
        if not 0.0 < self.error_threshold <= 1.0:
            raise ValueError("error_threshold must be in (0, 1]")
        if self.open_seconds < 0:
            raise ValueError("open_seconds must be >= 0")
        if self.half_open_successes < 1:
            raise ValueError("half_open_successes must be >= 1")
        self._outcomes = deque(maxlen=self.window_size)

    @property
    def state(self) -> CircuitState:
        """当前状态；OPEN 到期时自动切半开。"""
        if self._state is CircuitState.OPEN:
            if time.monotonic() - self._opened_at >= self.open_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_ok = 0
        return self._state

    @property
    def error_rate(self) -> float:
        """窗口内失败占比；样本不足时为 0。"""
        if not self._outcomes:
            return 0.0
        fails = sum(1 for ok in self._outcomes if not ok)
        return fails / len(self._outcomes)

    def guard(self) -> None:
        """
        调用前检查；OPEN 且未到半开时间则拒绝。

        Raises:
            CircuitOpenError: 熔断开闸中。
        """
        st = self.state
        if st is CircuitState.OPEN:
            remain = max(0.0, self.open_seconds - (time.monotonic() - self._opened_at))
            raise CircuitOpenError(
                f"circuit open name={self.name} retry_after={remain:.1f}s "
                f"error_rate={self.error_rate:.2f}"
            )

    def record_success(self) -> None:
        """记录一次成功。"""
        self._outcomes.append(True)
        if self.state is CircuitState.HALF_OPEN:
            self._half_open_ok += 1
            if self._half_open_ok >= self.half_open_successes:
                self._state = CircuitState.CLOSED
                self._half_open_ok = 0
            return
        # CLOSED：窗口错误率仍可能再开闸（极端连续成功不会）
        self._maybe_trip()

    def record_failure(self) -> None:
        """记录一次失败。"""
        self._outcomes.append(False)
        if self.state is CircuitState.HALF_OPEN:
            self._trip()
            return
        self._maybe_trip()

    def _maybe_trip(self) -> None:
        """窗口满且错误率超阈值则开闸。"""
        if len(self._outcomes) < self.window_size:
            return
        if self.error_rate > self.error_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        self._half_open_ok = 0
