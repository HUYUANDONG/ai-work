"""已生成爆品 HTML 报表的查找。对话主链不再走这里开跑。"""

from __future__ import annotations

from pathlib import Path

from harness.runtime import AppRuntime


class ExplosionService:
    """报表文件定位。"""

    def __init__(self, runtime: AppRuntime) -> None:
        """
        Args:
            runtime: 进程共享 AppRuntime。
        """
        self._runtime = runtime

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

