"""库存 Agent：预警与限购（数据来自 DataTask / mock）。"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from schemas.agent import AgentResult


class InventoryAgent(BaseAgent):
    """库存策略叶子。"""

    def __init__(self, *, timeout: float | None = 15.0) -> None:
        super().__init__(name="inventory", timeout=timeout)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        inventory = dict(kwargs.get("inventory") or {})
        items = list(inventory.get("items") or [])
        warnings = [x for x in items if str(x.get("warning") or "OK") != "OK"]
        lines = []
        for w in warnings[:8]:
            lines.append(
                f"- {w.get('sku_id')}: {w.get('warning')} "
                f"库存={w.get('stock_qty')} 限购={w.get('purchase_limit')} "
                f"（{w.get('rationale')}）"
            )
        summary = (
            "\n".join(lines)
            if lines
            else "焦点商品库存整体健康，暂无强预警。"
        )
        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.9,
            data={
                "items": items,
                "warning_count": len(warnings),
                "summary": summary,
            },
            source=str(inventory.get("source") or "inventory"),
        )
