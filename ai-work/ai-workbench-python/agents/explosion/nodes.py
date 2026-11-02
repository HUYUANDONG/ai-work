"""Explosion LangGraph 节点（业务逻辑；编排在 lg_graph）。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from agents.explosion.campaign import apply_revise, init_plan, plan_decide
from agents.explosion.council import COUNCIL_VERSION, _focus_preview, council_reduce
from agents.explosion.roles import (
    run_risk_council,
    run_signal_council,
    run_strategy_council,
)
from agents.explosion.state import ExplosionState
from harness.runtime import AppRuntime
from harness.task_control import TaskControl
from reporting.builder import build_explosion_report
from scoring import config as scoring_config
from scoring.pipeline import rank_candidates
from tools.features import query_features
from tools.reports import upsert_explosion_report

logger = logging.getLogger(__name__)


def _cfg(config: RunnableConfig) -> tuple[AppRuntime, TaskControl | None]:
    conf = (config or {}).get("configurable") or {}
    runtime: AppRuntime = conf["runtime"]
    control: TaskControl | None = conf.get("control")
    return runtime, control


def _build_summary(
    candidates: list[dict[str, Any]],
    *,
    goal_mode: str,
    slots: int,
    plan: dict[str, Any],
) -> str:
    focus = [c for c in candidates if c.get("in_focus_slot")]
    parts = [
        f"目标 {goal_mode}，本周槽位 {slots}，实际进槽 {len(focus)} 个。",
        f"会签轮次 {plan.get('llm_round')}，修订 {plan.get('revision')} 次。",
    ]
    if plan.get("plan_degraded"):
        parts.append(f"计划降级：{plan.get('revision_reason')}")
    elif plan.get("revision_reason"):
        parts.append(str(plan.get("revision_reason")))
    for c in focus[:5]:
        parts.append(
            f"{c.get('sku_id')}→{c.get('action_bucket')}（分 {c.get('explosion_score')}，"
            f"风险 {c.get('quality_risk_level')}）"
        )
    return " ".join(parts)


async def node_load_features(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    runtime, control = _cfg(config)
    task_input = dict(state.get("task_input") or {})
    if control:
        await control.emit("load_features", "正在拉取商品特征…")
        await control.checkpoint(progress="load_features")

    features = await query_features(
        runtime,
        on_sale_only=bool(task_input.get("on_sale_only", True)),
        sku_ids=task_input.get("sku_ids"),
        category_id=task_input.get("category_id"),
        stat_date=task_input.get("stat_date"),
    )
    items = features.get("items") or []
    if not items:
        if control:
            await control.emit("failed", "特征为空，已停止")
        return {
            "features": features,
            "status": "FAILED_NO_FEATURES",
            "message": "特征为空，已阻断打分与报表。",
            "next_action": "abort",
        }
    return {
        "features": features,
        "goal_mode": str(task_input.get("goal_mode") or "GMV"),
        "focus_slots": int(task_input.get("focus_slots") or 5),
        "top_n": int(task_input.get("top_n") or scoring_config.DEFAULT_TOP_N),
        "next_action": "signal_risk",
        "status": "RUNNING",
    }


async def node_score(state: ExplosionState, config: RunnableConfig) -> dict[str, Any]:
    _, control = _cfg(config)
    features = state.get("features") or {}
    items = list(features.get("items") or [])
    top_n = int(state.get("top_n") or scoring_config.DEFAULT_TOP_N)
    if control:
        await control.emit(
            "scoring",
            "正在打分并挂质检标签…",
            detail=f"候选池约 {len(items)} 行，取 Top {top_n}",
        )
        await control.checkpoint(progress="scoring")

    ranked = rank_candidates(items, top_n=top_n)
    if control:
        await control.emit(
            "scored",
            f"已得到 Top {len(ranked['candidates'])} 候选",
            data={
                "pool_size": ranked["pool_size"],
                "top": [
                    {
                        "sku_id": c.get("sku_id"),
                        "explosion_score": c.get("explosion_score"),
                        "quality_risk_level": c.get("quality_risk_level"),
                    }
                    for c in ranked["candidates"][:5]
                ],
            },
        )
    plan = init_plan(
        goal_mode=str(state.get("goal_mode") or "GMV"),
        focus_slots=int(state.get("focus_slots") or 5),
    )
    return {
        "ranked": ranked,
        "candidates": ranked["candidates"],
        "plan": plan,
        "council_sources": {"rounds": []},
        "revise_scope": "FULL",
        "next_action": "signal_risk",
    }


async def node_signal_risk(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    runtime, control = _cfg(config)
    candidates = list(state.get("candidates") or [])
    plan = dict(state.get("plan") or {})
    plan["llm_round"] = int(plan.get("llm_round") or 0) + 1
    round_no = plan["llm_round"]

    if control:
        await control.checkpoint(progress=f"council_round_{round_no}")
        await control.emit(
            "council_round",
            f"会签第 {round_no} 轮",
            detail="信号官与风控官并行评估",
            data={"round": round_no, "scope": "FULL"},
        )
        await control.emit("signal_risk", "信号官与风控官评估中…")

    (signal_items, sig_src), (risk_items, risk_src) = await asyncio.gather(
        run_signal_council(candidates, runtime.llm_client),
        run_risk_council(candidates, runtime.llm_client),
    )

    if control:
        await control.checkpoint(progress="signal_risk_done")
        veto_n = sum(1 for r in risk_items if r.get("veto"))
        await control.emit(
            "signal_risk_done",
            "信号/风控意见已出",
            detail=f"否决 {veto_n} 个；信号源={sig_src}，风控源={risk_src}",
            data={"veto_count": veto_n},
        )

    return {
        "plan": plan,
        "signal_items": signal_items,
        "risk_items": risk_items,
        "signal_source": sig_src,
        "risk_source": risk_src,
        "revise_scope": "FULL",
        "next_action": "strategy",
    }


async def node_strategy(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    runtime, control = _cfg(config)
    candidates = list(state.get("candidates") or [])
    plan = dict(state.get("plan") or {})
    # 仅策略修订时也要推进轮次
    if str(state.get("revise_scope") or "") == "STRATEGY_ONLY":
        plan["llm_round"] = int(plan.get("llm_round") or 0) + 1
        if control:
            await control.checkpoint(progress=f"council_round_{plan['llm_round']}")
            await control.emit(
                "council_round",
                f"会签第 {plan['llm_round']} 轮（仅策略）",
                data={"scope": "STRATEGY_ONLY", "bias": plan.get("strategy_bias")},
            )

    if control:
        await control.emit("strategy", "策略官分配动作与槽位…")

    strategy_items, strat_src = await run_strategy_council(
        candidates,
        signal_items=list(state.get("signal_items") or []),
        risk_items=list(state.get("risk_items") or []),
        goal_mode=str(state.get("goal_mode") or "GMV"),
        focus_slots=int(state.get("focus_slots") or 5),
        bias=dict(plan.get("strategy_bias") or {}),
        llm=runtime.llm_client,
    )
    return {
        "plan": plan,
        "strategy_items": strategy_items,
        "strategy_source": strat_src,
        "next_action": "strategy",
    }


async def node_reduce_decide(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    _, control = _cfg(config)
    candidates = list(state.get("candidates") or [])
    focus_slots = int(state.get("focus_slots") or 5)
    plan = dict(state.get("plan") or {})
    sources = dict(state.get("council_sources") or {"rounds": []})
    rounds = list(sources.get("rounds") or [])

    council_reduce(
        candidates,
        signal_items=list(state.get("signal_items") or []),
        risk_items=list(state.get("risk_items") or []),
        strategy_items=list(state.get("strategy_items") or []),
        focus_slots=focus_slots,
    )

    rounds.append(
        {
            "round": plan.get("llm_round"),
            "signal": state.get("signal_source"),
            "risk": state.get("risk_source"),
            "strategy": state.get("strategy_source"),
            "bias": plan.get("strategy_bias"),
        }
    )
    sources["rounds"] = rounds

    if control:
        await control.emit(
            "reduce_done",
            "合并会签意见",
            detail="已落实否决约束与槽位上限",
            data={"focus_preview": _focus_preview(candidates)},
        )

    plan = plan_decide(
        candidates,
        plan,
        signal_items=list(state.get("signal_items") or []),
        risk_items=list(state.get("risk_items") or []),
    )
    decision = plan.get("decision")
    if control:
        await control.emit(
            "campaign_decide",
            "指挥裁决：" + str(decision),
            detail=str(plan.get("revision_reason") or ""),
            data={"decision": decision, "revision": plan.get("revision")},
        )
        await control.checkpoint(progress=f"decide_{decision}")

    if decision == "REVISE":
        from agents.explosion.campaign import MAX_LLM_ROUNDS
        from harness.memory.progress import ProgressBreaker

        # 进度感知：动作桶指纹不变则计空转，连续空转则强制结束
        fp = "|".join(
            f"{c.get('sku_id')}:{c.get('action_bucket')}:{c.get('in_focus_slot')}"
            for c in candidates
        )
        breaker_state = plan.get("_progress_breaker") or {}
        breaker = ProgressBreaker(
            max_idle=int(breaker_state.get("max_idle") or 2),
            idle=int(breaker_state.get("idle") or 0),
            last_fingerprint=str(breaker_state.get("last_fingerprint") or ""),
        )
        obs = breaker.observe(fp, label="revise")
        plan["_progress_breaker"] = {
            "max_idle": breaker.max_idle,
            "idle": breaker.idle,
            "last_fingerprint": breaker.last_fingerprint,
        }

        if obs == "TRIPPED" or int(plan.get("llm_round") or 0) >= MAX_LLM_ROUNDS:
            plan["decision"] = "FINISH"
            plan["plan_degraded"] = True
            reason = plan.get("revision_reason") or ""
            if obs == "TRIPPED":
                reason = (reason + "；" if reason else "") + "修订无实质进展，进度熔断"
            else:
                reason = (reason + "；" if reason else "") + "大轮达上限强制结束"
            plan["revision_reason"] = reason
            if control:
                await control.emit(
                    "council_degraded",
                    "会签降级结束",
                    detail=reason,
                )
            return {
                "candidates": candidates,
                "plan": plan,
                "council_sources": sources,
                "next_action": "finish",
            }

        plan = apply_revise(plan)
        scope = str(plan.get("revise_scope") or "STRATEGY_ONLY")
        if control:
            await control.emit(
                "revise",
                f"发现不合理，开始第 {plan['revision']} 次修订",
                detail=str(plan.get("revision_reason") or ""),
                data={"bias": plan.get("strategy_bias"), "scope": scope},
            )
        return {
            "candidates": candidates,
            "plan": plan,
            "council_sources": sources,
            "revise_scope": scope,
            "next_action": "strategy" if scope == "STRATEGY_ONLY" else "signal_risk",
        }

    if control:
        await control.emit(
            "council_done",
            "会签结束",
            detail=f"修订 {plan.get('revision')} 次，降级={bool(plan.get('plan_degraded'))}",
            data={"focus_preview": _focus_preview(candidates)},
        )
    return {
        "candidates": candidates,
        "plan": plan,
        "council_sources": sources,
        "next_action": "finish",
    }


async def node_report_upsert(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    runtime, control = _cfg(config)
    task_id = str(state.get("task_id") or "unknown-task")
    conversation_id = state.get("conversation_id") or "mock-conversation"
    user_id = state.get("user_id") or "mock-user"
    task_input = dict(state.get("task_input") or {})
    ranked = dict(state.get("ranked") or {})
    ranked["candidates"] = list(state.get("candidates") or [])
    plan = dict(state.get("plan") or {})
    features = state.get("features") or {}
    goal_mode = str(state.get("goal_mode") or "GMV")
    focus_slots = int(state.get("focus_slots") or 5)

    summary = _build_summary(
        ranked["candidates"],
        goal_mode=goal_mode,
        slots=focus_slots,
        plan=plan,
    )

    if control:
        await control.emit("report_html", "正在生成可下载分析报表…")
        await control.checkpoint(progress="report_html")

    report_files = await build_explosion_report(
        task_id=task_id,
        ranked_result=ranked,
        task_input=task_input,
        snapshot_date=features.get("snapshot_date"),
        llm=runtime.llm_client,
        output_dir=runtime.report_dir(),
    )

    explosion_report = {
        "header": {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "snapshot_date": features.get("snapshot_date"),
            "scoring_version": ranked.get("scoring_version"),
            "council_version": COUNCIL_VERSION,
            "time_window_days": int(task_input.get("time_window_days") or 30),
            "top_n": ranked.get("top_n"),
            "item_count": len(ranked["candidates"]),
            "goal_mode": goal_mode,
            "focus_slots": focus_slots,
            "plan_degraded": bool(plan.get("plan_degraded")),
            "focus_count": sum(1 for c in ranked["candidates"] if c.get("in_focus_slot")),
            "summary": summary,
            "council_meta": {
                "revision": plan.get("revision"),
                "llm_round": plan.get("llm_round"),
                "history": plan.get("history"),
                "sources": state.get("council_sources"),
                "orchestrator": "langgraph",
            },
        },
        "items": ranked["candidates"],
    }
    try:
        await upsert_explosion_report(runtime, task_id, explosion_report)
        upserted = True
    except Exception:
        logger.exception("upsert_explosion_report failed")
        upserted = False

    if control:
        await control.emit(
            "done",
            "分析完成",
            detail=summary[:200],
            data={"download": report_files.get("download")},
        )

    result = {
        "status": "REPORT_READY",
        "task_id": task_id,
        "snapshot_date": features.get("snapshot_date"),
        "row_count": features.get("row_count"),
        "pool_size": ranked.get("pool_size"),
        "scoring_version": ranked.get("scoring_version"),
        "council_version": COUNCIL_VERSION,
        "plan_degraded": bool(plan.get("plan_degraded")),
        "council_revision": plan.get("revision"),
        "council_rounds": plan.get("llm_round"),
        "top_n": ranked.get("top_n"),
        "candidates": ranked["candidates"],
        "html_source": report_files["html_source"],
        "report_path": report_files["report_path"],
        "download": report_files["download"],
        "summary": summary,
        "upserted": upserted,
        "input": task_input,
        "mock": bool(features.get("mock")),
        "orchestrator": "langgraph",
        "message": (
            f"已生成 Top {ranked.get('top_n')} 作战清单"
            f"（LangGraph 会签{plan.get('llm_round')}轮/修订{plan.get('revision')}次，"
            f"HTML={report_files['html_source']}）。"
            "前端请根据 download 展示下载按钮。"
        ),
    }
    return {
        "summary": summary,
        "report_files": report_files,
        "upserted": upserted,
        "status": "REPORT_READY",
        "result": result,
        "next_action": "finish",
    }

