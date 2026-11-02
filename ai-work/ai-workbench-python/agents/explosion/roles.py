"""
会签角色：Signal / Risk / Strategy（LLM 优先，失败则规则降级）。
"""

from __future__ import annotations

import json
from typing import Any

from agents.explosion.council_json import llm_json, slim_candidates
from clients.llm_client import LlmClient

SIGNAL_SYSTEM = """你是爆品信号官。根据候选 JSON 的 ops（运营接口字段）输出意见，禁止编造数字。
只输出 JSON：
{"items":[{"sku_id":"...","signal_confidence":"HIGH|MID|LOW","attribution":"短文","looks_like_breakout":true,"cited_fields":["orderSales","orderNumbers"]}]}
数字只引用 ops.orderSales/orderNumbers/goodsPv/goodsUv/ratePer；昨日 PV/UV 与实时销售不是同一窗口。
confidence：实时销售与订单都强→HIGH；流量高但实时订单弱或字段缺失→LOW。"""

RISK_SYSTEM = """你是爆品风控官。根据候选 JSON 输出意见，禁止编造 rule_id。
只输出 JSON：
{"items":[{"sku_id":"...","veto":false,"severity_view":"NONE|LOW|MID|HIGH","fix_first":["STOCK_LOW"],"rationale":"短文","cited_rule_ids":["STOCK_LOW"]}]}
quality_risk_level=HIGH 或硬规则（STOCK_LOW/PROFIT_NEGATIVE/PRICE_BELOW_COST）时应倾向 veto=true。"""

STRATEGY_SYSTEM = """你是爆品策略官。结合目标、信号、风控给出动作分型。禁止改 explosion_score。
只输出 JSON：
{"items":[{"sku_id":"...","action_bucket":"PUSH|FIX_THEN_PUSH|WATCH|DROP","primary_action":"短文","in_focus_slot":false,"rationale":"短文","goal_mode":"GMV"}]}
约束：Risk.veto=true 时不得 PUSH，至少 FIX_THEN_PUSH 或 DROP。
PUSH+FIX_THEN_PUSH 标记 in_focus_slot 的数量不得超过 focus_slots。
若 plan_bias 要求偏严/偏观察，请遵守。"""


