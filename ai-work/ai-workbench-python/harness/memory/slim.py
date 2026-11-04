"""
给 LLM 的结构化载荷预算裁剪（确定性截断，优先于摘要）。
"""

from __future__ import annotations

import copy
from typing import Any

from harness.memory.tokens import TokenBudget, estimate_json

# 会签只留窗口数字，避免 ops/metrics 双份膨胀
_COUNCIL_METRIC_KEYS: tuple[str, ...] = (
    "gmv_30d",
    "orders_30d",
    "clicks_30d",
    "rate_per",
)
_TITLE_MAX = 28


def _short_title(value: Any) -> str | None:
    """会签标题再截一刀。"""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= _TITLE_MAX:
        return text
    return text[: _TITLE_MAX - 1] + "…"


def _compact_num(value: Any) -> Any:
    """整数去掉 .0；转化率最多两位。"""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value.is_integer():
            return int(value)
        return round(value, 2)
    return value


def slim_candidates_for_llm(
    candidates: list[dict[str, Any]],
    *,
    budget: TokenBudget | None = None,
    max_items: int = 10,
) -> list[dict[str, Any]]:
    """
    会签用候选裁剪：身份 + 分数 + 少量窗口数。

    Args:
        candidates: 打分后的候选。
        budget: token 预算。
        max_items: 最多条数（默认 10，约 focus_slots×2）。

    Returns:
        list: 精简行。
    """
    b = budget or TokenBudget(context_window=32_000, reserve_output=2048, guard_ratio=0.65)
    keep_keys = (
        "sku_id",
        "rank",
        "explosion_score",
        "quality_risk_level",
        "quality_rule_ids",
        "action_bucket",
        "signal_confidence",
        "risk_veto",
        "in_focus_slot",
    )
    out: list[dict[str, Any]] = []
    committed = 0
    limit = min(max_items, b.input_limit // 50)
    for c in candidates[: max(1, limit)]:
        row: dict[str, Any] = {}
        title = _short_title(c.get("title"))
        if title:
            row["title"] = title
        for k in keep_keys:
            if k not in c or c.get(k) is None:
                continue
            val = c.get(k)
            if k == "quality_rule_ids" and not val:
                continue
            if k == "explosion_score" and isinstance(val, (int, float)):
                row[k] = round(float(val), 1)
            else:
                row[k] = val
        metrics = c.get("metrics") if isinstance(c.get("metrics"), dict) else {}
        for key in _COUNCIL_METRIC_KEYS:
            val = c.get(key)
            if val is None and metrics:
                val = metrics.get(key)
            if val is not None:
                row[key] = _compact_num(val)
        cost = estimate_json(row)
        if committed + cost > b.input_limit // 2:
            break
        out.append(row)
        committed += cost
    return out



def slim_reports_for_llm(
    reports: list[dict[str, Any]],
    *,
    max_reports: int = 2,
    max_items: int = 10,
) -> list[dict[str, Any]]:
    """追问用报告瘦身。"""
    from harness.memory.fields import ops_goods_view

    slimmed = []
    for r in reports[:max_reports]:
        header = r.get("header") or {}
        items = []
        for it in list(r.get("items") or [])[:max_items]:
            row = ops_goods_view(it)
            issues = it.get("issues")
            if issues:
                row["issue_rule_ids"] = [
                    str(x.get("rule_id"))
                    for x in issues
                    if isinstance(x, dict) and x.get("rule_id")
                ][:6]
            items.append(row)
        slimmed.append(
            {
                "task_id": r.get("task_id"),
                "task_type": r.get("task_type"),
                "header": {
                    "summary": header.get("summary"),
                    "scoring_version": header.get("scoring_version"),
                    "snapshot_date": header.get("snapshot_date"),
                    "goal_mode": header.get("goal_mode"),
                },
                "items": items,
            }
        )
    return slimmed


def clamp_obj(obj: Any, *, max_tokens: int) -> Any:
    """若 JSON 估算超预算，深拷贝后截断 list 字段。"""
    data = copy.deepcopy(obj)
    if estimate_json(data) <= max_tokens:
        return data
    if isinstance(data, dict):
        for k, v in list(data.items()):
            if isinstance(v, list) and len(v) > 3:
                data[k] = v[: max(1, len(v) // 2)]
                if estimate_json(data) <= max_tokens:
                    return data
    return data

