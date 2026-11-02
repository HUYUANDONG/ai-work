"""质检任务应用服务（dev + Worker 共用图）。"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from agents.quality.graph import run_quality
from harness.runtime import AppRuntime


class QualityService:
    """质检用例服务。"""

    def __init__(self, runtime: AppRuntime) -> None:
        """
        Args:
            runtime: AppRuntime。
        """
        self._runtime = runtime

    async def run_pipeline(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        跑质检流水线。

        Args:
            body: task_id / input / conversation_id。

        Returns:
            dict: QUALITY_READY 等。
        """
        task_input = body.get("input") or {
            "sku_ids": None,
            "on_sale_only": True,
            "storewide_problems": True,
            "time_window_days": 30,
        }
        context = {
            "task_id": body.get("task_id") or f"dev-q-{uuid4().hex[:12]}",
            "run_id": body.get("run_id") or f"run-{uuid4().hex[:8]}",
            "conversation_id": body.get("conversation_id") or "mock-conversation",
            "user_id": body.get("user_id") or "mock-user",
            "input": task_input,
        }
        return await run_quality(context, self._runtime)

