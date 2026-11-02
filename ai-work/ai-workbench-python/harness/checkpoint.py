"""
LangGraph Checkpointer 工厂。

默认 MemorySaver（进程内可续跑）；配置了 Postgres URL 则用官方 AsyncPostgresSaver。
"""

from __future__ import annotations

import logging
from typing import Any

from core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_memory_saver: Any = None


def get_checkpointer(settings: Settings | None = None) -> Any:
    """
    返回 LangGraph Checkpointer。

    Args:
        settings: 可选配置。

    Returns:
        Checkpointer: MemorySaver 或 AsyncPostgresSaver。
    """
    global _memory_saver
    cfg = settings or get_settings()

    if cfg.checkpoint_database_url:
        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            # from_conn_string 返回上下文管理器式工厂；这里用同步 PostgresSaver 更稳
            from langgraph.checkpoint.postgres import PostgresSaver

            saver = PostgresSaver.from_conn_string(cfg.checkpoint_database_url)
            # 新版本可能需要 setup()
            try:
                saver.setup()
            except Exception:
                logger.debug("checkpointer setup skipped/failed", exc_info=True)
            logger.info("using PostgresSaver for LangGraph checkpoint")
            return saver
        except Exception:
            logger.exception(
                "Postgres checkpointer unavailable; falling back to MemorySaver"
            )

    if _memory_saver is None:
        from langgraph.checkpoint.memory import MemorySaver

        _memory_saver = MemorySaver()
        logger.info("using MemorySaver for LangGraph checkpoint")
    return _memory_saver

