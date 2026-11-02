"""
异步 SQLAlchemy 引擎与 Session 工厂。

供 FastAPI lifespan 与 Worker 进程共用；用于健康检查与后续 Checkpointer 连接复用。
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings | None = None) -> None:
    """
    初始化全局 AsyncEngine 与 sessionmaker。

    Args:
        settings: 可选配置；为空时使用 get_settings()。

    Raises:
        ValueError: 未配置 WB_CHECKPOINT_DATABASE_URL。
    """
    global _engine, _session_factory

    cfg = settings or get_settings()
    if not cfg.checkpoint_database_url:
        raise ValueError("WB_CHECKPOINT_DATABASE_URL is required")

    if _engine is not None:
        return

    _engine = create_async_engine(
        cfg.checkpoint_database_url,
        pool_pre_ping=True,
        echo=cfg.profile == "local",
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


async def close_db() -> None:
    """关闭全局引擎并清空 session 工厂。"""
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    产出一个 AsyncSession（FastAPI Depends 可用）。

    Yields:
        AsyncSession: 数据库会话。

    Raises:
        RuntimeError: 引擎尚未 init_db。
    """
    if _session_factory is None:
        raise RuntimeError("database is not initialized; call init_db() first")

    async with _session_factory() as session:
        yield session


async def ping_db() -> bool:
    """
    执行 ``SELECT 1`` 探测连接。

    Returns:
        bool: 连通返回 True，否则 False（不抛异常）。
    """
    if _session_factory is None:
        return False

    try:
        async with _session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
