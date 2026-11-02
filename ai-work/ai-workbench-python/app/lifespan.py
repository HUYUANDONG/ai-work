"""FastAPI lifespan：启动挂 Runtime，顺带拉起 Worker，关闭释放 DB。"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.worker import run_worker_loop
from core.config import get_settings
from db.session import close_db, init_db
from harness.runtime import AppRuntime

logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    应用生命周期。

    Args:
        app: FastAPI 实例；state 上挂 settings / runtime。
    """
    settings = get_settings()
    app.state.settings = settings
    app.state.runtime = AppRuntime.create(settings)

    if settings.checkpoint_database_url:
        init_db(settings)

    worker_task = asyncio.create_task(
        run_worker_loop(runtime=app.state.runtime),
        name="py-worker",
    )
    logger.info("background worker scheduled poll=%ss", settings.worker_poll_interval_seconds)

    try:
        yield
    finally:
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task
        await close_db()
