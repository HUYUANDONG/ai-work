"""
爆品任务应用服务。

正式由 Worker + router 调用；dev Controller 可直接跑完整筛选+报表。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from agents.explosion.graph import run_explosion
from harness.runtime import AppRuntime


class ExplosionService:
    """爆品作战用例服务。"""

    def __init__(self, runtime: AppRuntime) -> None:
        """
        Args:
            runtime: 进程共享 AppRuntime。
        """
        self._runtime = runtime

    async def run_pipeline(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        拉特征 → 打分挂标 → 生成可下载报表。

        Args:
            body: 可选 task_id / run_id / input。

        Returns:
            dict[str, Any]: REPORT_READY 等。
        """
        task_input = body.get("input") or {
            "time_window_days": 30,
            "goal_mode": "GMV",
            "focus_slots": 5,
            "top_n": 20,
            "on_sale_only": True,
        }
        context = {
            "task_id": body.get("task_id") or f"dev-{uuid4().hex[:12]}",
            "run_id": body.get("run_id") or f"run-{uuid4().hex[:8]}",
            "conversation_id": body.get("conversation_id") or "mock-conversation",
            "user_id": body.get("user_id") or "mock-user",
            "input": task_input,
        }
        return await run_explosion(context, self._runtime)

    # 兼容旧方法名
    async def run_load_features_step(self, body: dict[str, Any]) -> dict[str, Any]:
        """旧名：现已跑完整 pipeline。"""
        return await self.run_pipeline(body)

    def resolve_report_file(self, task_id: str) -> Path | None:
        """
        查找已生成的 HTML 报表。

        Args:
            task_id: 任务 ID。

        Returns:
            Path | None: 存在则返回路径。
        """
        path = self._runtime.report_dir() / f"{task_id}.html"
        return path if path.is_file() else None

