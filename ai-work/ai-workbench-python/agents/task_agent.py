"""
任务专家注册表：按 ``task_type`` 派发到 LangGraph 入口。

新专家：实现 ``TaskAgent``（或 ``CallableTaskAgent``）并 ``register_task_agent``，
不必再改 ``route_task`` 的 if/else。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.runtime import AppRuntime

TaskRunner = Callable[[dict[str, Any], Any], Awaitable[dict[str, Any]]]

_REGISTRY: dict[str, "TaskAgent"] = {}
_BUILTINS_LOADED = False


class TaskAgent(ABC):
    """
    Worker 侧任务专家契约（整图入口，不是叶子 BaseAgent）。

    Attributes:
        task_type: 如 EXPLOSION / QUALITY。
    """

    task_type: str

    @abstractmethod
    async def run(
        self,
        context: dict[str, Any],
        runtime: AppRuntime,
    ) -> dict[str, Any]:
        """执行任务并返回 Worker 可识别的结果字典。"""


class CallableTaskAgent(TaskAgent):
    """用已有 ``async def run_*(context, runtime)`` 包装成 TaskAgent。"""

    def __init__(self, task_type: str, runner: TaskRunner) -> None:
        self.task_type = task_type.strip().upper()
        self._runner = runner

    async def run(
        self,
        context: dict[str, Any],
        runtime: AppRuntime,
    ) -> dict[str, Any]:
        return await self._runner(context, runtime)


def register_task_agent(agent: TaskAgent) -> None:
    """注册或覆盖某个 ``task_type``。"""
    key = (agent.task_type or "").strip().upper()
    if not key:
        raise ValueError("task_type is required")
    _REGISTRY[key] = agent


def get_task_agent(task_type: str) -> TaskAgent | None:
    """按类型查找；未注册返回 None。"""
    ensure_builtin_task_agents()
    return _REGISTRY.get((task_type or "").strip().upper())


def supported_task_types() -> frozenset[str]:
    """当前已注册的任务类型。"""
    ensure_builtin_task_agents()
    return frozenset(_REGISTRY)


def ensure_builtin_task_agents() -> None:
    """幂等注册 V1 内置 EXPLOSION / QUALITY。"""
    global _BUILTINS_LOADED
    if _BUILTINS_LOADED:
        return
    from agents.explosion.graph import run_explosion
    from agents.quality.graph import run_quality

    register_task_agent(CallableTaskAgent("EXPLOSION", run_explosion))
    register_task_agent(CallableTaskAgent("QUALITY", run_quality))
    _BUILTINS_LOADED = True


def reset_task_agent_registry_for_tests() -> None:
    """仅测试：清空注册表。"""
    global _BUILTINS_LOADED
    _REGISTRY.clear()
    _BUILTINS_LOADED = False
