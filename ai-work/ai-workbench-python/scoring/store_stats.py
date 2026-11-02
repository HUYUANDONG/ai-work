"""从一批特征行汇总店铺级统计，供收缩与相对分位使用。"""

from __future__ import annotations

from typing import Any

from scoring.math_utils import num


def build_store_stats(items: list[dict[str, Any]]) -> dict[str, Any]:
    """
    计算店铺汇总。

    Args:
        items: 特征行列表。

    Returns:
        dict[str, Any]: 含 sku_count、avg_gmv_30d、store_ctr、store_cvr 等。
    """
    n = len(items)
    gmv_sum = 0.0
    clicks_sum = 0.0
    impressions_sum = 0.0
    paid_sum = 0.0
    review_weighted = 0.0
    review_n = 0.0

    for row in items:
        gmv_sum += num(row.get("gmv_30d"), 0.0) or 0.0
        clicks_sum += num(row.get("clicks_30d"), 0.0) or 0.0
        impressions_sum += num(row.get("impressions_30d"), 0.0) or 0.0
        paid_sum += num(row.get("paid_orders_from_clicks_30d"), 0.0) or 0.0
        rc = num(row.get("review_count"), 0.0) or 0.0
        rs = num(row.get("review_score"))
        if rc > 0 and rs is not None:
            review_weighted += rs * rc
            review_n += rc

    avg_gmv = gmv_sum / n if n else 0.0
    store_ctr = (clicks_sum / impressions_sum) if impressions_sum > 0 else 0.05
    store_cvr = (paid_sum / clicks_sum) if clicks_sum > 0 else 0.02
    store_review = (review_weighted / review_n) if review_n > 0 else 4.5

    return {
        "sku_count": n,
        "avg_gmv_30d": avg_gmv,
        "store_ctr": store_ctr,
        "store_cvr": store_cvr,
        "store_review_score": store_review,
        "total_clicks_30d": clicks_sum,
    }

