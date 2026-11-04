"""
Explosion 入口：调用 LangGraph 编排（会签修订 / checkpoint / 思考流）。

暂停后续跑：复用 ``graph_thread_id``，对同一 Checkpointer ``ainvoke(None)``。
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


def _graph_thread_id(context: dict[str, Any], task_id: str) -> str:
    """
    解析稳定的 LangGraph thread_id。

    Args:
        context: Worker 领取的任务上下文。
        task_id: 当前租约任务 ID。

    Returns:
        str: Checkpointer thread_id（续跑必须与首跑一致）。
    """
    task_input = dict(context.get("input") or {})
    thread = str(task_input.get("graph_thread_id") or "").strip()
    return thread or task_id


def _is_checkpoint_resume(context: dict[str, Any]) -> bool:
    """是否从断点续跑。"""
    task_input = dict(context.get("input") or {})
    flag = task_input.get("resume_from_checkpoint")
    if flag is True or str(flag).lower() in {"1", "true", "yes"}:
        return True
    return str(context.get("next_action") or "").upper() == "RESUME"


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
    thread_id = _graph_thread_id(context, task_id)
    resume = _is_checkpoint_resume(context)
    control = _make_control(context, runtime)
    app = get_explosion_app()

    config = {
        "configurable": {
            "thread_id": thread_id,
            "runtime": runtime,
            "control": control,
        }
    }

    try:
        if resume:
            snapshot = await app.aget_state(config)
            pending = list(snapshot.next or ()) if snapshot else ()
            if not pending:
                logger.warning(
                    "explosion resume has no pending nodes thread=%s; fallback full run",
                    thread_id,
                )
                resume = False
            else:
                logger.info(
                    "explosion resume thread=%s next=%s task_id=%s",
                    thread_id,
                    pending,
                    task_id,
                )
                final = await app.ainvoke(None, config=config)

        if not resume:
            initial = {
                "task_id": task_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "task_input": task_input,
                "status": "RUNNING",
                "next_action": "signal_risk",
            }
            final = await app.ainvoke(initial, config=config)
    except TaskAborted as aborted:
        logger.info(
            "explosion aborted kind=%s reason=%s thread=%s",
            aborted.kind,
            aborted.reason,
            thread_id,
        )
        return {
            "status": aborted.kind,
            "task_id": task_id,
            "graph_thread_id": thread_id,
            "paused_at": getattr(aborted, "progress", "") or "",
            "message": aborted.reason,
            "summary": aborted.reason,
            "download": {"available": False},
            "thinking_events": list(control.events) if control else [],
            "orchestrator": "langgraph",
            "resume_mode": "checkpoint",
        }

    if final.get("status") == "FAILED_NO_FEATURES":
        return {
            "status": "FAILED_NO_FEATURES",
            "task_id": task_id,
            "graph_thread_id": thread_id,
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
    result["graph_thread_id"] = thread_id
    context["ranked"] = final.get("ranked")
    context["explosion"] = {
        "plan": final.get("plan"),
        "source": final.get("explosion_source"),
        "analysis": final.get("explosion_analysis"),
    }
    context["report"] = final.get("report_files")
    return result
