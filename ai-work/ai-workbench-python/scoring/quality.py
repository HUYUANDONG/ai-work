"""
质检规则命中（挂到爆品行上的风险标签）。

规则 ID 与文档 data-contract 一致。未判定项进 skipped_rules。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from scoring import config as C
from scoring.math_utils import num, shrink_to_mean, smoothed_growth


def _severity_rank(level: str) -> int:
    order = {"NONE": 0, "LOW": 1, "MID": 2, "HIGH": 3}
    return order.get(level, 0)


def check_sku(
    feature: dict[str, Any], *, store_stats: dict[str, Any] | None = None
) -> dict[str, Any]:
    """
    对单个 SKU 执行规则检查（爆品挂标用精简结果）。

    Args:
        feature: 特征行。
        store_stats: 店铺汇总。

    Returns:
        dict: quality_risk_level / quality_rule_ids / issues / skipped_rules /
              quality_score / ops_score（简化）。
    """
    stats = store_stats or {}
    issues: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    def hit(rule_id: str, severity: str, **extra: Any) -> None:
        issues.append({"rule_id": rule_id, "severity": severity, **extra})

    price = num(feature.get("price"))
    cost = num(feature.get("cost"))
    stock = num(feature.get("stock_qty"))
    clicks = num(feature.get("clicks_30d"), 0.0) or 0.0
    on_sale = bool(feature.get("on_sale", True))

    # PRICE_BELOW_COST / PROFIT_*
    if price is None or cost is None:
        skipped.append({"rule_id": "PROFIT_LOW", "reason": "NO_DATA"})
        skipped.append({"rule_id": "PROFIT_NEGATIVE", "reason": "NO_DATA"})
        skipped.append({"rule_id": "PRICE_BELOW_COST", "reason": "NO_DATA"})
    else:
        if price < cost:
            hit("PRICE_BELOW_COST", "HIGH", actual=price, threshold=cost)
        if price > 0:
            margin = (price - cost) / price
            if margin < 0:
                hit("PROFIT_NEGATIVE", "HIGH", actual=round(margin, 4), threshold=0)
            elif margin < C.MARGIN_LOW:
                hit("PROFIT_LOW", "MID", actual=round(margin, 4), threshold=C.MARGIN_LOW)

    # STOCK_LOW
    units = num(feature.get("units_30d"))
    orders = num(feature.get("orders_30d"), 0.0) or 0.0
    if stock is None:
        skipped.append({"rule_id": "STOCK_LOW", "reason": "NO_DATA"})
    elif on_sale and stock <= 0 and clicks > 0:
        hit("STOCK_LOW", "HIGH", actual=stock, threshold=0)
    elif orders < C.MIN_ORDERS_30D_FOR_DAYS_OF_SUPPLY:
        skipped.append({"rule_id": "STOCK_LOW", "reason": "LOW_SAMPLE"})
    elif units is not None and units > 0 and stock is not None:
        dos = stock / (units / 30.0)
        if dos < C.DAYS_OF_SUPPLY_LOW:
            hit("STOCK_LOW", "HIGH", actual=round(dos, 2), threshold=C.DAYS_OF_SUPPLY_LOW)

    # STOCK_OVER（按库存金额 + 久未成交；无 last_sale_date 则仅看金额过高时 MID）
    stock_value = num(feature.get("stock_value"))
    if stock_value is None:
        skipped.append({"rule_id": "STOCK_OVER", "reason": "NO_DATA"})
    elif stock_value >= C.STOCK_OVER_VALUE:
        last = feature.get("last_sale_date")
        stale = False
        if last:
            try:
                if isinstance(last, date):
                    last_d = last
                else:
                    last_d = datetime.fromisoformat(str(last)[:10]).date()
                stale = (date.today() - last_d).days >= C.STOCK_OVER_DAYS_SINCE_SALE
            except ValueError:
                stale = False
        if stale or last is None:
            hit(
                "STOCK_OVER",
                "MID" if last is None else "HIGH",
                actual=stock_value,
                threshold=C.STOCK_OVER_VALUE,
            )

    # SALES_DOWN
    gmv = num(feature.get("gmv_30d"))
    gmv_prev = num(feature.get("gmv_prev_30d"))
    orders_prev = num(feature.get("orders_prev_30d"), 0.0) or 0.0
    alpha = float(stats.get("avg_gmv_30d") or 1.0)
    if gmv is None or gmv_prev is None:
        skipped.append({"rule_id": "SALES_DOWN", "reason": "NO_DATA"})
    elif (orders + orders_prev) < C.MIN_ORDERS_FOR_SALES_GROWTH:
        skipped.append({"rule_id": "SALES_DOWN", "reason": "LOW_SAMPLE"})
    else:
        growth = smoothed_growth(gmv, gmv_prev, alpha)
        if growth <= C.SALES_GROWTH_DOWN:
            hit("SALES_DOWN", "MID", actual=round(growth, 4), threshold=C.SALES_GROWTH_DOWN)

    # RETURN_HIGH
    ret = num(feature.get("return_orders_90d"))
    orders_90 = num(feature.get("orders_90d"))
    if ret is None or orders_90 is None:
        skipped.append({"rule_id": "RETURN_HIGH", "reason": "NO_DATA"})
    elif orders_90 < C.MIN_ORDERS_90D_FOR_RETURN:
        skipped.append({"rule_id": "RETURN_HIGH", "reason": "LOW_SAMPLE"})
    elif orders_90 > 0:
        rate = ret / orders_90
        if rate >= C.RETURN_RATE_HIGH:
            hit("RETURN_HIGH", "MID", actual=round(rate, 4), threshold=C.RETURN_RATE_HIGH)

    # REVIEW_LOW
    review_score = num(feature.get("review_score"))
    review_count = num(feature.get("review_count"), 0.0) or 0.0
    store_review = float(stats.get("store_review_score") or 4.5)
    if review_score is None:
        skipped.append({"rule_id": "REVIEW_LOW", "reason": "NO_DATA"})
    elif review_count < C.MIN_REVIEW_COUNT:
        skipped.append({"rule_id": "REVIEW_LOW", "reason": "LOW_SAMPLE"})
    else:
        shrunk = shrink_to_mean(
            review_score, review_count, store_review, C.REVIEW_PRIOR_COUNT
        )
        if shrunk < C.REVIEW_SCORE_LOW:
            hit("REVIEW_LOW", "LOW", actual=round(shrunk, 3), threshold=C.REVIEW_SCORE_LOW)

    # CTR_LOW / CVR_LOW / TRAFFIC_HIGH_CVR_LOW（简化）
    impressions = num(feature.get("impressions_30d"))
    paid = num(feature.get("paid_orders_from_clicks_30d"))
    store_ctr = float(stats.get("store_ctr") or 0.05)
    store_cvr = float(stats.get("store_cvr") or 0.02)
    total_clicks = float(stats.get("total_clicks_30d") or 0.0)

    if clicks is None or impressions is None:
        skipped.append({"rule_id": "CTR_LOW", "reason": "NO_DATA"})
    elif impressions < C.MIN_IMPRESSIONS_FOR_CTR:
        skipped.append({"rule_id": "CTR_LOW", "reason": "LOW_SAMPLE"})
    elif impressions > 0:
        ctr = clicks / impressions
        if ctr < store_ctr * C.CTR_LOW_RATIO_OF_STORE:
            hit("CTR_LOW", "LOW", actual=round(ctr, 6), threshold=round(store_ctr * C.CTR_LOW_RATIO_OF_STORE, 6))

    if clicks is None or paid is None:
        skipped.append({"rule_id": "CVR_LOW", "reason": "NO_DATA"})
        skipped.append({"rule_id": "TRAFFIC_HIGH_CVR_LOW", "reason": "NO_DATA"})
    elif clicks < C.MIN_CLICKS_FOR_CVR:
        skipped.append({"rule_id": "CVR_LOW", "reason": "LOW_SAMPLE"})
        skipped.append({"rule_id": "TRAFFIC_HIGH_CVR_LOW", "reason": "LOW_SAMPLE"})
    else:
        cvr = paid / clicks if clicks > 0 else 0.0
        if cvr < store_cvr * C.CVR_LOW_RATIO_OF_STORE:
            hit("CVR_LOW", "MID", actual=round(cvr, 6), threshold=round(store_cvr * C.CVR_LOW_RATIO_OF_STORE, 6))
        # 点击占店内较高且 CVR 低
        if total_clicks > 0 and clicks / total_clicks >= 0.15 and cvr < store_cvr * C.CVR_LOW_RATIO_OF_STORE:
            hit("TRAFFIC_HIGH_CVR_LOW", "MID", actual=round(cvr, 6))

    # 汇总风险
    risk = "NONE"
    for issue in issues:
        if _severity_rank(issue["severity"]) > _severity_rank(risk):
            risk = issue["severity"]

    rule_ids = [i["rule_id"] for i in issues]
    # 简化分：命中越多越低
    penalty = sum(10 if i["severity"] == "HIGH" else 5 if i["severity"] == "MID" else 2 for i in issues)
    quality_score = max(0.0, 100.0 - penalty)
    ops_score = quality_score

    return {
        "sku_id": feature.get("sku_id"),
        "quality_risk_level": risk,
        "quality_rule_ids": rule_ids,
        "issues": issues,
        "skipped_rules": skipped,
        "quality_score": round(quality_score, 2),
        "ops_score": round(ops_score, 2),
    }
