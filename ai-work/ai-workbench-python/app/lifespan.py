"""FastAPI lifespan：启动挂 Runtime，关闭时释放 DB。对话内直接做完分析，不拉起领任务 Worker。"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.config import get_settings
from db.session import close_db, init_db
from harness.checkpoint import close_checkpointer, init_checkpointer
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
    await init_checkpointer(settings)
    from agents.quality.lg_graph import get_quality_app

    get_quality_app()
    logger.info("chat runtime ready")

    try:
        yield
    finally:
        await close_checkpointer()
        await close_db()
