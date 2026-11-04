"""
按 task_type 代码路由到专家 Agent。

查 ``TaskAgent`` 注册表（内置 EXPLOSION / QUALITY）；对话入口不经此路由。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from harness.runtime import AppRuntime

# 兼容旧引用（内置类型；运行时以注册表为准）
SUPPORTED_TASK_TYPES = frozenset({"EXPLOSION", "QUALITY"})


async def route_task(
    task_type: str,
    context: dict[str, Any],
    runtime: AppRuntime,
) -> dict[str, Any]:
    """
    将领取到的任务派发到对应专家入口。

    Args:
        task_type: 已注册的任务类型。
        context: 任务上下文。
        runtime: AppRuntime。

    Returns:
        dict: 专家返回结果。

    Raises:
        ValueError: 未知 task_type。
    """
    # 任务专家也经 Supervisor 派发（内部仍查 TaskAgent 注册表）
    from agents.supervisor import WorkbenchSupervisor

    if not isinstance(getattr(runtime, "supervisor", None), WorkbenchSupervisor):
        runtime.supervisor = WorkbenchSupervisor.create(
            llm=getattr(runtime, "llm_client", None),
            council_llm_enabled=bool(
                getattr(getattr(runtime, "settings", None), "council_llm_enabled", False)
            ),
        )
    return await runtime.supervisor.run_task(task_type, context, runtime)
