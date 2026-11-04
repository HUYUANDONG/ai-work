"""爆品计划：仅保留轻量 plan 元数据（会签 REVISE 已移除）。"""

from __future__ import annotations

from typing import Any


def init_plan(*, goal_mode: str, focus_slots: int) -> dict[str, Any]:
    """初始计划（无修订环）。"""
    return {
        "goal_mode": goal_mode,
        "focus_slots": focus_slots,
        "steps": ["SCORE", "EXPLOSION", "REPORT"],
        "revision": 0,
        "decision": "FINISH",
        "plan_degraded": False,
        "history": [],
    }
