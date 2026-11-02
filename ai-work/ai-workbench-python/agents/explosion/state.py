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

    signal_items: list[dict[str, Any]]
    risk_items: list[dict[str, Any]]
    strategy_items: list[dict[str, Any]]
    signal_source: str
    risk_source: str
    strategy_source: str

    plan: dict[str, Any]
    council_sources: dict[str, Any]
    revise_scope: str

    summary: str
    report_files: dict[str, Any]
    upserted: bool

    status: str
    message: str
    result: dict[str, Any]

    # 路由辅助
    next_action: Literal["signal_risk", "strategy", "finish", "abort"]

