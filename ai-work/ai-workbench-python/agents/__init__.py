"""
Agent 包：叶子按目录分类 + Chat 入口 + Explosion/Quality 专家图。

- 叶子：``decision`` / ``recommend`` / ``advise`` / ``copy`` / …
- 编排：``Supervisor`` / ``WorkbenchSupervisor`` / ``OpsSupervisor``
- 任务专家：``TaskAgent`` 注册表
"""

from agents.base import BaseAgent
from agents.supervisor.ops import OpsSupervisor
from agents.supervisor.workbench import (
    ExplosionSupervisor,
    Supervisor,
    WorkbenchSupervisor,
)
from agents.task_agent import (
    CallableTaskAgent,
    TaskAgent,
    get_task_agent,
    register_task_agent,
    supported_task_types,
)

__all__ = [
    "BaseAgent",
    "CallableTaskAgent",
    "ExplosionSupervisor",
    "OpsSupervisor",
    "Supervisor",
    "TaskAgent",
    "WorkbenchSupervisor",
    "get_task_agent",
    "register_task_agent",
    "supported_task_types",
]
