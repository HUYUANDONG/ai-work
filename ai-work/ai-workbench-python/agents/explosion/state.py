"""Explosion LangGraph 状态。"""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class ExplosionState(TypedDict, total=False):
    """爆品任务图状态（可 checkpoint）。"""

    task_id: str
    conversation_id: str
    user_id: str
    task_input: dict[str, Any]
    goal_mode: str
    focus_slots: int
    top_n: int

    features: dict[str, Any]
    ranked: dict[str, Any]
    candidates: list[dict[str, Any]]
    advise_context: dict[str, Any]
    advise_llm_text: str
    advise_llm_source: str
    explosion_analysis: str
    explosion_source: str

    plan: dict[str, Any]

    summary: str
    report_files: dict[str, Any]
    upserted: bool

    status: str
    message: str
    result: dict[str, Any]

    next_action: Literal["explosion", "advise", "finish", "abort"]
