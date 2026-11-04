"""任务生命周期 Tool：claim / heartbeat / complete / fail。"""

from __future__ import annotations

from typing import Any

from clients.java_client import WORKFLOW_VERSION
from harness.runtime import AppRuntime


async def claim_task(
    runtime: AppRuntime,
    *,
    task_types: list[str] | None = None,
    worker_id: str = "py-worker",
) -> dict[str, Any] | None:
    """
    向 Java 领取任务。

    Args:
        runtime: AppRuntime。
        task_types: 支持的类型。
        worker_id: Worker 标识。

    Returns:
        dict | None: 任务载荷。
    """
    types = task_types or ["EXPLOSION", "QUALITY"]
    return await runtime.java_client.claim_task(
        task_types=types,
        workflow_version=WORKFLOW_VERSION,
        worker_id=worker_id,
    )


async def heartbeat_task(
    runtime: AppRuntime,
    task_id: str,
    *,
    lease_token: str,
    progress: str = "",
) -> dict:
    """
    续租心跳。

    Returns:
        dict: cancel_requested / pause_requested 等控制位。
    """
    return await runtime.java_client.heartbeat(
        task_id, lease_token=lease_token, progress=progress
    )


async def complete_task(
    runtime: AppRuntime,
    task_id: str,
    *,
    lease_token: str,
    summary: str = "",
    result_meta: dict[str, Any] | None = None,
) -> None:
    """标记成功。"""
    await runtime.java_client.complete_task(
        task_id,
        lease_token=lease_token,
        summary=summary,
        result_meta=result_meta,
    )


async def fail_task(
    runtime: AppRuntime,
    task_id: str,
    *,
    lease_token: str,
    error_code: str,
    message: str,
    extra: dict[str, Any] | None = None,
) -> None:
    """
    标记失败 / 暂停 / 取消。

    Args:
        runtime: AppRuntime。
        task_id: 任务 ID。
        lease_token: 租约。
        error_code: 错误码（含 PAUSED / CANCELLED）。
        message: 说明。
        extra: 额外写入 fail_body 的字段（如 graph_thread_id）。
    """
    await runtime.java_client.fail_task(
        task_id,
        lease_token=lease_token,
        error_code=error_code,
        message=message,
        extra=extra,
    )

