"""Quality LangGraph 状态。"""

from __future__ import annotations

from typing import Any, TypedDict


class QualityState(TypedDict, total=False):
    """质检任务图状态。"""

    task_id: str
    conversation_id: str
    user_id: str
    task_input: dict[str, Any]
    features: dict[str, Any]
    rows: list[dict[str, Any]]
    summary: str
    explain_source: str
    status: str
    message: str
    result: dict[str, Any]

