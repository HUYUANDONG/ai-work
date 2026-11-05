"""
运行时配套：Checkpoint 与 AppRuntime。

注意：本包 ``__init__`` 不做急切导入，避免
``clients.* → harness.resilience → harness.__init__ → runtime → clients`` 环依赖。
"""

from __future__ import annotations

from typing import Any

__all__ = ["AppRuntime"]


def __getattr__(name: str) -> Any:
    """按需导出，保持 ``from harness import AppRuntime`` 可用。"""
    if name == "AppRuntime":
        from harness.runtime import AppRuntime

        return AppRuntime
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
