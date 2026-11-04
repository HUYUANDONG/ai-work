"""
任务侧配套：Checkpoint、按 task_type 代码路由、AppRuntime。

AppRuntime = 共享依赖盒，不是业界「Agent Harness 产品」的全称实现。
跨任务指挥不做；Explosion 会签见 agents.explosion。

注意：本包 ``__init__`` 不做急切导入，避免
``clients.* → harness.resilience → harness.__init__ → runtime → clients`` 环依赖。
"""

from __future__ import annotations

from typing import Any

__all__ = ["AppRuntime", "route_task"]


def __getattr__(name: str) -> Any:
    """按需导出，保持 ``from harness import AppRuntime`` 可用。"""
    if name == "AppRuntime":
        from harness.runtime import AppRuntime

        return AppRuntime
    if name == "route_task":
        from harness.router import route_task

        return route_task
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
