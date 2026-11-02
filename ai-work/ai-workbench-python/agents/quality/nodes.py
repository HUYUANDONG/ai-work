"""Quality LangGraph 节点。"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.runnables import RunnableConfig

from agents.quality.state import QualityState
from clients.llm_client import LlmClient
from harness.runtime import AppRuntime
from scoring import config as scoring_config
from scoring.explosion import score_sku
from scoring.quality import check_sku
from scoring.store_stats import build_store_stats
from tools.features import query_features
from tools.reports import upsert_quality_report

logger = logging.getLogger(__name__)
MAX_EXPLAIN = 50
EXPLAIN_SYSTEM = """你是质检顾问。对每个有问题的 SKU，根据 issues 写一句 ai_comment（中文，可执行）。
输出 JSON 对象：{"comments":{"SKU-001":"..."}, "summary":"整份报告一句话总结"}。
禁止改分数；禁止编造 rule_id。不要用 Markdown 围栏。"""


def _runtime(config: RunnableConfig) -> AppRuntime:
    return ((config or {}).get("configurable") or {})["runtime"]


def _template_comments(rows: list[dict[str, Any]]) -> tuple[dict[str, str], str]:
    comments: dict[str, str] = {}
    high = 0
    for r in rows:
        if r.get("risk_level") in {"HIGH", "MID"}:
            if r.get("risk_level") == "HIGH":
                high += 1
            rules = ",".join(i["rule_id"] for i in (r.get("issues") or [])[:3])
            tip = "先修再冲" if (r.get("explosion_score") or 0) >= 70 else "优先处理风险"
            comments[str(r["sku_id"])] = f"命中 {rules}。{tip}。"
    summary = f"共 {len(rows)} 个问题品，其中高风险 {high} 个。请优先处理高风险项。"
    return comments, summary


async def node_load(state: QualityState, config: RunnableConfig) -> dict[str, Any]:
    runtime = _runtime(config)
    task_input = dict(state.get("task_input") or {})
    sku_ids = task_input.get("sku_ids")
    features = await query_features(
        runtime,
        on_sale_only=bool(task_input.get("on_sale_only", True)),
        sku_ids=list(sku_ids)[:50] if sku_ids else None,
        category_id=task_input.get("category_id"),
        stat_date=task_input.get("stat_date"),
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
    _ = config
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
    runtime = _runtime(config)
    rows = list(state.get("rows") or [])
    comments, summary = _template_comments(rows)
    explain_source = "template"
    llm: LlmClient | None = runtime.llm_client
    if llm is not None and llm.enabled and rows:
        try:
            slim = [
                {
                    "sku_id": r["sku_id"],
                    "risk_level": r["risk_level"],
                    "explosion_score": r["explosion_score"],
                    "issues": r["issues"],
                }
                for r in rows
            ]
            raw = await llm.chat(
                system=EXPLAIN_SYSTEM,
                user=json.dumps({"items": slim}, ensure_ascii=False),
            )
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:].strip()
            parsed = json.loads(raw)
            if isinstance(parsed.get("comments"), dict):
                comments.update({str(k): str(v) for k, v in parsed["comments"].items()})
            if parsed.get("summary"):
                summary = str(parsed["summary"])
            explain_source = "llm"
        except Exception:
            logger.exception("quality LLM explain failed")
            explain_source = "template_fallback"

    for r in rows:
        for issue in r["issues"]:
            issue["ai_comment"] = comments.get(str(r["sku_id"]), "")
            issue.setdefault("evidence", issue.get("rule_id", ""))
            issue.setdefault("sample_size", None)
            issue.setdefault("threshold", None)
            issue.setdefault("actual", None)

    return {"rows": rows, "summary": summary, "explain_source": explain_source}


async def node_upsert(state: QualityState, config: RunnableConfig) -> dict[str, Any]:
    runtime = _runtime(config)
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

