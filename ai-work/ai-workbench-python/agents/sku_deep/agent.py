"""单品深挖叶子：包装 analyze_sku。"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from agents.sku_deep.analyze import analyze_sku
from harness.runtime import AppRuntime
from schemas.agent import AgentResult


class SkuDeepAgent(BaseAgent):
    """单品深挖叶子。"""

    def __init__(self, *, timeout: float | None = 60.0) -> None:
        super().__init__(name="sku_deep", timeout=timeout)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        runtime: AppRuntime = kwargs["runtime"]
        sku_id = str(kwargs.get("sku_id") or "")
        out = await analyze_sku(
            runtime,
            sku_id,
            user_question=str(kwargs.get("user_question") or ""),
        )
        return AgentResult(
            agent_name=self.name,
            success=out.get("source") != "empty",
            confidence=0.75,
            data=out,
            source=str(out.get("source") or "ok"),
        )
