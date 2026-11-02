"""
作战指挥：计划状态机 + 发现结果不合理时 REVISE / FINISH。

修订看「结果是否仍错」，不是只看输入风险占比（否则会空转修订）。
"""

from __future__ import annotations

from typing import Any

MAX_REVISIONS = 2
MAX_LLM_ROUNDS = 3


def init_plan(*, goal_mode: str, focus_slots: int) -> dict[str, Any]:
    """初始计划。"""
    return {
        "goal_mode": goal_mode,
        "focus_slots": focus_slots,
        "steps": ["SIGNAL_RISK_PARALLEL", "STRATEGY", "REDUCE", "DECIDE"],
        "revision": 0,
        "max_revisions": MAX_REVISIONS,
        "max_llm_rounds": MAX_LLM_ROUNDS,
        "llm_round": 0,
        "decision": "CONTINUE",
        "revision_reason": "",
        "revise_scope": "FULL",
        "strategy_bias": {},
        "plan_degraded": False,
        "history": [],
    }


def plan_decide(
    candidates: list[dict[str, Any]],
    plan: dict[str, Any],
    *,
    signal_items: list[dict[str, Any]],
    risk_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    指挥裁决：REVISE（结果仍不合理）| FINISH。

    在一轮会签 reduce 之后调用。
    """
    n = max(len(candidates), 1)
    slots = int(plan.get("focus_slots") or 5)
    goal = str(plan.get("goal_mode") or "GMV")
    risk_by = {str(r.get("sku_id")): r for r in risk_items}
    sig_by = {str(s.get("sku_id")): s for s in signal_items}

    high_risk_n = sum(
        1 for c in candidates if str(c.get("quality_risk_level")) == "HIGH"
    )
    high_ratio = high_risk_n / n

    # 结果错误：HIGH 风险仍被 PUSH
    high_still_push = [
        c
        for c in candidates
        if str(c.get("quality_risk_level")) == "HIGH"
        and c.get("action_bucket") == "PUSH"
    ]

    veto_n = sum(1 for r in risk_items if r.get("veto"))
    # 结果错误：veto 品仍 PUSH，或否决很多却仍大量进槽硬冲
    veto_still_push = [
        c
        for c in candidates
        if risk_by.get(str(c.get("sku_id")), {}).get("veto")
        and c.get("action_bucket") == "PUSH"
    ]
    focus_veto_push = sum(
        1
        for c in candidates
        if c.get("in_focus_slot")
        and risk_by.get(str(c.get("sku_id")), {}).get("veto")
        and c.get("action_bucket") == "PUSH"
    )

    low_signal_n = sum(
        1 for s in signal_items if str(s.get("signal_confidence")) == "LOW"
    )
    low_ratio = low_signal_n / n
    # 结果错误：低置信仍大量 PUSH
    low_still_push = [
        c
        for c in candidates
        if str(sig_by.get(str(c.get("sku_id")), {}).get("signal_confidence")) == "LOW"
        and c.get("action_bucket") == "PUSH"
    ]

    profit_bad_push = []
    if goal == "PROFIT":
        for c in candidates:
            if c.get("action_bucket") != "PUSH":
                continue
            rules = set(c.get("quality_rule_ids") or [])
            if rules.intersection({"PROFIT_LOW", "PROFIT_NEGATIVE"}):
                profit_bad_push.append(c)

    focus = sum(1 for c in candidates if c.get("in_focus_slot"))

    reasons: list[str] = []
    bias: dict[str, Any] = dict(plan.get("strategy_bias") or {})
    scope = "STRATEGY_ONLY"

    if high_ratio > 0.30 and high_still_push:
        reasons.append(
            f"HIGH风险占比{high_ratio:.0%}且仍有{len(high_still_push)}个PUSH，应收紧为先修/放弃"
        )
        bias["prefer_fix_then_push"] = True

    if veto_still_push or (veto_n >= slots and focus_veto_push > 0):
        reasons.append(
            f"否决约束未落实（veto仍PUSH={len(veto_still_push)}，槽内硬冲={focus_veto_push}）"
        )
        bias["prefer_fix_then_push"] = True

    if low_ratio > 0.50 and len(low_still_push) >= 2:
        reasons.append(
            f"低置信信号多且仍有{len(low_still_push)}个PUSH，应提高观察比例"
        )
        bias["prefer_watch"] = True

    if profit_bad_push:
        reasons.append(
            f"PROFIT目标下仍有{len(profit_bad_push)}个微利/负利被PUSH"
        )
        bias["prefer_drop_weak_profit"] = True

    if focus > slots:
        reasons.append(f"进槽{focus}>槽位{slots}")

    if not reasons:
        plan["decision"] = "FINISH"
        plan["revision_reason"] = plan.get("revision_reason") or "会签结果自洽"
        return plan

    if int(plan.get("revision") or 0) >= int(plan.get("max_revisions") or MAX_REVISIONS):
        plan["decision"] = "FINISH"
        plan["plan_degraded"] = True
        plan["revision_reason"] = "需修订但已达上限：" + "；".join(reasons)
        return plan

    if int(plan.get("llm_round") or 0) >= int(plan.get("max_llm_rounds") or MAX_LLM_ROUNDS):
        plan["decision"] = "FINISH"
        plan["plan_degraded"] = True
        plan["revision_reason"] = "会签大轮达上限：" + "；".join(reasons)
        return plan

    plan["decision"] = "REVISE"
    plan["revise_scope"] = scope
    plan["strategy_bias"] = bias
    plan["revision_reason"] = "；".join(reasons)
    return plan


def apply_revise(plan: dict[str, Any]) -> dict[str, Any]:
    """消费一次 REVISE：revision+1，记 history。"""
    plan = dict(plan)
    plan["revision"] = int(plan.get("revision") or 0) + 1
    hist = list(plan.get("history") or [])
    hist.append(
        {
            "revision": plan["revision"],
            "reason": plan.get("revision_reason"),
            "scope": plan.get("revise_scope"),
            "bias": dict(plan.get("strategy_bias") or {}),
        }
    )
    plan["history"] = hist
    plan["decision"] = "CONTINUE"
    return plan

