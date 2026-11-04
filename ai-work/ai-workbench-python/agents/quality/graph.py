"""Quality 入口：LangGraph 编排（支持断点续跑）。"""

from __future__ import annotations

import logging
from typing import Any

from agents.quality.lg_graph import get_quality_app
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
    质检图 thread_id（与 Explosion 共用 ``graph_thread_id`` 字段）。

    Args:
        context: 任务上下文。
        task_id: 当前任务 ID。

    Returns:
        str: Checkpointer thread。
    """
    task_input = dict(context.get("input") or {})
    thread = str(task_input.get("graph_thread_id") or "").strip()
    if thread:
        return thread
    # 兼容旧前缀，但新任务用稳定 id（不再强制 quality- 前缀换号）
    return f"quality-{task_id}"


def _is_checkpoint_resume(context: dict[str, Any]) -> bool:
    task_input = dict(context.get("input") or {})
    flag = task_input.get("resume_from_checkpoint")
    if flag is True or str(flag).lower() in {"1", "true", "yes"}:
        return True
    return str(context.get("next_action") or "").upper() == "RESUME"


async def run_quality(
    context: dict[str, Any],
    runtime: AppRuntime,
) -> dict[str, Any]:
    """
    执行质检任务（LangGraph）。

    Args:
        context: task_id / input / conversation_id / user_id。
        runtime: AppRuntime。

    Returns:
        dict: QUALITY_READY 或失败 / PAUSED / CANCELLED。
    """
    task_id = str(context.get("task_id") or "unknown-task")
    task_input = dict(context.get("input") or {})
    thread_id = _graph_thread_id(context, task_id)
    resume = _is_checkpoint_resume(context)
    control = _make_control(context, runtime)
    app = get_quality_app()
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
                    "quality resume has no pending nodes thread=%s; fallback full run",
                    thread_id,
                )
                resume = False
            else:
                logger.info(
                    "quality resume thread=%s next=%s task_id=%s",
                    thread_id,
                    pending,
                    task_id,
                )
                final = await app.ainvoke(None, config=config)

        if not resume:
            initial = {
                "task_id": task_id,
                "conversation_id": context.get("conversation_id") or "mock-conversation",
                "user_id": context.get("user_id") or "mock-user",
                "task_input": task_input,
                "status": "RUNNING",
            }
            final = await app.ainvoke(initial, config=config)
    except TaskAborted as aborted:
        logger.info(
            "quality aborted kind=%s reason=%s thread=%s",
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
            "orchestrator": "langgraph",
        }
    result = dict(final.get("result") or final)
    result["graph_thread_id"] = thread_id
    return result
