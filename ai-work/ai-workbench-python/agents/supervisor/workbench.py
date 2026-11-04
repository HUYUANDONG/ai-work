"""
Supervisor：持有叶子、并行/串行编排。

``WorkbenchSupervisor`` 是进程级中枢（已去掉三会签）。
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from agents.base import BaseAgent
from clients.llm_client import LlmClient
from schemas.agent import AgentResult

if TYPE_CHECKING:
    from harness.runtime import AppRuntime

logger = logging.getLogger(__name__)


class Supervisor:
    """编排中枢：注册并调用叶子 ``BaseAgent``。"""

    def __init__(self, name: str = "supervisor") -> None:
        self.name = name
        self.agents: dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> None:
        key = (agent.name or "").strip()
        if not key:
            raise ValueError("agent.name is required")
        self.agents[key] = agent

    def get_agent(self, name: str) -> BaseAgent:
        key = (name or "").strip()
        if key not in self.agents:
            raise KeyError(f"agent not registered: {name!r}; known={sorted(self.agents)}")
        return self.agents[key]

    def has_agent(self, name: str) -> bool:
        return (name or "").strip() in self.agents

    async def run_agent(self, name: str, **kwargs: Any) -> AgentResult:
        return await self.get_agent(name).run(**kwargs)

    async def run_parallel(
        self,
        *jobs: tuple[str, dict[str, Any]],
    ) -> dict[str, AgentResult]:
        if not jobs:
            return {}

        async def _one(agent_name: str, kwargs: dict[str, Any]) -> tuple[str, AgentResult]:
            return agent_name, await self.run_agent(agent_name, **kwargs)

        pairs = await asyncio.gather(*[_one(n, kw) for n, kw in jobs])
        return {name: result for name, result in pairs}


class WorkbenchSupervisor(Supervisor):
    """
    工作台总指挥。

    叶子：explosion / advise / quality_explain / sku_deep / followup
    """

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        council_llm_enabled: bool = False,
        timeout: float | None = 30.0,
    ) -> None:
        super().__init__(name="workbench")
        from agents.advise.agent import AdviseAgent
        from agents.explosion.agent import ExplosionAgent
        from agents.followup.agent import FollowupAgent
        from agents.quality_explain.agent import QualityExplainAgent
        from agents.sku_deep.agent import SkuDeepAgent

        self.llm = llm
        # 兼容旧配置字段；会签已移除，忽略
        self.council_llm_enabled = bool(council_llm_enabled)
        self.register_agent(ExplosionAgent(llm=llm, timeout=60.0))
        self.register_agent(AdviseAgent(llm=llm, timeout=60.0))
        self.register_agent(QualityExplainAgent(llm=llm, timeout=40.0))
        self.register_agent(SkuDeepAgent(timeout=60.0))
        self.register_agent(FollowupAgent(timeout=60.0))

    @classmethod
    def create(
        cls,
        *,
        llm: LlmClient | None = None,
        council_llm_enabled: bool = False,
    ) -> "WorkbenchSupervisor":
        return cls(llm=llm, council_llm_enabled=council_llm_enabled)

    async def phase_quality_explain(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        result = await self.run_agent("quality_explain", rows=rows, llm=self.llm)
        data = dict(result.data or {})
        return {
            "comments": dict(data.get("comments") or {}),
            "summary": str(data.get("summary") or ""),
            "explain_source": result.source or "template",
            "agent_result": result,
        }

    async def run_explosion(self, **kwargs: Any) -> AgentResult:
        kwargs.setdefault("llm", self.llm)
        return await self.run_agent("explosion", **kwargs)

    async def run_placement_advise(self, **kwargs: Any) -> AgentResult:
        kwargs.setdefault("llm", self.llm)
        return await self.run_agent("advise", **kwargs)

    async def run_advise(self, **kwargs: Any) -> AgentResult:
        kwargs.setdefault("llm", self.llm)
        return await self.run_agent("advise", **kwargs)

    async def run_sku_deep(self, **kwargs: Any) -> AgentResult:
        return await self.run_agent("sku_deep", **kwargs)

    async def run_followup(self, **kwargs: Any) -> AgentResult:
        return await self.run_agent("followup", **kwargs)

    async def run_task(
        self,
        task_type: str,
        context: dict[str, Any],
        runtime: AppRuntime,
    ) -> dict[str, Any]:
        from agents.task_agent import get_task_agent, supported_task_types

        normalized = (task_type or "").strip().upper()
        agent = get_task_agent(normalized)
        if agent is None:
            known = ", ".join(sorted(supported_task_types())) or "(none)"
            raise ValueError(f"unsupported task_type: {task_type!r}; known=[{known}]")
        return await agent.run(context, runtime)


class ExplosionSupervisor(WorkbenchSupervisor):
    """兼容旧 import。"""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        llm_enabled: bool = False,
        timeout: float | None = 30.0,
    ) -> None:
        super().__init__(
            llm=llm,
            council_llm_enabled=llm_enabled,
            timeout=timeout,
        )
