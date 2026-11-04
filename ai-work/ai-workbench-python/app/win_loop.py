"""Windows 事件循环：uvicorn 默认 Proactor，psycopg 异步必须用 Selector。"""

from __future__ import annotations

import asyncio
import selectors


def selector_loop_factory() -> asyncio.AbstractEventLoop:
    """
    给 uvicorn ``loop=`` 用的工厂，返回 SelectorEventLoop。

    Returns:
        asyncio.AbstractEventLoop: 可供 psycopg 异步连接使用的循环。
    """
    return asyncio.SelectorEventLoop(selectors.SelectSelector())
