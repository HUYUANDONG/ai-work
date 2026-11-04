"""
推荐 Agent：正式爆品排序用代码规则（scoring），不用 LLM 算分。

复杂指标（趋势/转化/价格/利润）在 scoring/ 可解释加权。
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from schemas.agent import AgentResult
from scoring.pipeline import rank_candidates


class RecommendAgent(BaseAgent):
    """爆品列表叶子（代码排序）。"""

    def __init__(self, *, timeout: float | None = 15.0) -> None:
        super().__init__(name="recommend", timeout=timeout)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        items = list(kwargs.get("items") or [])
        top_n = int(kwargs.get("top_n") or 10)
        ranked = rank_candidates(items, top_n=top_n)
        candidates = list(ranked.get("candidates") or [])
        # 默认前 focus_slots 进槽，供建议/文案使用
        focus_slots = int(kwargs.get("focus_slots") or 5)
        for i, row in enumerate(candidates):
            row["in_focus_slot"] = i < max(1, focus_slots)
        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.95,
            data={
                "candidates": candidates,
                "pool_size": ranked.get("pool_size"),
                "scoring_version": ranked.get("scoring_version"),
                "top_n": ranked.get("top_n"),
            },
            source="scoring_rules",
        )