def _rules_signal(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = []
    for c in candidates:
        score = float(c.get("explosion_score") or 0)
        risk = str(c.get("quality_risk_level") or "NONE")
        skipped = c.get("skipped_items") or []
        if score >= 75 and risk in {"NONE", "LOW"} and len(skipped) < 3:
            conf = "HIGH"
            breakout = True
        elif score >= 55:
            conf = "MID"
            breakout = score >= 65
        else:
            conf = "LOW"
            breakout = False
        items.append(
            {
                "sku_id": c.get("sku_id"),
                "signal_confidence": conf,
                "attribution": f"代码分 {score}，风险 {risk}",
                "looks_like_breakout": breakout,
                "cited_fields": ["orderSales", "orderNumbers"],
                "degraded": True,
            }
        )
    return items


def _rules_risk(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hard = {"STOCK_LOW", "PROFIT_NEGATIVE", "PRICE_BELOW_COST"}
    items = []
    for c in candidates:
        risk = str(c.get("quality_risk_level") or "NONE")
        rules = list(c.get("quality_rule_ids") or [])
        veto = risk == "HIGH" or bool(hard.intersection(rules))
        items.append(
            {
                "sku_id": c.get("sku_id"),
                "veto": veto,
                "severity_view": risk,
                "fix_first": [r for r in rules if r in hard] or rules[:2],
                "rationale": f"规则命中 {rules or '无'}",
                "cited_rule_ids": rules,
                "degraded": True,
            }
        )
    return items


def _rules_strategy(
    candidates: list[dict[str, Any]],
    *,
    signal_by: dict[str, dict[str, Any]],
    risk_by: dict[str, dict[str, Any]],
    goal_mode: str,
    focus_slots: int,
    bias: dict[str, Any],
) -> list[dict[str, Any]]:
    prefer_fix = bool(bias.get("prefer_fix_then_push"))
    prefer_watch = bool(bias.get("prefer_watch"))
    prefer_drop_weak_profit = bool(bias.get("prefer_drop_weak_profit"))
    items = []
    for c in candidates:
        sku = str(c.get("sku_id"))
        score = float(c.get("explosion_score") or 0)
        sig = signal_by.get(sku) or {}
        risk = risk_by.get(sku) or {}
        veto = bool(risk.get("veto"))
        conf = str(sig.get("signal_confidence") or "MID")
        qrisk = str(c.get("quality_risk_level") or "NONE")

        if veto and score >= 55:
            bucket = "FIX_THEN_PUSH"
        elif veto:
            bucket = "DROP"
        elif prefer_watch and conf == "LOW":
            bucket = "WATCH"
        elif prefer_fix and qrisk in {"MID", "HIGH"}:
            bucket = "FIX_THEN_PUSH" if score >= 50 else "DROP"
        elif goal_mode == "PROFIT" and prefer_drop_weak_profit:
            rules = set(c.get("quality_rule_ids") or [])
            if rules.intersection({"PROFIT_LOW", "PROFIT_NEGATIVE"}):
                bucket = "DROP" if score < 70 else "FIX_THEN_PUSH"
            elif score >= 70 and conf == "HIGH":
                bucket = "PUSH"
            elif score >= 45:
                bucket = "WATCH"
            else:
                bucket = "DROP"
        elif score >= 70 and conf in {"HIGH", "MID"} and not veto:
            bucket = "PUSH"
        elif score >= 50:
            bucket = "FIX_THEN_PUSH" if qrisk in {"MID", "HIGH"} else "WATCH"
        else:
            bucket = "DROP"

        if veto and bucket == "PUSH":
            bucket = "FIX_THEN_PUSH"

        items.append(
            {
                "sku_id": sku,
                "action_bucket": bucket,
                "primary_action": _action_text(bucket, risk),
                "in_focus_slot": False,
                "rationale": f"信号{conf}/veto={veto}/goal={goal_mode}",
                "goal_mode": goal_mode,
                "degraded": True,
            }
        )

    # 槽位
    used = 0
    slots = max(1, min(focus_slots, 10))
    for it in items:
        if it["action_bucket"] in {"PUSH", "FIX_THEN_PUSH"} and used < slots:
            it["in_focus_slot"] = True
            used += 1
    return items


def _action_text(bucket: str, risk: dict[str, Any]) -> str:
    if bucket == "PUSH":
        return "本周可加大曝光与转化实验"
    if bucket == "FIX_THEN_PUSH":
        fixes = ",".join(risk.get("fix_first") or []) or "风险项"
        return f"先处理 {fixes} 再放量"
    if bucket == "WATCH":
        return "观察信号，暂不加大投入"
    return "本周不建议主推"


async def run_signal_council(
    candidates: list[dict[str, Any]],
    llm: LlmClient | None,
) -> tuple[list[dict[str, Any]], str]:
    """信号官。"""
    user = json.dumps({"candidates": slim_candidates(candidates)}, ensure_ascii=False)
    obj, source = await llm_json(llm, system=SIGNAL_SYSTEM, user=user)
    if obj and isinstance(obj.get("items"), list) and obj["items"]:
        return obj["items"], source
    return _rules_signal(candidates), "rules_degraded"


async def run_risk_council(
    candidates: list[dict[str, Any]],
    llm: LlmClient | None,
) -> tuple[list[dict[str, Any]], str]:
    """风控官。"""
    user = json.dumps({"candidates": slim_candidates(candidates)}, ensure_ascii=False)
    obj, source = await llm_json(llm, system=RISK_SYSTEM, user=user)
    if obj and isinstance(obj.get("items"), list) and obj["items"]:
        return obj["items"], source
    return _rules_risk(candidates), "rules_degraded"


async def run_strategy_council(
    candidates: list[dict[str, Any]],
    *,
    signal_items: list[dict[str, Any]],
    risk_items: list[dict[str, Any]],
    goal_mode: str,
    focus_slots: int,
    bias: dict[str, Any],
    llm: LlmClient | None,
) -> tuple[list[dict[str, Any]], str]:
    """策略官。"""
    signal_by = {str(x.get("sku_id")): x for x in signal_items}
    risk_by = {str(x.get("sku_id")): x for x in risk_items}
    payload = {
        "goal_mode": goal_mode,
        "focus_slots": focus_slots,
        "plan_bias": bias,
        "candidates": slim_candidates(candidates),
        "signal": signal_items,
        "risk": risk_items,
    }
    obj, source = await llm_json(
        llm, system=STRATEGY_SYSTEM, user=json.dumps(payload, ensure_ascii=False)
    )
    if obj and isinstance(obj.get("items"), list) and obj["items"]:
        # 硬约束修补：veto 不得 PUSH；槽位截断
        fixed = []
        used = 0
        slots = max(1, min(focus_slots, 10))
        for it in obj["items"]:
            sku = str(it.get("sku_id"))
            bucket = str(it.get("action_bucket") or "WATCH")
            if risk_by.get(sku, {}).get("veto") and bucket == "PUSH":
                bucket = "FIX_THEN_PUSH"
            in_slot = bool(it.get("in_focus_slot")) and bucket in {
                "PUSH",
                "FIX_THEN_PUSH",
            }
            if in_slot and used >= slots:
                in_slot = False
            if in_slot:
                used += 1
            fixed.append(
                {
                    **it,
                    "action_bucket": bucket,
                    "in_focus_slot": in_slot,
                    "goal_mode": goal_mode,
                    "primary_action": it.get("primary_action")
                    or _action_text(bucket, risk_by.get(sku) or {}),
                }
            )
        # 若 LLM 没占满合理槽位，按 rank 补
        if used < slots:
            for it in fixed:
                if (
                    not it["in_focus_slot"]
                    and it["action_bucket"] in {"PUSH", "FIX_THEN_PUSH"}
                    and used < slots
                ):
                    it["in_focus_slot"] = True
                    used += 1
        return fixed, source

    return (
        _rules_strategy(
            candidates,
            signal_by=signal_by,
            risk_by=risk_by,
            goal_mode=goal_mode,
            focus_slots=focus_slots,
            bias=bias,
        ),
        "rules_degraded",
    )

