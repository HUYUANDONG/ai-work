"""
任务侧配套：Checkpoint、按 task_type 代码路由、AppRuntime。

AppRuntime = 共享依赖盒，不是业界「Agent Harness 产品」的全称实现。
跨任务指挥不做；Explosion 会签见 agents.explosion。
"""

from harness.router import route_task
from harness.runtime import AppRuntime

__all__ = ["AppRuntime", "route_task"]

