"""Explosion LangGraph 节点（业务逻辑；编排在 lg_graph）。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from agents.chat.intent import ADVICE_OFFER_QUESTION
from agents.explosion.campaign import init_plan
from agents.explosion.narrative import build_operator_report
from agents.explosion.state import ExplosionState
from agents.supervisor.workbench import WorkbenchSupervisor
from harness.runtime import AppRuntime
from harness.task_control import TaskControl
from reporting.builder import build_explosion_report
from scoring import config as scoring_config
from scoring.pipeline import rank_candidates
from tools.features import query_advise_context, query_features
from tools.reports import upsert_explosion_report

logger = logging.getLogger(__name__)

AGENT_VERSION = "explosion-agent-v1"


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
    features: dict[str, Any] | None = None,
    thinking_events: list[dict[str, Any]] | None = None,
    task_input: dict[str, Any] | None = None,
    advise_context: dict[str, Any] | None = None,
    advise_llm_text: str | None = None,
    offer_advise: bool = False,
    explosion_analysis: str | None = None,
) -> str:
    """运营可读结论。"""
    base = build_operator_report(
        candidates,
        goal_mode=goal_mode,
        slots=slots,
        plan=plan,
        features=features,
        thinking_events=thinking_events,
        task_input=task_input,
        advise_context=advise_context,
        advise_llm_text=advise_llm_text,
        offer_advise=offer_advise,
        advice_offer_question=ADVICE_OFFER_QUESTION,
    )
    analysis = (explosion_analysis or "").strip()
    if analysis:
        return f"{base}\n\n【爆品解读】\n{analysis}"
    return base


def _supervisor(runtime: AppRuntime) -> WorkbenchSupervisor:
    if runtime.supervisor is None:
        runtime.supervisor = WorkbenchSupervisor.create(llm=runtime.llm_client)
    return runtime.supervisor


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
        user_id=str(state.get("user_id") or ""),
        time_window_days=int(task_input.get("time_window_days") or 30),
        profile="score",
    )
    items = features.get("items") or []
    amount_unit = features.get("amount_unit") or features.get("amountUnit")
    if amount_unit and items:
        for row in items:
            if isinstance(row, dict) and not row.get("amount_unit"):
                row["amount_unit"] = amount_unit
    if not items:
        source = str(features.get("source") or "")
        detail = str(features.get("message") or "")
        if source == "no_credentials":
            message = "拉不到真实销量：工作台还没有电商登录 token。请在已登录后台的页面重新发起分析。"
        elif source == "error":
            message = "调用 goodsStatList 失败：" + (detail or "未知错误")
        else:
            message = "特征为空，已阻断打分与报表。"
        if control:
            await control.emit("failed", message)
        return {
            "features": features,
            "status": "FAILED_NO_FEATURES",
            "message": message,
            "next_action": "abort",
        }
    if control:
        sample = items[0] if items else {}
        await control.emit(
            "load_features_done",
            f"已拉取 {len(items)} 个在售商品销量",
            detail=(
                f"来源 {features.get('source')}；样例「{sample.get('title') or sample.get('sku_id')}」"
                f"销售额 {sample.get('gmv_30d')}、订单 {sample.get('orders_30d')}"
            ),
        )
    return {
        "features": features,
        "goal_mode": str(task_input.get("goal_mode") or "GMV"),
        "focus_slots": int(task_input.get("focus_slots") or 5),
        "top_n": int(task_input.get("top_n") or scoring_config.DEFAULT_TOP_N),
        "next_action": "explosion",
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
            detail=f"候选池 {ranked['pool_size']}",
        )
    plan = init_plan(
        goal_mode=str(state.get("goal_mode") or "GMV"),
        focus_slots=int(state.get("focus_slots") or 5),
    )
    return {
        "ranked": ranked,
        "candidates": ranked["candidates"],
        "plan": plan,
        "next_action": "explosion",
    }


async def node_explosion(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    """规则榜后：爆品 Agent 解读 + 有限进槽重排。"""
    runtime, control = _cfg(config)
    candidates = list(state.get("candidates") or [])
    if control:
        await control.emit("explosion", "爆品 Agent 解读并微调进槽…")
        await control.checkpoint(progress="explosion")

    result = await _supervisor(runtime).run_explosion(
        candidates=candidates,
        focus_slots=int(state.get("focus_slots") or 5),
        goal_mode=str(state.get("goal_mode") or "GMV"),
        llm=runtime.llm_client,
    )
    data = dict(result.data or {})
    out_cands = list(data.get("candidates") or candidates)
    analysis = str(data.get("text") or "")
    if control:
        await control.emit(
            "explosion_done",
            "爆品解读完成",
            detail=f"source={result.source}",
        )
    ranked = dict(state.get("ranked") or {})
    ranked["candidates"] = out_cands
    return {
        "candidates": out_cands,
        "ranked": ranked,
        "explosion_analysis": analysis,
        "explosion_source": result.source or "template",
        "next_action": "advise",
    }


async def node_load_advise_context(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    runtime, control = _cfg(config)
    candidates = list(state.get("candidates") or [])
    focus_ids = [
        str(c.get("sku_id"))
        for c in candidates
        if c.get("in_focus_slot") and c.get("sku_id") is not None
    ]
    if not focus_ids:
        focus_ids = [
            str(c.get("sku_id")) for c in candidates[:5] if c.get("sku_id") is not None
        ]
    user_id = str(state.get("user_id") or "")
    if control:
        await control.emit(
            "advise_context",
            "正在拉取板块流量以生成投放建议…",
            detail=f"槽位 SKU {len(focus_ids)} 个",
        )
        await control.checkpoint(progress="advise_context")

    try:
        advise = await query_advise_context(
            runtime,
            user_id=user_id,
            sku_ids=focus_ids,
            days=7,
        )
    except Exception as exc:
        logger.exception("query_advise_context failed")
        advise = {
            "sku_ids": focus_ids,
            "plates": [],
            "store": {},
            "source": "error",
            "message": str(exc),
        }

    plates = advise.get("plates") or []
    if control:
        await control.emit(
            "advise_context_done",
            "板块辅源已就绪",
            detail=f"source={advise.get('source')}，板块 {len(plates)} 条",
        )
    return {
        "advise_context": advise,
        "next_action": "advise",
    }


async def node_write_advise(
    state: ExplosionState, config: RunnableConfig
) -> dict[str, Any]:
    runtime, control = _cfg(config)
    candidates = list(state.get("candidates") or [])
    advise = dict(state.get("advise_context") or {})
    goal_mode = str(state.get("goal_mode") or "GMV")
    if control:
        await control.emit(
            "advise_llm",
            "正在结合板块流量撰写投放建议…",
            detail=f"板块 {len(advise.get('plates') or [])} 条",
        )
        await control.checkpoint(progress="advise_llm")

    async def _on_delta(delta: str) -> None:
        if control:
            await control.emit_llm_delta(delta)

    advised = await _supervisor(runtime).run_placement_advise(
        candidates=candidates,
        advise_context=advise,
        goal_mode=goal_mode,
        on_delta=_on_delta if control else None,
    )
    written = dict(advised.data or {})
    if control:
        await control.emit(
            "advise_llm_done",
            "投放建议已生成",
            detail=f"source={written.get('source')}",
        )
    return {
        "advise_llm_text": str(written.get("text") or ""),
        "advise_llm_source": str(written.get("source") or advised.source or "template"),
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
    advise_context = state.get("advise_context") or {}
    advise_llm_text = state.get("advise_llm_text")
    include_advise = bool(task_input.get("include_advise"))
    goal_mode = str(state.get("goal_mode") or "GMV")
    focus_slots = int(state.get("focus_slots") or 5)

    summary = _build_summary(
        ranked["candidates"],
        goal_mode=goal_mode,
        slots=focus_slots,
        plan=plan,
        features=features,
        thinking_events=list(control.events) if control else [],
        task_input=task_input,
        advise_context=advise_context if include_advise else {},
        advise_llm_text=advise_llm_text if include_advise else None,
        offer_advise=not include_advise,
        explosion_analysis=str(state.get("explosion_analysis") or ""),
    )

    if control:
        await control.emit("report_html", "正在生成分析报表…")
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
            "agent_version": AGENT_VERSION,
            "time_window_days": int(task_input.get("time_window_days") or 30),
            "top_n": ranked.get("top_n"),
            "item_count": len(ranked["candidates"]),
            "goal_mode": goal_mode,
            "focus_slots": focus_slots,
            "focus_count": sum(1 for c in ranked["candidates"] if c.get("in_focus_slot")),
            "summary": summary,
            "explosion_source": state.get("explosion_source"),
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
        "agent_version": AGENT_VERSION,
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
        "advice_offer_pending": not include_advise,
        "include_advise": include_advise,
        "advise_llm_source": state.get("advise_llm_source"),
        "explosion_source": state.get("explosion_source"),
        "message": (
            f"已生成 Top {ranked.get('top_n')} 作战清单"
            f"（规则打分 + 爆品 Agent，HTML={report_files['html_source']}）。"
            + (
                "已含投放建议。"
                if include_advise
                else "榜单已出，等待确认是否写投放建议。"
            )
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
