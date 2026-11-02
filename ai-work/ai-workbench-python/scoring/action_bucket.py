"""
规则化作战桶（会签 LLM 失败时的降级基线；正式路径见 agents.explosion.council）。
"""

from __future__ import annotations

from typing import Any

# 兼容旧导入；正式 council_version 在 agents.explosion.council
COUNCIL_VERSION = "council-rules-1.0.0"


def assign_action_buckets(
    candidates: list[dict[str, Any]],
    *,
    focus_slots: int = 5,
    goal_mode: str = "GMV",
) -> list[dict[str, Any]]:
    """
    规则基线：为候选填 action_bucket / risk_veto / in_focus_slot。

    Args:
        candidates: 已打分挂标列表。
        focus_slots: 槽位上限。
        goal_mode: 目标模式（基线暂不细分，保留参数）。

    Returns:
        list[dict]: 同一列表。
    """
    slots = max(1, min(int(focus_slots), 10))
    _ = goal_mode

    for c in candidates:
        risk = str(c.get("quality_risk_level") or "NONE")
        score = float(c.get("explosion_score") or 0)
        veto = risk in {"HIGH", "MID"} and score >= 60
        c["risk_veto"] = veto

        if risk == "HIGH":
            bucket = "FIX_THEN_PUSH" if score >= 55 else "DROP"
        elif risk == "MID":
            bucket = "FIX_THEN_PUSH" if score >= 50 else "WATCH"
        elif score >= 70:
            bucket = "PUSH"
        elif score >= 45:
            bucket = "WATCH"
        else:
            bucket = "DROP"

        if veto and bucket == "PUSH":
            bucket = "FIX_THEN_PUSH"

        c["action_bucket"] = bucket
        if score >= 75 and risk in {"NONE", "LOW"}:
            c["signal_confidence"] = "HIGH"
        elif score >= 55:
            c["signal_confidence"] = "MID"
        else:
            c["signal_confidence"] = "LOW"

        if not c.get("primary_action"):
            c["primary_action"] = _default_action(bucket, risk)
        c.setdefault("ai_reason", "")
        c.setdefault("ai_risk", "")
        c.setdefault("ai_suggestion", "")
        c["council_excerpt"] = {
            "source": "rules_baseline",
            "council_version": COUNCIL_VERSION,
        }
        c["in_focus_slot"] = False

    used = 0
    for c in candidates:
        if c["action_bucket"] in {"PUSH", "FIX_THEN_PUSH"} and used < slots:
            c["in_focus_slot"] = True
            used += 1

    for i, c in enumerate(candidates, start=1):
        c["mode_rank"] = i

    return candidates


def _default_action(bucket: str, risk: str) -> str:
    if bucket == "PUSH":
        return "本周可加大曝光与转化实验"
    if bucket == "FIX_THEN_PUSH":
        return f"先处理 {risk} 风险再放量"
    if bucket == "WATCH":
        return "观察一周信号，暂不加大投入"
    return "本期不建议主推"


def focus_count(candidates: list[dict[str, Any]]) -> int:
    """进入槽位的数量。"""
    return sum(1 for c in candidates if c.get("in_focus_slot"))

