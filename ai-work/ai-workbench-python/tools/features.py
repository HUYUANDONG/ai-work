"""
特征查询 Tool。

筛选主路径一次批量拉取；单品深挖用 get_product_features。
"""

from __future__ import annotations

from typing import Any

from harness.runtime import AppRuntime


async def query_features(
    runtime: AppRuntime,
    *,
    on_sale_only: bool = True,
    sku_ids: list[str] | None = None,
    category_id: str | None = None,
    stat_date: str | None = None,
    user_id: str | None = None,
    time_window_days: int | None = None,
    profile: str = "score",
) -> dict[str, Any]:
    """
    封装 Java ``POST /internal/features/query``（默认 profile=score）。

    Args:
        runtime: AppRuntime。
        on_sale_only: 是否仅在售。
        sku_ids: 质检批量 SKU（上限 50）。
        category_id: 可选类目过滤。
        stat_date: 统计日。
        user_id: 用来取电商登录态。
        time_window_days: 当前窗口天数。
        profile: 投影档，选品阶段固定 ``score``。

    Returns:
        dict[str, Any]: 特征响应。
    """
    body: dict[str, Any] = {"on_sale_only": on_sale_only, "profile": profile or "score"}
    if sku_ids is not None:
        body["sku_ids"] = sku_ids[:50]
    if category_id is not None:
        body["category_id"] = category_id
    if stat_date is not None:
        body["stat_date"] = stat_date
    if user_id:
        body["user_id"] = user_id
    if time_window_days is not None:
        body["time_window_days"] = int(time_window_days)
    return await runtime.java_client.query_features(body)


async def query_advise_context(
    runtime: AppRuntime,
    *,
    user_id: str,
    sku_ids: list[str] | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """
    建议阶段辅源：``POST /internal/features/advise``（日板块 + 可选大盘）。

    Args:
        runtime: AppRuntime。
        user_id: 电商登录态用户。
        sku_ids: 槽位 SKU。
        days: 回看天数。

    Returns:
        dict: plates / store / source。
    """
    body: dict[str, Any] = {
        "user_id": user_id,
        "days": max(1, int(days)),
    }
    if sku_ids:
        body["sku_ids"] = [str(x) for x in sku_ids[:10]]
    return await runtime.java_client.query_advise(body)


async def get_product_features(
    runtime: AppRuntime,
    sku_id: str,
    *,
    stat_date: str | None = None,
) -> dict[str, Any]:
    """
    单品深挖特征。

    Args:
        runtime: AppRuntime。
        sku_id: SKU。
        stat_date: 可选统计日。

    Returns:
        dict: snapshot_date / item。
    """
    return await runtime.java_client.get_product_features(sku_id, stat_date=stat_date)

