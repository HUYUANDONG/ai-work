"""
会签工具：reduce / 预览。编排已迁至 LangGraph（lg_graph）。
"""

from __future__ import annotations

from typing import Any

COUNCIL_VERSION = "council-v1.0.0"


def _index_by_sku(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(x.get("sku_id")): x for x in items}


def council_reduce(
    candidates: list[dict[str, Any]],
    *,
    signal_items: list[dict[str, Any]],
    risk_items: list[dict[str, Any]],
    strategy_items: list[dict[str, Any]],
    focus_slots: int,
) -> list[dict[str, Any]]:
    """合并三角色意见到候选行。"""
    sig_by = _index_by_sku(signal_items)
    risk_by = _index_by_sku(risk_items)
    strat_by = _index_by_sku(strategy_items)
    slots = max(1, min(int(focus_slots), 10))

    for c in candidates:
        sku = str(c.get("sku_id"))
        sig = sig_by.get(sku) or {}
        risk = risk_by.get(sku) or {}
        strat = strat_by.get(sku) or {}

        bucket = str(strat.get("action_bucket") or c.get("action_bucket") or "WATCH")
        veto = bool(risk.get("veto"))
        if veto and bucket == "PUSH":
            bucket = "FIX_THEN_PUSH"

        c["action_bucket"] = bucket
        c["risk_veto"] = veto
        c["signal_confidence"] = (
            sig.get("signal_confidence") or c.get("signal_confidence") or "MID"
        )
        c["primary_action"] = strat.get("primary_action") or c.get("primary_action") or ""
        c["ai_reason"] = sig.get("attribution") or ""
        c["ai_risk"] = risk.get("rationale") or ""
        c["ai_suggestion"] = strat.get("rationale") or ""
        c["council_excerpt"] = {
            "council_version": COUNCIL_VERSION,
            "signal": {
                "confidence": sig.get("signal_confidence"),
                "breakout": sig.get("looks_like_breakout"),
                "degraded": sig.get("degraded", False),
            },
            "risk": {
                "veto": veto,
                "severity_view": risk.get("severity_view"),
                "fix_first": risk.get("fix_first"),
                "degraded": risk.get("degraded", False),
            },
            "strategy": {"bucket": bucket, "degraded": strat.get("degraded", False)},
        }
        c["in_focus_slot"] = False

    used = 0
    for c in candidates:
        sku = str(c.get("sku_id"))
        strat = strat_by.get(sku) or {}
        want = bool(strat.get("in_focus_slot")) and c["action_bucket"] in {
            "PUSH",
            "FIX_THEN_PUSH",
        }
        if want and used < slots:
            c["in_focus_slot"] = True
            used += 1
    if used < slots:
        for c in candidates:
            if (
                not c["in_focus_slot"]
                and c["action_bucket"] in {"PUSH", "FIX_THEN_PUSH"}
                and used < slots
            ):
                c["in_focus_slot"] = True
                used += 1

    for i, c in enumerate(candidates, start=1):
        c["mode_rank"] = i
    return candidates


def _focus_preview(
    candidates: list[dict[str, Any]], limit: int = 5
) -> list[dict[str, Any]]:
    focus = [c for c in candidates if c.get("in_focus_slot")][:limit]
    return [
        {
            "sku_id": c.get("sku_id"),
            "action_bucket": c.get("action_bucket"),
            "explosion_score": c.get("explosion_score"),
            "risk_veto": c.get("risk_veto"),
        }
        for c in focus
    ]

