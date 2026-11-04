"""
深度上下文压缩：仅在 token 水位过高时用 LLM 摘要旧轮。

策略（按产品约定）：
- 平时不截断、不压缩；
- 约占输入预算 80% 时触发一次；
- 只摘要「即将移出 working 的旧轮」，已有 summary 只追加、不再二次摘要；
- 失败则保持原文（不静默截断对话）。
"""

from __future__ import annotations

import logging
from typing import Any

from clients.llm_client import LlmClient
from harness.memory.rails import SessionMemory
from harness.memory.tokens import TokenBudget, estimate_tokens

logger = logging.getLogger(__name__)

_SUMMARIZE_SYSTEM = """你是会话记忆压缩器。把多轮对话压成一段短摘要，供后续助手使用。
要求：
1. 保留：用户目标、已确认的筛选条件（时间窗/目标模式/槽位）、结论要点、未决问题、关键 SKU/任务。
2. 删除：寒暄、重复确认、无信息客套。
3. 用简洁中文，条目或短段落均可；不要编造未出现的数字或商品。
4. 只输出摘要正文，不要前言。"""


def estimate_memory_tokens(mem: SessionMemory) -> int:
    """估算 summary + working 占用的 token。"""
    parts = [mem.summary or ""]
    for item in mem.working:
        parts.append(f"{item.get('role')}: {item.get('content')}")
    return estimate_tokens("\n".join(parts))


def pressure_ratio(mem: SessionMemory, budget: TokenBudget) -> float:
    """
    记忆部分相对输入预算的压力。

    Args:
        mem: 会话记忆。
        budget: token 预算。

    Returns:
        float: 0~若干，>=1 表示已超预算。
    """
    limit = max(1, budget.input_limit)
    return estimate_memory_tokens(mem) / float(limit)


def _format_turns(turns: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in turns:
        role = item.get("role") or "?"
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _max_message_id(turns: list[dict[str, Any]]) -> int | None:
    """从被折叠的轮次里取最大消息 id，供 Java 水位截断。"""
    found: int | None = None
    for item in turns:
        raw = item.get("id")
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and (found is None or value > found):
            found = value
    return found


async def deep_summarize_if_needed(
    mem: SessionMemory,
    *,
    llm: LlmClient | None,
    budget: TokenBudget,
    keep_last: int = 8,
    pressure_threshold: float = 0.80,
) -> dict[str, Any]:
    """
    水位达到阈值时，用 LLM 把旧轮压进 summary。

    Args:
        mem: 会话记忆（原地更新）。
        llm: 大模型客户端；不可用则跳过。
        budget: 预算。
        keep_last: 压缩后保留的原文尾部轮数。
        pressure_threshold: 触发阈值，默认 0.80。

    Returns:
        dict: compacted / skipped_reason / pressure / summary_chars。
    """
    keep_last = max(2, int(keep_last))
    ratio = pressure_ratio(mem, budget)
    meta: dict[str, Any] = {
        "compacted": False,
        "pressure": round(ratio, 4),
        "threshold": pressure_threshold,
        "summary_chars": len(mem.summary or ""),
        "working_turns": len(mem.working),
    }
    if ratio < pressure_threshold:
        meta["skipped_reason"] = "below_threshold"
        return meta
    if len(mem.working) <= keep_last:
        meta["skipped_reason"] = "nothing_to_fold"
        return meta
    if llm is None or not llm.enabled:
        meta["skipped_reason"] = "llm_unavailable"
        return meta

    old, mem.working = mem.working[:-keep_last], mem.working[-keep_last:]
    through_id = _max_message_id(old)
    user_payload = (
        "请摘要下列对话轮次（这些轮次将移出近期原文窗口）：\n\n"
        + _format_turns(old)
    )
    try:
        chunk = await llm.chat(
            system=_SUMMARIZE_SYSTEM,
            user=user_payload,
            json_mode=False,
        )
        chunk = (chunk or "").strip()
        if not chunk:
            # 摘要空则把旧轮放回，避免丢上下文
            mem.working = old + mem.working
            meta["skipped_reason"] = "empty_summary"
            return meta
        # 禁止对旧 summary 再送去摘要：只追加本轮折叠结果
        block = f"[Summarized turns x{len(old)}]\n{chunk}"
        if mem.summary and mem.summary.strip():
            mem.summary = mem.summary.rstrip() + "\n\n" + block
        else:
            mem.summary = block
        if through_id is not None:
            mem.summary_through_message_id = through_id
        meta.update(
            {
                "compacted": True,
                "dropped_turns": len(old),
                "summary_chars": len(mem.summary),
                "working_turns": len(mem.working),
                "summary_through_message_id": through_id,
                "pressure_after": round(pressure_ratio(mem, budget), 4),
            }
        )
        logger.info(
            "deep summarize ok conversation=%s dropped=%s pressure=%.3f->%.3f",
            mem.conversation_id,
            len(old),
            ratio,
            meta["pressure_after"],
        )
        return meta
    except Exception:
        logger.exception("deep summarize failed; keep original turns")
        mem.working = old + mem.working
        meta["skipped_reason"] = "llm_error"
        return meta
