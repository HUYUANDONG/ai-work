"""
给 LLM 的结构化载荷预算裁剪（确定性截断，优先于摘要）。
"""

from __future__ import annotations

import copy
from typing import Any

from harness.memory.fields import ops_goods_view
from harness.memory.tokens import TokenBudget, estimate_json


def slim_candidates_for_llm(
    candidates: list[dict[str, Any]],
    *,
    budget: TokenBudget | None = None,
    max_items: int = 30,
) -> list[dict[str, Any]]:
    """
    会签用候选裁剪：运营接口字段 + 内部会签键，并按预算截断条数。
    """
    b = budget or TokenBudget(context_window=32_000, reserve_output=2048, guard_ratio=0.65)
    keep_keys = (
        "sku_id",
        "quality_risk_level",
        "quality_rule_ids",
        "skipped_items",
        "action_bucket",
        "signal_confidence",
        "risk_veto",
        "in_focus_slot",
    )
    out: list[dict[str, Any]] = []
    committed = 0
    limit = min(max_items, b.input_limit // 50)  # 粗上限
    for c in candidates[: max(1, limit)]:
        row = {k: c.get(k) for k in keep_keys if k in c}
        ops = ops_goods_view(c)
        if ops:
            row["ops"] = ops
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
