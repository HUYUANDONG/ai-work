"""
Token 估算与预算（业界常见启发式；可用真实 prompt_tokens 校准）。

中文按字符估，英文按 ~4 字符/token，避免纯字节/4 对 CJK 低估。
"""

from __future__ import annotations

import json
from typing import Any


def estimate_tokens(text: str) -> int:
    """
    估算文本 token 数。

    Args:
        text: 任意字符串。

    Returns:
        int: 估算值，至少 0。
    """
    if not text:
        return 0
    cjk = 0
    other = 0
    for ch in text:
        o = ord(ch)
        if (
            0x4E00 <= o <= 0x9FFF
            or 0x3400 <= o <= 0x4DBF
            or 0xF900 <= o <= 0xFAFF
            or 0x3000 <= o <= 0x303F
        ):
            cjk += 1
        else:
            other += 1
    # CJK ≈ 1 token/字；其它 ≈ 4 字符/token
    return cjk + max(1, (other + 3) // 4) if (cjk + other) else 0


def estimate_json(obj: Any) -> int:
    """估算 JSON 可序列化对象的 token。"""
    try:
        return estimate_tokens(json.dumps(obj, ensure_ascii=False, default=str))
    except TypeError:
        return estimate_tokens(str(obj))


class TokenBudget:
    """
    一次 LLM 调用的预算账本。

    Attributes:
        context_window: 模型上下文上限（token）。
        reserve_output: 留给输出的预留。
        guard_ratio: 输入守卫比例（如 0.7）。
    """

    def __init__(
        self,
        *,
        context_window: int = 128_000,
        reserve_output: int = 4096,
        guard_ratio: float = 0.70,
    ) -> None:
        self.context_window = max(4096, int(context_window))
        self.reserve_output = max(256, int(reserve_output))
        self.guard_ratio = min(0.9, max(0.4, float(guard_ratio)))
        self._scale = 1.0  # 真实用量校准系数，只上调

    @property
    def input_limit(self) -> int:
        """允许的输入 token 上限。"""
        raw = int(self.context_window * self.guard_ratio) - self.reserve_output
        return max(2048, raw)

    def calibrate(self, estimated: int, actual_prompt_tokens: int) -> None:
        """
        用 API 返回的 prompt_tokens 校准估算偏差（只上调，上限 1.6）。

        Args:
            estimated: 估算值。
            actual_prompt_tokens: 实测值。
        """
        if estimated <= 0 or actual_prompt_tokens <= 0:
            return
        ratio = actual_prompt_tokens / estimated
        if ratio > self._scale:
            self._scale = min(1.6, ratio)

    def sized(self, text: str) -> int:
        """带校准系数的估算。"""
        return int(estimate_tokens(text) * self._scale)

    def remaining(self, committed: int) -> int:
        """剩余可塞入的 token。"""
        return max(0, self.input_limit - committed)
