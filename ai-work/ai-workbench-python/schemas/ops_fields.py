"""
运营接口字段视图（以 docs/llm-field-glossary.md 为准）。

给 LLM 的数字只允许词典里出现过的商品销量字段。
禁止把内部快照字段（gmv_30d / explosion_score 等）改名冒充接口字段。
缺 key 或 null → 省略，禁止当 0。
"""

from __future__ import annotations

from typing import Any

# 商品销量主源：POST outfit-admin/reportStat/goodsStatList
GOODS_STAT_KEYS: tuple[str, ...] = (
    "goodsId",
    "goodsName",
    "goodsFirstPic",
    "goodsLink",
    "goodsBrandId",
    "gbName",
    "supBrandName",
    "orderSales",
    "orderNumbers",
    "orderPays",
    "goodsPv",
    "goodsUv",
    "ratePer",
    "statDay",
)

# 仅身份可回退；销售额/流量窗口不同，禁止映射
_ID_FALLBACKS: tuple[str, ...] = ("goodsId", "sku_id", "product_id")
_NAME_FALLBACKS: tuple[str, ...] = ("goodsName", "title")


def _merge_item_sources(item: dict[str, Any] | None) -> dict[str, Any]:
    """行字段优先，其次 feature_excerpt。"""
    if not item:
        return {}
    excerpt = item.get("feature_excerpt")
    base = excerpt if isinstance(excerpt, dict) else {}
    top = {k: v for k, v in item.items() if k != "feature_excerpt"}
    return {**base, **top}


def _first_present(src: dict[str, Any], keys: tuple[str, ...]) -> Any:
    """返回第一个存在且非 null 的值。"""
    for key in keys:
        if key in src and src[key] is not None:
            return src[key]
    return None


def ops_goods_view(item: dict[str, Any] | None) -> dict[str, Any]:
    """
    抽出可喂给模型的商品销量字段。

    Args:
        item: 特征行或报告行（可含 feature_excerpt）。

    Returns:
        dict: 仅含词典字段；可能为空。
    """
    src = _merge_item_sources(item)
    view: dict[str, Any] = {}
    for key in GOODS_STAT_KEYS:
        if key in src and src[key] is not None:
            view[key] = src[key]
    if "goodsId" not in view:
        gid = _first_present(src, _ID_FALLBACKS)
        if gid is not None:
            view["goodsId"] = gid
    if "goodsName" not in view:
        name = _first_present(src, _NAME_FALLBACKS)
        if name is not None:
            view["goodsName"] = name
    return view


def slim_ops_excerpt(item: dict[str, Any] | None) -> dict[str, Any]:
    """报告落库用的运营字段摘录（同 ops_goods_view）。"""
    return ops_goods_view(item)
