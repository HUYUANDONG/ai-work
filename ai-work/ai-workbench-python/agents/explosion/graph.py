"""
Explosion 入口：调用 LangGraph 编排（会签修订 / checkpoint / 思考流）。
"""

from __future__ import annotations

import logging
from typing import Any

from agents.explosion.lg_graph import get_explosion_app
from harness.runtime import AppRuntime
from harness.task_control import TaskAborted, TaskControl

logger = logging.getLogger(__name__)


def _make_control(context: dict[str, Any], runtime: AppRuntime) -> TaskControl | None:
    task_id = str(context.get("task_id") or "")
    if not task_id:
        return None
    return TaskControl(
        task_id=task_id,
        lease_token=str(context.get("lease_token") or "dev-lease"),
        runtime=runtime,
    )


async def run_explosion(
    context: dict[str, Any],
    runtime: AppRuntime,
) -> dict[str, Any]:
    """
    执行爆品筛选（LangGraph）。

    Args:
        context: task_id / input / lease_token / conversation_id / user_id。
        runtime: AppRuntime。

    Returns:
        dict: REPORT_READY / FAILED_* / CANCELLED / PAUSED。
    """
    task_input = dict(context.get("input") or {})
    task_id = str(context.get("task_id") or "unknown-task")
    conversation_id = str(context.get("conversation_id") or "mock-conversation")
    user_id = str(context.get("user_id") or "mock-user")
    control = _make_control(context, runtime)
    app = get_explosion_app()

    initial = {
        "task_id": task_id,
        "conversation_id": conversation_id,
        "user_id": user_id,
        "task_input": task_input,
        "status": "RUNNING",
        "next_action": "signal_risk",
    }
    config = {
        "configurable": {
            "thread_id": task_id,
            "runtime": runtime,
            "control": control,
        }
    }

    try:
        final = await app.ainvoke(initial, config=config)
    except TaskAborted as aborted:
        logger.info("explosion aborted kind=%s reason=%s", aborted.kind, aborted.reason)
        return {
            "status": aborted.kind,
            "task_id": task_id,
            "message": aborted.reason,
            "summary": aborted.reason,
            "download": {"available": False},
            "thinking_events": list(control.events) if control else [],
            "orchestrator": "langgraph",
        }

    if final.get("status") == "FAILED_NO_FEATURES":
        return {
            "status": "FAILED_NO_FEATURES",
            "task_id": task_id,
            "message": final.get("message") or "特征为空",
            "summary": final.get("message") or "特征为空",
            "download": {"available": False},
            "features": final.get("features"),
            "thinking_events": list(control.events) if control else [],
            "orchestrator": "langgraph",
        }

    result = dict(final.get("result") or {})
    if not result:
        result = {
            "status": final.get("status") or "REPORT_READY",
            "task_id": task_id,
            "summary": final.get("summary") or "",
            "candidates": final.get("candidates") or [],
            "download": (final.get("report_files") or {}).get("download")
            or {"available": False},
            "orchestrator": "langgraph",
        }

    result["thinking_events"] = list(control.events) if control else []
    context["ranked"] = final.get("ranked")
    context["council"] = {
        "plan": final.get("plan"),
        "sources": final.get("council_sources"),
    }
    context["report"] = final.get("report_files")
    return result

