"""
FastAPI 启动入口（只负责 create_app，不含业务）。

启动::

    python -m app.main

Windows 上必须先切到 SelectorEventLoop，否则 psycopg 异步连不上 Postgres。

分层对照 Nest::

    api/controllers  ≈  Controller
    services         ≈  Service
    schemas          ≈  DTO
    core             ≈  ConfigModule
    agents           ≈  领域能力（LangGraph 专家，不是 HTTP）
    clients / db     ≈  Infrastructure
    harness          ≈  AppRuntime（共享依赖）+ 任务路由

浏览器 → Gateway → Java → 本服务 /internal/*
"""

from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI

from api.router import api_router
from app.lifespan import lifespan


def create_app() -> FastAPI:
    """
    工厂方法：组装 lifespan + 路由。

    Returns:
        FastAPI: ASGI 应用。
    """
    application = FastAPI(
        title="ai-workbench-python",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(api_router)
    return application


app = create_app()

if __name__ == "__main__":
    import uvicorn

    # uvicorn 在 Windows 上硬编码 ProactorEventLoop，psycopg 连不上 Postgres。
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        loop="app.win_loop:selector_loop_factory",
    )

