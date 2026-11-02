"""会签 JSON 解析与 LLM 调用辅助。"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from clients.llm_client import LlmClient

logger = logging.getLogger(__name__)


def strip_fences(text: str) -> str:
    """去掉 ```json 围栏。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json|JSON)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def parse_json_obj(text: str) -> dict[str, Any]:
    """解析为 dict；失败抛 ValueError。"""
    raw = strip_fences(text)
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


async def llm_json(
    llm: LlmClient | None,
    *,
    system: str,
    user: str,
) -> tuple[dict[str, Any] | None, str]:
    """
    调用 LLM 取 JSON；失败重试一次。

    Returns:
        (obj|None, source): source 为 llm / llm_retry_fail / no_llm。
    """
    if llm is None or not llm.enabled:
        return None, "no_llm"
    last_err = ""
    for attempt in range(2):
        try:
            raw = await llm.chat(system=system, user=user)
            return parse_json_obj(raw), "llm" if attempt == 0 else "llm_retry"
        except Exception as exc:
            last_err = str(exc)
            logger.warning("council llm json attempt %s failed: %s", attempt + 1, exc)
    logger.error("council llm json gave up: %s", last_err)
    return None, "llm_retry_fail"


def slim_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """送给会签的精简行（按 token 预算确定性截断）。"""
    from harness.memory.slim import slim_candidates_for_llm

    return slim_candidates_for_llm(candidates)

