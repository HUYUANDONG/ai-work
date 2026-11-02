"""FastAPI lifespan：启动挂 Runtime，关闭释放 DB。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.config import get_settings
from db.session import close_db, init_db
from harness.runtime import AppRuntime


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

    try:
        yield
    finally:
        await close_db()
