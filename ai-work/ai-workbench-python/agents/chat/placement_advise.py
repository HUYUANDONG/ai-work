"""
对话同步投放建议：用户确认「要」后拉板块 + LLM，不重跑全店打分。
"""

from __future__ import annotations

import logging
from typing import Any

from agents.supervisor import WorkbenchSupervisor
from harness.runtime import AppRuntime
from tools.features import query_advise_context
from tools.reports import get_conversation_reports

logger = logging.getLogger(__name__)


def _focus_from_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    """从最新爆品报告抽出进槽（或 Top）候选。"""
    items = list(report.get("items") or [])
    focus = [c for c in items if c.get("in_focus_slot")]
    return focus or items[:5]


async def run_placement_advise(
    runtime: AppRuntime,
    *,
    conversation_id: str,
    user_id: str,
) -> dict[str, Any]:
    """
    基于会话最近一份爆品报告写投放建议。

    Args:
        runtime: AppRuntime。
        conversation_id: 会话。
        user_id: 电商登录态用户。

    Returns:
        dict: reply / source / focus_count / plate_count。
    """
    try:
        payload = await get_conversation_reports(
            runtime,
            conversation_id,
            user_id=user_id,
            limit=3,
        )
    except Exception:
        logger.exception("get_conversation_reports failed for placement advise")
        return {
            "reply": "还没有可用的爆品报告，请先说「近7天爆品」筛一版，再决定是否要建议。",
            "source": "no_report",
            "focus_count": 0,
            "plate_count": 0,
        }

    reports = list(payload.get("reports") or [])
    explosion = next(
        (
            r
            for r in reports
            if str(r.get("task_type") or r.get("header", {}).get("task_type") or "")
            .upper()
            .find("EXPLOSION")
            >= 0
            or (r.get("items") and (r.get("header") or {}).get("goal_mode"))
        ),
        reports[0] if reports else None,
    )
    if not explosion:
        # 无 task_type 时取最新有 items 的报告
        explosion = next((r for r in reports if r.get("items")), None)
    if not explosion:
        return {
            "reply": "还没有可用的爆品报告，请先筛一版爆品再要建议。",
            "source": "no_report",
            "focus_count": 0,
            "plate_count": 0,
        }

    candidates = _focus_from_report(explosion)
    focus_ids = [str(c.get("sku_id")) for c in candidates if c.get("sku_id") is not None]
    header = explosion.get("header") if isinstance(explosion.get("header"), dict) else {}
    goal_mode = str(header.get("goal_mode") or "GMV")

    try:
        advise = await query_advise_context(
            runtime,
            user_id=user_id,
            sku_ids=focus_ids,
            days=7,
        )
    except Exception as exc:
        logger.exception("query_advise_context failed in placement advise")
        advise = {
            "sku_ids": focus_ids,
            "plates": [],
            "store": {},
            "source": "error",
            "message": str(exc),
        }

    if runtime.supervisor is None:
        runtime.supervisor = WorkbenchSupervisor.create(llm=runtime.llm_client)
    advised = await runtime.supervisor.run_placement_advise(
        candidates=candidates,
        advise_context=advise,
        goal_mode=goal_mode,
    )
    written = dict(advised.data or {})
    text = str(written.get("text") or "").strip()
    if not text:
        text = "板块数据不足，暂时写不出投放建议；可稍后再试或先看榜单自行判断。"
    return {
        "reply": text,
        "source": written.get("source") or advised.source,
        "focus_count": len(candidates),
        "plate_count": len(advise.get("plates") or []),
    }
