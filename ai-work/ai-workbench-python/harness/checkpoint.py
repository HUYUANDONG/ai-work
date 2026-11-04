"""
LangGraph Checkpointer 工厂。

Worker 走 ``ainvoke``，必须用 AsyncPostgresSaver，不能用同步 PostgresSaver
（``aget_tuple`` 未实现会直接 NotImplementedError）。
``from_conn_string()`` 是上下文管理器，不能丢给 ``compile()``。
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver

from core.config import Settings, get_settings

logger = logging.getLogger("uvicorn.error")

_saver: BaseCheckpointSaver | None = None
_pool: Any = None


def get_checkpointer(settings: Settings | None = None) -> BaseCheckpointSaver:
    """
    返回已初始化的 Checkpointer。

    尚未 ``init_checkpointer`` 时用内存 saver（单测）。

    Args:
        settings: 未使用，保留签名。

    Returns:
        BaseCheckpointSaver: 进程内单例。
    """
    global _saver
    if _saver is None:
        _ = settings
        _saver = InMemorySaver()
        logger.info("using InMemorySaver for LangGraph checkpoint")
    return _saver


async def init_checkpointer(settings: Settings | None = None) -> BaseCheckpointSaver:
    """
    在事件循环里创建 Checkpointer。有 Postgres URL 则用 AsyncPostgresSaver。

    Args:
        settings: 可选配置。

    Returns:
        BaseCheckpointSaver: 可供 ``compile(checkpointer=...)`` 的实例。
    """
    global _saver, _pool
    if _saver is not None and _pool is not None:
        return _saver

    cfg = settings or get_settings()
    url = (cfg.checkpoint_database_url or "").strip()
    logger.info("event loop=%s", type(asyncio.get_running_loop()).__name__)
    if url:
        try:
            _saver = await _build_async_postgres_saver(url)
            logger.info("using AsyncPostgresSaver for LangGraph checkpoint")
            return _saver
        except Exception:
            logger.exception(
                "Postgres checkpointer unavailable; falling back to InMemorySaver"
            )
            if _pool is not None:
                with suppress(Exception):
                    await _pool.close()
                _pool = None

    if _saver is None:
        _saver = InMemorySaver()
        logger.info("using InMemorySaver for LangGraph checkpoint")
    return _saver


async def close_checkpointer() -> None:
    """关闭 Postgres 连接池。"""
    global _saver, _pool
    pool = _pool
    _pool = None
    _saver = None
    if pool is not None:
        await pool.close()


async def _build_async_postgres_saver(url: str) -> BaseCheckpointSaver:
    """
    用异步连接池构造 AsyncPostgresSaver。

    Args:
        url: ``postgresql://`` 或 ``postgresql+asyncpg://``。

    Returns:
        AsyncPostgresSaver: 已 setup。
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    conninfo = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    global _pool
    _pool = AsyncConnectionPool(
        conninfo=conninfo,
        min_size=1,
        max_size=4,
        timeout=15,
        open=False,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
            "connect_timeout": 10,
        },
    )
    await _pool.open()
    saver = AsyncPostgresSaver(conn=_pool)
    await saver.setup()
    return saver
