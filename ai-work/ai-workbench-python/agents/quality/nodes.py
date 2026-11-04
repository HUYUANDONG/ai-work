"""Quality LangGraph 节点。"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from agents.quality.state import QualityState
from agents.supervisor.workbench import WorkbenchSupervisor
from harness.runtime import AppRuntime
from harness.task_control import TaskControl
from schemas.ops_fields import slim_ops_excerpt
from scoring import config as scoring_config
from scoring.explosion import score_sku
from scoring.quality import check_sku
from scoring.store_stats import build_store_stats
from tools.features import query_features
from tools.reports import upsert_quality_report

logger = logging.getLogger(__name__)
MAX_EXPLAIN = 50


def _cfg(config: RunnableConfig) -> tuple[AppRuntime, TaskControl | None]:
    """
    从 RunnableConfig 取 runtime / TaskControl。

    Args:
        config: LangGraph 配置。

    Returns:
        tuple: (AppRuntime, TaskControl|None)。
    """
    conf = (config or {}).get("configurable") or {}
    return conf["runtime"], conf.get("control")


def _runtime(config: RunnableConfig) -> AppRuntime:
    return _cfg(config)[0]


def _supervisor(runtime: AppRuntime) -> WorkbenchSupervisor:
    if runtime.supervisor is None:
        runtime.supervisor = WorkbenchSupervisor.create(llm=runtime.llm_client)
    return runtime.supervisor


async def node_load(state: QualityState, config: RunnableConfig) -> dict[str, Any]:
    runtime, control = _cfg(config)
    if control:
        await control.checkpoint(progress="quality_load")
    task_input = dict(state.get("task_input") or {})
    sku_ids = task_input.get("sku_ids")
    features = await query_features(
        runtime,
        on_sale_only=bool(task_input.get("on_sale_only", True)),
        sku_ids=list(sku_ids)[:50] if sku_ids else None,
        category_id=task_input.get("category_id"),
        stat_date=task_input.get("stat_date"),
        user_id=str(state.get("user_id") or ""),
        time_window_days=int(task_input.get("time_window_days") or 30),
    )
    items = list(features.get("items") or [])
    if not items:
        return {
            "features": features,
            "status": "FAILED_NO_FEATURES",
            "message": "特征为空，已阻断质检。",
        }
    return {"features": features, "status": "RUNNING"}


async def node_rule_check(state: QualityState, config: RunnableConfig) -> dict[str, Any]:
    _, control = _cfg(config)
    if control:
        await control.checkpoint(progress="quality_rule_check")
    task_input = dict(state.get("task_input") or {})
    sku_ids = task_input.get("sku_ids")
    storewide = bool(task_input.get("storewide_problems"))
    items = list((state.get("features") or {}).get("items") or [])
    store_stats = build_store_stats(items)
    rows: list[dict[str, Any]] = []
    for row in items:
        q = check_sku(row, store_stats=store_stats)
        exp = score_sku(row, store_stats=store_stats)
        risk = q["quality_risk_level"]
        if sku_ids:
            include = True
        else:
            include = risk != "NONE"  # 全店/问题品：只留命中项
        _ = storewide
        if not include:
            continue
        rows.append(
            {
                "sku_id": row.get("sku_id"),
                "title": row.get("title"),
                "quality_score": q["quality_score"],
                "ops_score": q["ops_score"],
                "risk_level": risk,
                "explosion_score": exp["explosion_score"],
                "explosion_candidate": exp["explosion_score"] >= 60,
                "issues": q.get("issues") or [],
                "skipped_rules": q.get("skipped_rules") or [],
                "feature_excerpt": slim_ops_excerpt(row),
            }
        )
    rows.sort(
        key=lambda r: (
            {"HIGH": 3, "MID": 2, "LOW": 1, "NONE": 0}.get(str(r["risk_level"]), 0),
            r.get("explosion_score") or 0,
        ),
        reverse=True,
    )
    return {"rows": rows[:MAX_EXPLAIN]}


async def node_explain(state: QualityState, config: RunnableConfig) -> dict[str, Any]:
    runtime, control = _cfg(config)
    if control:
        await control.checkpoint(progress="quality_explain")
    rows = list(state.get("rows") or [])
    phase = await _supervisor(runtime).phase_quality_explain(rows)
    comments = dict(phase.get("comments") or {})
    summary = str(phase.get("summary") or "")
    explain_source = str(phase.get("explain_source") or "template")

    for r in rows:
        for issue in r["issues"]:
            issue["ai_comment"] = comments.get(str(r["sku_id"]), "")
            issue.setdefault("evidence", issue.get("rule_id", ""))
            issue.setdefault("sample_size", None)
            issue.setdefault("threshold", None)
            issue.setdefault("actual", None)

    return {"rows": rows, "summary": summary, "explain_source": explain_source}


async def node_upsert(state: QualityState, config: RunnableConfig) -> dict[str, Any]:
    runtime, control = _cfg(config)
    if control:
        await control.checkpoint(progress="quality_upsert")
    task_id = str(state.get("task_id") or "unknown-task")
    conversation_id = state.get("conversation_id") or "mock-conversation"
    user_id = state.get("user_id") or "mock-user"
    rows = list(state.get("rows") or [])
    summary = str(state.get("summary") or "")
    features = state.get("features") or {}
    high_risk_count = sum(1 for r in rows if r.get("risk_level") == "HIGH")
    report = {
        "header": {
            "task_id": task_id,
            "conversation_id": conversation_id,
            "user_id": user_id,
            "snapshot_date": features.get("snapshot_date"),
            "scoring_version": scoring_config.SCORING_VERSION,
            "sku_count": len(rows),
            "high_risk_count": high_risk_count,
            "summary": summary,
            "orchestrator": "langgraph",
        },
        "items": rows,
    }
    await upsert_quality_report(runtime, task_id, report)
    result = {
        "status": "QUALITY_READY",
        "task_id": task_id,
        "snapshot_date": features.get("snapshot_date"),
        "sku_count": len(rows),
        "high_risk_count": high_risk_count,
        "explain_source": state.get("explain_source"),
        "summary": summary,
        "items": rows,
        "message": summary,
        "orchestrator": "langgraph",
    }
    return {"status": "QUALITY_READY", "result": result}

