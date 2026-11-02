"""
行为级自修复（业界常见）：空输出重试、假完成 nudge。

不是第二套「反思 critic LLM」。
"""

from __future__ import annotations

import logging
import re
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

ChatFn = Callable[..., Awaitable[str]]

_FAKE_DONE = re.compile(
    r"^(好的?|完成|搞定|ok|done|已完成|分析完成|没问题)[.!。！\s]*$",
    re.IGNORECASE,
)


def is_empty_output(text: str | None) -> bool:
    """是否空回复。"""
    return not (text or "").strip()


def is_fake_completion(text: str | None, *, max_chars: int = 40) -> bool:
    """短句且像「做完了」。"""
    t = (text or "").strip()
    if not t or len(t) > max_chars:
        return False
    if _FAKE_DONE.match(t):
        return True
    if len(t) <= 12 and "SKU" not in t.upper() and not any(ch.isdigit() for ch in t):
        return True
    return False


async def chat_with_repair(
    chat_fn: ChatFn,
    *,
    system: str,
    user: str,
    max_empty_retries: int = 2,
    repair_fake_completion: bool = True,
) -> dict[str, Any]:
    """
    包装一次 LLM 调用：空输出重试；假完成追加 nudge。

    Returns:
        dict: text / repairs / attempts。
    """
    repairs: list[str] = []
    text = ""
    attempts = 0

    for i in range(max_empty_retries + 1):
        attempts += 1
        text = await chat_fn(system=system, user=user)
        if not is_empty_output(text):
            break
        repairs.append(f"empty_output_retry_{i + 1}")
        logger.warning("llm empty output, retry %s", i + 1)

    if repair_fake_completion and is_fake_completion(text):
        repairs.append("fake_completion_nudge")
        nudge_user = (
            user
            + "\n\n[系统纠偏] 上一轮回复过于空泛或像假完成。"
            "请基于给定 Facts/数据给出具体结论（含 SKU/数字/动作），不要只说「好的/完成」。"
        )
        attempts += 1
        text2 = await chat_fn(system=system, user=nudge_user)
        if not is_empty_output(text2):
            text = text2

    return {"text": text, "repairs": repairs, "attempts": attempts}
