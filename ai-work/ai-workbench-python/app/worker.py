"""
Worker：领取 → 推送思考 → 可暂停取消 → complete / fail。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from core.config import get_settings
from db.session import close_db, init_db
from harness.checkpoint import close_checkpointer, init_checkpointer
from harness.router import route_task
from harness.runtime import AppRuntime
from harness.task_control import TaskAborted
from tools.tasks import claim_task, complete_task, fail_task, heartbeat_task

logger = logging.getLogger("uvicorn.error")


async def poll_once(runtime: AppRuntime) -> dict[str, Any] | None:
    """领取一条可执行任务。"""
    return await claim_task(runtime, worker_id="py-worker")


async def execute_claimed(runtime: AppRuntime, task: dict[str, Any]) -> dict[str, Any]:
    """执行已领取任务并 complete/fail；支持 CANCELLED / PAUSED。"""
    task_id = str(task.get("task_id") or "")
    lease = str(task.get("lease_token") or "")
    task_type = str(task.get("task_type") or "")

    try:
        await heartbeat_task(runtime, task_id, lease_token=lease, progress="running")
        result = await route_task(task_type, task, runtime)
        status = str(result.get("status") or "")

        if status in {"CANCELLED", "PAUSED"}:
            extra: dict[str, Any] = {}
            if result.get("graph_thread_id"):
                extra["graph_thread_id"] = result["graph_thread_id"]
            if result.get("paused_at"):
                extra["paused_at"] = result["paused_at"]
            if result.get("resume_mode"):
                extra["resume_mode"] = result["resume_mode"]
            await fail_task(
                runtime,
                task_id,
                lease_token=lease,
                error_code=status,
                message=str(result.get("message") or status),
                extra=extra or None,
            )
            return result

        if status.startswith("FAILED"):
            await fail_task(
                runtime,
                task_id,
                lease_token=lease,
                error_code=status,
                message=str(result.get("message") or status),
            )
            return result

        summary = str(result.get("summary") or result.get("message") or "")
        result_meta: dict[str, Any] = {}
        if result.get("download"):
            result_meta["download"] = result["download"]
        if result.get("thinking_events"):
            result_meta["thinking_event_count"] = len(result["thinking_events"])
        await complete_task(
            runtime,
            task_id,
            lease_token=lease,
            summary=summary,
            result_meta=result_meta,
        )
        return result
    except TaskAborted as aborted:
        logger.info("task aborted task_id=%s kind=%s", task_id, aborted.kind)
        task_input = dict(task.get("input") or {})
        thread = str(task_input.get("graph_thread_id") or task_id)
        await fail_task(
            runtime,
            task_id,
            lease_token=lease,
            error_code=aborted.kind,
            message=aborted.reason,
            extra={
                "graph_thread_id": thread,
                "paused_at": getattr(aborted, "progress", "") or "",
                "resume_mode": "checkpoint",
            },
        )
        return {
            "status": aborted.kind,
            "task_id": task_id,
            "graph_thread_id": thread,
            "message": aborted.reason,
        }
    except Exception as exc:
        logger.exception("task failed task_id=%s task_type=%s", task_id, task_type)
        try:
            detail = str(exc).strip() or type(exc).__name__
            await fail_task(
                runtime,
                task_id,
                lease_token=lease,
                error_code="WORKER_EXCEPTION",
                message=f"{type(exc).__name__}: {detail}",
            )
        except Exception:
            logger.exception("fail_task callback failed task_id=%s", task_id)
        raise


async def run_worker_loop(*, runtime: AppRuntime | None = None) -> None:
    """
    Worker 主循环。

    Args:
        runtime: 可选共享运行时；空则本进程自建。
    """
    own_runtime = runtime is None
    settings = runtime.settings if runtime is not None else get_settings()
    if runtime is None:
        runtime = AppRuntime.create(settings)
        if settings.checkpoint_database_url:
            init_db(settings)
        await init_checkpointer(settings)
        # 预编译图，绑定当前进程的 Checkpointer
        from agents.explosion.lg_graph import get_explosion_app
        from agents.quality.lg_graph import get_quality_app

        get_explosion_app()
        get_quality_app()

    logger.info(
        "worker started profile=%s poll=%ss mock_java=%s java=%s",
        settings.profile,
        settings.worker_poll_interval_seconds,
        settings.java_mock_features,
        settings.java_base_url,
    )

    try:
        while True:
            try:
                task = await poll_once(runtime)
            except httpx.ConnectError as exc:
                logger.warning(
                    "claim_task: Java 不可达 %s (%s)",
                    settings.java_base_url,
                    exc,
                )
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                continue
            except Exception:
                logger.exception("claim_task failed")
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                continue
            if task is None:
                await asyncio.sleep(settings.worker_poll_interval_seconds)
                continue
            try:
                await execute_claimed(runtime, task)
            except Exception:
                continue
    finally:
        if own_runtime:
            await close_checkpointer()
            await close_db()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    asyncio.run(run_worker_loop())


if __name__ == "__main__":
    main()

