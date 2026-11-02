"""
爆品加权分（纯函数）。

同一快照输入必须得到稳定分数；LOW_SAMPLE / NO_DATA 跳过并标注。
"""

from __future__ import annotations

from typing import Any

from scoring import config as C
from scoring.math_utils import (
    clamp01,
    growth_to_unit,
    num,
    shrink_to_mean,
    smoothed_growth,
)


def score_sku(
    feature: dict[str, Any], *, store_stats: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    对单个 SKU 特征行计算爆品分。

    Args:
        feature: Java 快照特征行。
        store_stats: 店铺级汇总（平滑 α、CTR/CVR 收缩）。

    Returns:
        dict[str, Any]: explosion_score / score_breakdown / skipped_items。
    """
    stats = store_stats or {}
    alpha = float(stats.get("avg_gmv_30d") or 1.0)
    beta = max(10.0, alpha / 50.0)  # 点击平滑，避免为 0
    store_ctr = float(stats.get("store_ctr") or 0.05)
    store_cvr = float(stats.get("store_cvr") or 0.02)

    breakdown: dict[str, Any] = {}
    skipped: list[dict[str, str]] = []
    weighted_sum = 0.0
    weight_sum = 0.0

    def add(name: str, weight: float, unit_score: float, detail: dict[str, Any]) -> None:
        nonlocal weighted_sum, weight_sum
        weighted_sum += weight * unit_score
        weight_sum += weight
        breakdown[name] = {"weight": weight, "unit_score": round(unit_score, 4), **detail}

    # --- 流量增速 ---
    clicks = num(feature.get("clicks_30d"))
    clicks_prev = num(feature.get("clicks_prev_30d"))
    if clicks is None or clicks_prev is None:
        skipped.append({"item": "traffic_growth", "reason": "NO_DATA"})
    elif (clicks + clicks_prev) < C.MIN_CLICKS_FOR_TRAFFIC_GROWTH:
        skipped.append({"item": "traffic_growth", "reason": "LOW_SAMPLE"})
    else:
        g = smoothed_growth(clicks, clicks_prev, beta)
        add(
            "traffic_growth",
            C.WEIGHT_TRAFFIC_GROWTH,
            growth_to_unit(g),
            {"raw_growth": round(g, 4)},
        )

    # --- CTR ---
    impressions = num(feature.get("impressions_30d"))
    if clicks is None or impressions is None:
        skipped.append({"item": "ctr", "reason": "NO_DATA"})
    elif impressions < C.MIN_IMPRESSIONS_FOR_CTR:
        skipped.append({"item": "ctr", "reason": "LOW_SAMPLE"})
    else:
        raw_ctr = clicks / impressions if impressions > 0 else 0.0
        ctr = shrink_to_mean(
            raw_ctr,
            impressions,
            store_ctr,
            C.CTR_PRIOR_IMPRESSIONS,
        )
        # 相对店均：店均附近 0.5，2 倍店均 → 1
        unit = clamp01(ctr / (store_ctr * 2) if store_ctr > 0 else 0.5)
        add("ctr", C.WEIGHT_CTR, unit, {"ctr": round(ctr, 6)})

    # --- CVR ---
    paid = num(feature.get("paid_orders_from_clicks_30d"))
    if clicks is None or paid is None:
        skipped.append({"item": "cvr", "reason": "NO_DATA"})
    elif clicks < C.MIN_CLICKS_FOR_CVR:
        skipped.append({"item": "cvr", "reason": "LOW_SAMPLE"})
    else:
        raw_cvr = paid / clicks if clicks > 0 else 0.0
        cvr = shrink_to_mean(raw_cvr, clicks, store_cvr, C.CVR_PRIOR_CLICKS)
        unit = clamp01(cvr / (store_cvr * 2) if store_cvr > 0 else 0.5)
        add("cvr", C.WEIGHT_CVR, unit, {"cvr": round(cvr, 6)})

    # --- 销售规模 ---
    gmv = num(feature.get("gmv_30d"))
    if gmv is None:
        skipped.append({"item": "gmv_scale", "reason": "NO_DATA"})
    else:
        avg = float(stats.get("avg_gmv_30d") or 1.0)
        # 相对店均对数感：0 → 0，等于店均 → ~0.5，3 倍+ → 1
        ratio = gmv / avg if avg > 0 else 0.0
        unit = clamp01(ratio / 3.0)
        add("gmv_scale", C.WEIGHT_GMV_SCALE, unit, {"gmv_30d": gmv, "ratio_to_avg": round(ratio, 4)})

    # --- 销售增速 ---
    gmv_prev = num(feature.get("gmv_prev_30d"))
    orders = num(feature.get("orders_30d"), 0.0) or 0.0
    orders_prev = num(feature.get("orders_prev_30d"), 0.0) or 0.0
    if gmv is None or gmv_prev is None:
        skipped.append({"item": "sales_growth", "reason": "NO_DATA"})
    elif (orders + orders_prev) < C.MIN_ORDERS_FOR_SALES_GROWTH:
        skipped.append({"item": "sales_growth", "reason": "LOW_SAMPLE"})
    else:
        g = smoothed_growth(gmv, gmv_prev, alpha)
        add(
            "sales_growth",
            C.WEIGHT_SALES_GROWTH,
            growth_to_unit(g),
            {"raw_growth": round(g, 4)},
        )

    # --- 毛利 ---
    price = num(feature.get("price"))
    cost = num(feature.get("cost"))
    if price is None or cost is None:
        skipped.append({"item": "margin", "reason": "NO_DATA"})
    elif price <= 0:
        skipped.append({"item": "margin", "reason": "NO_DATA"})
    else:
        margin = (price - cost) / price
        unit = clamp01((margin + 0.1) / 0.6)  # -10%→0，50%→1 附近
        add("margin", C.WEIGHT_MARGIN, unit, {"margin": round(margin, 4)})

    if weight_sum <= 0:
        score = 0.0
    else:
        score = 100.0 * (weighted_sum / weight_sum)

    return {
        "sku_id": feature.get("sku_id"),
        "explosion_score": round(score, 2),
        "score_breakdown": breakdown,
        "skipped_items": skipped,
    }
