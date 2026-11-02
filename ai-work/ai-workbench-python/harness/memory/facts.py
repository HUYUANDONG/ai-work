"""
确定性 Session Facts：从报告/候选轨迹抽取，禁止模型编造数字。

灵感来自业界「工具轨迹 → 事实块」做法（ADM 同类），实现为本仓适配版。
"""

from __future__ import annotations

from typing import Any


def extract_report_facts(reports: list[dict[str, Any]], *, max_items: int = 8) -> dict[str, Any]:
    """
    从会话报告抽取可引用事实。

    Args:
        reports: get_conversation_reports 的 reports 列表。
        max_items: 每份报告最多摘多少行。

    Returns:
        dict: 结构化 facts，可注入 prompt。
    """
    blocks: list[dict[str, Any]] = []
    for r in reports[:3]:
        header = r.get("header") or {}
        items = list(r.get("items") or [])[:max_items]
        rows = []
        for it in items:
            row: dict[str, Any] = {"sku_id": it.get("sku_id")}
            if "explosion_score" in it:
                row["explosion_score"] = it.get("explosion_score")
            if "action_bucket" in it:
                row["action_bucket"] = it.get("action_bucket")
            if "quality_risk_level" in it:
                row["quality_risk_level"] = it.get("quality_risk_level")
            if "risk_level" in it:
                row["risk_level"] = it.get("risk_level")
            if "in_focus_slot" in it:
                row["in_focus_slot"] = it.get("in_focus_slot")
            rows.append(row)
        blocks.append(
            {
                "task_id": r.get("task_id"),
                "task_type": r.get("task_type"),
                "scoring_version": header.get("scoring_version"),
                "snapshot_date": header.get("snapshot_date"),
                "summary": (header.get("summary") or "")[:300],
                "items": rows,
                "archive_ref": f"report:{r.get('task_id')}",
            }
        )
    return {
        "source": "code_extracted",
        "note": "数字与桶位仅来自已落库报告，模型不得改写。",
        "reports": blocks,
    }


def render_facts_block(facts: dict[str, Any], *, max_chars: int = 1200) -> str:
    """
    渲染为可注入的短文本块。

    Args:
        facts: extract_report_facts 结果。
        max_chars: 硬截断字符数。

    Returns:
        str: `[Session Facts]` 文本。
    """
    lines = ["[Session Facts]", facts.get("note") or ""]
    for b in facts.get("reports") or []:
        lines.append(
            f"- {b.get('task_type')} {b.get('archive_ref')} "
            f"snapshot={b.get('snapshot_date')} scoring={b.get('scoring_version')}"
        )
        if b.get("summary"):
            lines.append(f"  summary: {b['summary'][:160]}")
        for it in b.get("items") or []:
            parts = [str(it.get("sku_id"))]
            if it.get("explosion_score") is not None:
                parts.append(f"score={it['explosion_score']}")
            if it.get("action_bucket"):
                parts.append(f"bucket={it['action_bucket']}")
            risk = it.get("quality_risk_level") or it.get("risk_level")
            if risk:
                parts.append(f"risk={risk}")
            lines.append("  · " + " ".join(parts))
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…(facts truncated)"
    return text
