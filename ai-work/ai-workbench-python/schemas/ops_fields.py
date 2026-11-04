"""
运营特征视图（给 LLM / 报告摘录）。

Java goodsStatList 映射后只下发打分窗口字段；此处从候选行抽出
会签可读的精简视图，禁止塞图片/链接。
"""

from __future__ import annotations

from typing import Any

# 会签可读运营字段（对齐 Java 精简特征 + 少量别名）
_AGENT_OPS_KEYS: tuple[str, ...] = (
    "sku_id",
    "title",
    "brand",
    "gmv_30d",
    "gmv_prev_30d",
    "orders_30d",
    "orders_prev_30d",
    "clicks_30d",
    "clicks_prev_30d",
    "impressions_30d",
    "impressions_prev_30d",
    "paid_orders_from_clicks_30d",
    "rate_per",
    "amount_unit",
)

# 兼容旧 fixture / 未裁剪行
_LEGACY_OPS_KEYS: tuple[str, ...] = (
    "goodsId",
    "goodsName",
    "gbName",
    "supBrandName",
    "orderSales",
    "orderNumbers",
    "orderPays",
    "goodsPv",
    "goodsUv",
)

_ID_FALLBACKS: tuple[str, ...] = ("sku_id", "goodsId", "product_id")
_NAME_FALLBACKS: tuple[str, ...] = ("title", "goodsName")
_BRAND_FALLBACKS: tuple[str, ...] = ("brand", "gbName")


def _merge_item_sources(item: dict[str, Any] | None) -> dict[str, Any]:
    """行字段优先，其次 feature_excerpt / metrics。"""
    if not item:
        return {}
    excerpt = item.get("feature_excerpt")
    metrics = item.get("metrics")
    base: dict[str, Any] = {}
    if isinstance(metrics, dict):
        base.update(metrics)
    if isinstance(excerpt, dict):
        base.update(excerpt)
    top = {
        k: v
        for k, v in item.items()
        if k not in {"feature_excerpt", "metrics", "score_breakdown", "skipped_items"}
    }
    return {**base, **top}


def _first_present(src: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """返回第一个存在且非 null 的值。"""
    for key in keys:
        if key in src and src[key] is not None:
            return src[key]
    return None


def ops_goods_view(item: dict[str, Any] | None) -> dict[str, Any]:
    """
    抽出可喂给模型的精简商品字段。

    Args:
        item: 特征行或报告行（可含 feature_excerpt / metrics）。

    Returns:
        dict: 仅含会签需要的字段；可能为空。
    """
    src = _merge_item_sources(item)
    view: dict[str, Any] = {}
    for key in _AGENT_OPS_KEYS + _LEGACY_OPS_KEYS:
        if key in src and src[key] is not None:
            view[key] = src[key]
    # 统一身份字段，去掉重复别名
    sku = _first_present(src, _ID_FALLBACKS)
    if sku is not None:
        view["sku_id"] = sku
    name = _first_present(src, _NAME_FALLBACKS)
    if name is not None:
        view["title"] = name
    brand = _first_present(src, _BRAND_FALLBACKS)
    if brand is not None:
        view["brand"] = brand
    for drop in (
        "goodsId",
        "goodsName",
        "gbName",
        "supBrandName",
        "supplier_brand",
        "goodsFirstPic",
        "goodsLink",
        "orderSales",
        "orderNumbers",
        "orderPays",
        "goodsPv",
        "goodsUv",
        "ratePer",
        "statDay",
    ):
        view.pop(drop, None)
    return view


def slim_ops_excerpt(item: dict[str, Any] | None) -> dict[str, Any]:
    """报告落库用的运营字段摘录（同 ops_goods_view）。"""
    return ops_goods_view(item)


# 兼容旧 import
GOODS_STAT_KEYS: tuple[str, ...] = _AGENT_OPS_KEYS
