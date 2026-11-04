"""投放建议叶子（唯一）：LLM 写建议，失败模板兜底。"""

from __future__ import annotations

from typing import Any

from agents.advise.llm import write_placement_advise
from agents.base import BaseAgent
from clients.llm_client import LlmClient
from schemas.agent import AgentResult


class AdviseAgent(BaseAgent):
    """投放建议叶子。"""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        timeout: float | None = 60.0,
    ) -> None:
        super().__init__(name="advise", timeout=timeout)
        self.llm = llm

    async def _execute(self, **kwargs: Any) -> AgentResult:
        written = await write_placement_advise(
            candidates=list(kwargs.get("candidates") or []),
            advise_context=dict(kwargs.get("advise_context") or {}),
            llm=kwargs.get("llm") or self.llm,
            goal_mode=str(kwargs.get("goal_mode") or "GMV"),
            on_delta=kwargs.get("on_delta"),
        )
        text = str(written.get("text") or "").strip()
        return AgentResult(
            agent_name=self.name,
            success=bool(text),
            confidence=0.85 if str(written.get("source") or "").startswith("llm") else 0.6,
            data={"text": text, **written},
            source=str(written.get("source") or "template"),
        )


# 兼容旧类名
PlacementAdviseAgent = AdviseAgent
