"""Quality 入口：LangGraph 编排。"""

from __future__ import annotations

from typing import Any

from agents.quality.lg_graph import get_quality_app
from harness.runtime import AppRuntime


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
        dict: QUALITY_READY 或失败。
    """
    task_id = str(context.get("task_id") or "unknown-task")
    app = get_quality_app()
    initial = {
        "task_id": task_id,
        "conversation_id": context.get("conversation_id") or "mock-conversation",
        "user_id": context.get("user_id") or "mock-user",
        "task_input": dict(context.get("input") or {}),
        "status": "RUNNING",
    }
    config = {
        "configurable": {
            "thread_id": f"quality-{task_id}",
            "runtime": runtime,
        }
    }
    final = await app.ainvoke(initial, config=config)
    if final.get("status") == "FAILED_NO_FEATURES":
        return {
            "status": "FAILED_NO_FEATURES",
            "task_id": task_id,
            "message": final.get("message") or "特征为空",
            "summary": final.get("message") or "特征为空",
            "orchestrator": "langgraph",
        }
    return dict(final.get("result") or final)
