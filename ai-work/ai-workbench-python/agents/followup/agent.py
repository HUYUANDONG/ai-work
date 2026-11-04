"""报告追问叶子：包装 answer_followup。"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from agents.followup.answer import answer_followup
from harness.runtime import AppRuntime
from schemas.agent import AgentResult


class FollowupAgent(BaseAgent):
    """会话报告追问叶子。"""

    def __init__(self, *, timeout: float | None = 60.0) -> None:
        super().__init__(name="followup", timeout=timeout)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        runtime: AppRuntime = kwargs["runtime"]
        out = await answer_followup(
            runtime,
            conversation_id=str(kwargs.get("conversation_id") or ""),
            user_id=str(kwargs.get("user_id") or ""),
            message=str(kwargs.get("message") or ""),
            history=kwargs.get("history"),
        )
        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.75,
            data=dict(out),
            source=str(out.get("source") or "followup"),
        )
