"""
任务控制：推送思考过程、协作式暂停/取消。

Java 负责把 progress 事件 SSE 给前端，并维护追问排队。
Python Worker 每步上报 thinking，心跳时读取 cancel/pause。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from harness.runtime import AppRuntime

logger = logging.getLogger(__name__)


class TaskAborted(Exception):
    """用户暂停或取消。"""

    def __init__(self, reason: str, *, kind: str = "CANCELLED") -> None:
        super().__init__(reason)
        self.reason = reason
        self.kind = kind  # CANCELLED | PAUSED


EmitFn = Callable[[dict[str, Any]], Awaitable[None]]
CheckFn = Callable[[], Awaitable[dict[str, Any]]]


@dataclass
class TaskControl:
    """
    单个任务的思考流与中断检查。

    Attributes:
        task_id: 任务 ID。
        lease_token: 租约。
        runtime: AppRuntime。
        events: 本地已发出的事件（便于返回/mock）。
    """

    task_id: str
    lease_token: str
    runtime: AppRuntime
    events: list[dict[str, Any]] = field(default_factory=list)
    _seq: int = 0

    async def emit(
        self,
        stage: str,
        title: str,
        *,
        detail: str = "",
        data: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> None:
        """
        上报一步思考（Java 转发给前端展示）。

        Args:
            stage: 机器可读阶段，如 load_features / signal / revise。
            title: 用户可见短标题。
            detail: 可选说明。
            data: 可选结构化摘要（勿塞全量 SKU 特征）。
            visible: 是否给用户看（内部步骤可 false）。
        """
        self._seq += 1
        event = {
            "seq": self._seq,
            "task_id": self.task_id,
            "stage": stage,
            "title": title,
            "detail": detail,
            "data": data or {},
            "visible": visible,
            "at": datetime.now(timezone.utc).isoformat(),
        }
        self.events.append(event)
        try:
            await self.runtime.java_client.post_task_progress(
                self.task_id,
                lease_token=self.lease_token,
                event=event,
            )
        except Exception:
            logger.exception("post_task_progress failed task_id=%s", self.task_id)

    async def checkpoint(self, progress: str = "") -> dict[str, Any]:
        """
        心跳并读取取消/暂停标志。

        Returns:
            dict: cancel_requested / pause_requested / queue_depth 等。

        Raises:
            TaskAborted: 用户要求停止。
        """
        ctrl = await self.runtime.java_client.heartbeat(
            self.task_id,
            lease_token=self.lease_token,
            progress=progress,
        )
        if ctrl.get("cancel_requested"):
            await self.emit(
                "cancelled",
                "已取消分析",
                detail=str(ctrl.get("cancel_reason") or "用户取消"),
            )
            raise TaskAborted(
                str(ctrl.get("cancel_reason") or "用户取消"),
                kind="CANCELLED",
            )
        if ctrl.get("pause_requested"):
            await self.emit(
                "paused",
                "已暂停分析",
                detail=str(ctrl.get("pause_reason") or "用户暂停"),
            )
            raise TaskAborted(
                str(ctrl.get("pause_reason") or "用户暂停"),
                kind="PAUSED",
            )
        return ctrl

