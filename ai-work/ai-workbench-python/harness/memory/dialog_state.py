"""
对话路由用的显式会话状态（业界常见：状态机 + 短上下文，而非塞全文报告）。

决策/规则只读本快照；贵步骤（建议 LLM）另开，不进路由。
"""

from __future__ import annotations

from typing import Any

# 路由可见相位
PHASE_IDLE = "IDLE"
PHASE_AWAITING_CLARIFY = "AWAITING_CLARIFY"
PHASE_AWAITING_ADVISE = "AWAITING_ADVISE_CONFIRM"
PHASE_AWAITING_COPY = "AWAITING_COPY_CONFIRM"
PHASE_DONE = "DONE"

_TASK_KEYS = (
    "time_window_days",
    "goal_mode",
    "focus_slots",
    "top_n",
    "include_advise",
)


def compact_task_input(task_input: dict[str, Any] | None) -> dict[str, Any]:
    """只保留路由需要的任务槽位。"""
    if not isinstance(task_input, dict):
        return {}
    return {k: task_input[k] for k in _TASK_KEYS if k in task_input and task_input[k] is not None}


def resolve_phase(
    *,
    advice_offer_pending: bool = False,
    awaiting_clarify: bool = False,
    active_task_id: str | None = None,
    queue_message: bool = False,
    ops_phase: str | None = None,
) -> str:
    """
    由标志位推导当前相位（优先级：ops 相位 > 等建议确认 > 等澄清 > 空闲）。

    Args:
        advice_offer_pending: 榜单已出，等「要/不用」。
        awaiting_clarify: 上一轮返回了 clarify_pending。
        active_task_id: 保留入参，不再改相位。
        queue_message: 保留入参，不再改相位。
        ops_phase: 运营流水线显式相位（优先）。

    Returns:
        str: 相位枚举名。
    """
    phase = str(ops_phase or "").strip().upper()
    if phase in {PHASE_AWAITING_ADVISE, PHASE_AWAITING_COPY, PHASE_DONE}:
        return phase
    if advice_offer_pending or phase == "AWAITING_ADVISE":
        return PHASE_AWAITING_ADVISE
    if awaiting_clarify:
        return PHASE_AWAITING_CLARIFY
    return PHASE_IDLE


def build_router_snapshot(
    *,
    last_intent: str | None = None,
    last_task_input: dict[str, Any] | None = None,
    advice_offer_pending: bool = False,
    awaiting_clarify: bool = False,
    active_task_id: str | None = None,
    queue_message: bool = False,
    ops_phase: str | None = None,
) -> dict[str, Any]:
    """
    组装决策模型 / 规则可读的短状态。

    Returns:
        dict: phase / last_intent / last_task / flags。
    """
    phase = resolve_phase(
        advice_offer_pending=advice_offer_pending,
        awaiting_clarify=awaiting_clarify,
        active_task_id=active_task_id,
        queue_message=queue_message,
        ops_phase=ops_phase,
    )
    snap: dict[str, Any] = {
        "phase": phase,
        "last_intent": last_intent,
        "last_task": compact_task_input(last_task_input),
        "flags": {
            "advice_offer_pending": bool(advice_offer_pending)
            or phase == PHASE_AWAITING_ADVISE,
            "awaiting_copy": phase == PHASE_AWAITING_COPY,
            "awaiting_clarify": bool(awaiting_clarify),
        },
    }
    if active_task_id:
        snap["active_task_id"] = active_task_id
    return snap


def format_router_state(snapshot: dict[str, Any] | None) -> str:
    """
    把快照打成决策 prompt 里的 Session state 段。

    Args:
        snapshot: ``build_router_snapshot`` 结果。

    Returns:
        str: 多行英文短状态（模型侧稳定）。
    """
    if not snapshot:
        return "Session state: IDLE (no prior task)."
    phase = snapshot.get("phase") or PHASE_IDLE
    lines = [
        f"Session phase: {phase}",
        f"Last task intent: {snapshot.get('last_intent') or 'none'}",
    ]
    task = snapshot.get("last_task") or {}
    if task:
        bits = [f"{k}={v}" for k, v in task.items()]
        lines.append("Last task slots: " + ", ".join(bits))
    flags = snapshot.get("flags") or {}
    if flags.get("advice_offer_pending"):
        lines.append(
            "Awaiting user confirm for placement advise: "
            "short yes(要/需要) → write advise; no(不用) → keep list only. "
            "Do NOT open a new EXPLOSION unless user changes window/goal."
        )
    if flags.get("awaiting_copy"):
        lines.append(
            "Awaiting user confirm for compliant marketing copy: "
            "yes(要) → generate copy; no(不用) → skip. "
            "Do NOT open a new EXPLOSION."
        )
    if flags.get("awaiting_clarify"):
        lines.append(
            "Previous turn asked clarifying question; "
            "map clear answers to EXPLOSION/QUALITY/SKU_DEEP."
        )
    return "\n".join(lines)
