"""
按 task_type 代码路由到专家 Agent。

EXPLOSION → Explosion；QUALITY → Quality。
对话入口不经此路由。
"""

from __future__ import annotations

from typing import Any

from harness.runtime import AppRuntime

SUPPORTED_TASK_TYPES = frozenset({"EXPLOSION", "QUALITY"})


async def route_task(
    task_type: str,
    context: dict[str, Any],
    runtime: AppRuntime,
) -> dict[str, Any]:
    """
    将领取到的任务派发到对应专家入口。

    Args:
        task_type: ``EXPLOSION`` 或 ``QUALITY``。
        context: 任务上下文。
        runtime: AppRuntime。

    Returns:
        dict: 专家返回结果。

    Raises:
        ValueError: 未知 task_type。
    """
    normalized = (task_type or "").strip().upper()
    if normalized not in SUPPORTED_TASK_TYPES:
        raise ValueError(f"unsupported task_type: {task_type!r}")

    if normalized == "EXPLOSION":
        from agents.explosion.graph import run_explosion

        return await run_explosion(context, runtime)

    from agents.quality.graph import run_quality

    return await run_quality(context, runtime)
