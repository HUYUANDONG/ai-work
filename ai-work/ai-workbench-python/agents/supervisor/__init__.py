"""编排中枢：WorkbenchSupervisor + OpsSupervisor。"""

from agents.supervisor.workbench import ExplosionSupervisor, Supervisor, WorkbenchSupervisor

__all__ = [
    "ExplosionSupervisor",
    "OpsSupervisor",
    "PHASE_AWAITING_ADVISE",
    "PHASE_AWAITING_COPY",
    "PHASE_DONE",
    "PHASE_IDLE",
    "Supervisor",
    "WorkbenchSupervisor",
]


def __getattr__(name: str):
    """延迟加载 OpsSupervisor，避免与 explosion 图循环导入。"""
    if name == "OpsSupervisor":
        from agents.supervisor.ops import OpsSupervisor

        return OpsSupervisor
    if name in {
        "PHASE_IDLE",
        "PHASE_AWAITING_ADVISE",
        "PHASE_AWAITING_COPY",
        "PHASE_DONE",
    }:
        from agents.supervisor import ops as _ops

        return getattr(_ops, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
