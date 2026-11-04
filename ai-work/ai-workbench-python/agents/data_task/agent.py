"""
DataTaskAgent：按需拉营销特征 / 商品详情 / 评论 / 库存。

商品/评论/库存底层可 mock。
"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from harness.runtime import AppRuntime
from schemas.agent import AgentResult
from tools import catalog
from tools.features import query_advise_context, query_features


class DataTaskAgent(BaseAgent):
    """拉数任务叶子。"""

    def __init__(self, *, timeout: float | None = 45.0) -> None:
        super().__init__(name="data_task", timeout=timeout)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        runtime: AppRuntime = kwargs["runtime"]
        task = str(kwargs.get("task") or "marketing_features").strip().lower()
        data: dict[str, Any] = {"task": task}

        if task == "marketing_features":
            features = await query_features(
                runtime,
                on_sale_only=bool(kwargs.get("on_sale_only", True)),
                user_id=str(kwargs.get("user_id") or ""),
                time_window_days=int(kwargs.get("time_window_days") or 30),
                category_id=kwargs.get("category_id"),
            )
            data["features"] = features
            data["item_count"] = len(features.get("items") or [])
        elif task == "advise_context":
            advise = await query_advise_context(
                runtime,
                user_id=str(kwargs.get("user_id") or ""),
                sku_ids=list(kwargs.get("sku_ids") or []),
                days=int(kwargs.get("days") or 7),
            )
            data["advise_context"] = advise
        elif task == "product_bundle":
            # 文案用：详情 + 评论
            sku_ids = [str(x) for x in (kwargs.get("sku_ids") or [])][:5]
            bundles = []
            for sid in sku_ids:
                detail = await catalog.get_product_detail(runtime, sid)
                reviews = await catalog.get_product_reviews(runtime, sid, limit=5)
                bundles.append(
                    {
                        "sku_id": sid,
                        "detail": detail,
                        "reviews": reviews.get("reviews") or [],
                    }
                )
            data["bundles"] = bundles
        elif task == "inventory":
            sku_ids = [str(x) for x in (kwargs.get("sku_ids") or [])][:50]
            data["inventory"] = await catalog.get_inventory_policy(runtime, sku_ids)
        else:
            return AgentResult(
                agent_name=self.name,
                success=False,
                error=f"unknown data task: {task}",
                source="error",
            )

        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.9,
            data=data,
            source="mock" if getattr(runtime.java_client, "mock_features", True) else "http",
        )
