"""
商品详情 / 评论 / 库存策略 Tool（底层可 mock）。
"""

from __future__ import annotations

from typing import Any

from harness.runtime import AppRuntime


async def get_product_detail(runtime: AppRuntime, sku_id: str) -> dict[str, Any]:
    """商品详情。"""
    return await runtime.java_client.get_product_detail(sku_id)


async def get_product_reviews(
    runtime: AppRuntime,
    sku_id: str,
    *,
    limit: int = 5,
) -> dict[str, Any]:
    """商品评论。"""
    return await runtime.java_client.get_product_reviews(sku_id, limit=limit)


async def get_inventory_policy(
    runtime: AppRuntime,
    sku_ids: list[str],
) -> dict[str, Any]:
    """库存预警与限购。"""
    return await runtime.java_client.get_inventory_policy(sku_ids)
