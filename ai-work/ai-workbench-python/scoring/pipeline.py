"""
爆品筛选流水线：从营销特征行 → 过滤 → 打分 → 挂质检标 → Top N。

纯函数，不访问网络。
"""

from __future__ import annotations

from typing import Any

from schemas.ops_fields import slim_ops_excerpt
from scoring import config as C
from scoring.explosion import score_sku
from scoring.math_utils import num
from scoring.quality import check_sku
from scoring.store_stats import build_store_stats
from scoring.user_filters import row_passes_filters


def filter_marketing_candidates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    从营销数据里留下「有信号」的 SKU：在售，且近 30 天有 GMV 或点击。

    Args:
        items: 原始特征行。

    Returns:
        list[dict]: 候选池。
    """
    out: list[dict[str, Any]] = []
    for row in items:
        hydrate_ops_windows(row)
        if not bool(row.get("on_sale", True)):
            continue
        gmv = num(row.get("gmv_30d"), 0.0) or 0.0
        clicks = num(row.get("clicks_30d"), 0.0) or 0.0
        if gmv < C.MIN_MARKETING_SIGNAL_GMV_30D and clicks < C.MIN_MARKETING_SIGNAL_CLICKS_30D:
            continue
        out.append(row)
    return out


def hydrate_ops_windows(row: dict[str, Any]) -> None:
    """
    运营接口字段补进评分窗口：有 gmv_* 不覆盖；缺了才用 orderSales / goodsUv。
    """
    if num(row.get("gmv_30d")) is None and num(row.get("orderSales")) is not None:
        row["gmv_30d"] = row.get("orderSales")
    if num(row.get("gmv_prev_30d")) is None and num(row.get("orderSalesPrev")) is not None:
        row["gmv_prev_30d"] = row.get("orderSalesPrev")
    if num(row.get("orders_30d")) is None and num(row.get("orderNumbers")) is not None:
        row["orders_30d"] = row.get("orderNumbers")
    if num(row.get("orders_prev_30d")) is None and num(row.get("orderNumbersPrev")) is not None:
        row["orders_prev_30d"] = row.get("orderNumbersPrev")
    if num(row.get("clicks_30d")) is None and num(row.get("goodsUv")) is not None:
        row["clicks_30d"] = row.get("goodsUv")
    if num(row.get("impressions_30d")) is None and num(row.get("goodsPv")) is not None:
        row["impressions_30d"] = row.get("goodsPv")
    if num(row.get("rate_per")) is None and num(row.get("ratePer")) is not None:
        row["rate_per"] = row.get("ratePer")
    if not row.get("sku_id"):
        row["sku_id"] = row.get("goodsId")
    if not row.get("title"):
        row["title"] = row.get("goodsName")


def rank_candidates(
    items: list[dict[str, Any]],
    *,
    top_n: int | None = None,
    user_filters: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    过滤 → 店铺统计 → 打分+挂标 → 运营硬条件 → 按 explosion_score 排序截断。

    Args:
        items: 特征行（通常来自 features/query）。
        top_n: 返回条数；默认配置 DEFAULT_TOP_N，上限 MAX_TOP_N。
        user_filters: LLM 抽出的下限（毛利/转化率/销售额/订单）。空则不过滤。

    Returns:
        dict: candidates / store_stats / pool_size / scoring_version / user_filters。
    """
    n = top_n if top_n is not None else C.DEFAULT_TOP_N
    n = max(1, min(int(n), C.MAX_TOP_N))

    pool = filter_marketing_candidates(items)
    store_stats = build_store_stats(pool if pool else items)

    scored: list[dict[str, Any]] = []
    for row in pool:
        exp = score_sku(row, store_stats=store_stats)
        q = check_sku(row, store_stats=store_stats)
        scored.append(
            {
                "sku_id": row.get("sku_id"),
                "title": row.get("title"),
                "category_id": row.get("category_id"),
                "explosion_score": exp["explosion_score"],
                "score_breakdown": exp["score_breakdown"],
                "skipped_items": exp["skipped_items"],
                "quality_risk_level": q["quality_risk_level"],
                "quality_rule_ids": q["quality_rule_ids"],
                "quality_score": q["quality_score"],
                "ops_score": q["ops_score"],
                "feature_excerpt": slim_ops_excerpt(row),
                "metrics": {
                    "gmv_30d": row.get("gmv_30d"),
                    "gmv_prev_30d": row.get("gmv_prev_30d"),
                    "clicks_30d": row.get("clicks_30d"),
                    "clicks_prev_30d": row.get("clicks_prev_30d"),
                    "orders_30d": row.get("orders_30d"),
                    "orders_prev_30d": row.get("orders_prev_30d"),
                    "impressions_30d": row.get("impressions_30d"),
                    "impressions_prev_30d": row.get("impressions_prev_30d"),
                    "paid_orders_from_clicks_30d": row.get("paid_orders_from_clicks_30d"),
                    "rate_per": row.get("rate_per")
                    if row.get("rate_per") is not None
                    else row.get("ratePer"),
                    "stock_qty": row.get("stock_qty"),
                    "price": row.get("price"),
                    "cost": row.get("cost"),
                    "amount_unit": row.get("amount_unit") or "fen",
                },
            }
        )

    filters = dict(user_filters or {})
    kept = [row for row in scored if row_passes_filters(row.get("metrics") or {}, filters)]
    kept.sort(key=lambda x: x["explosion_score"], reverse=True)
    top = kept[:n]
    for i, row in enumerate(top, start=1):
        row["rank"] = i

    return {
        "scoring_version": C.SCORING_VERSION,
        "pool_size": len(pool),
        "scored_size": len(scored),
        "filtered_out": len(scored) - len(kept),
        "user_filters": filters,
        "top_n": n,
        "store_stats": store_stats,
        "candidates": top,
    }

