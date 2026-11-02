"""
确定性 Session Facts：从报告抽运营接口字段，禁止模型编造数字。

字段以 docs/llm-field-glossary.md 商品销量接口为准。
"""

from __future__ import annotations

from typing import Any

from harness.memory.fields import ops_goods_view


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
            row = ops_goods_view(it)
            if row:
                rows.append(row)
        blocks.append(
            {
                "task_id": r.get("task_id"),
                "task_type": r.get("task_type"),
                "snapshot_date": header.get("snapshot_date"),
                "summary": (header.get("summary") or "")[:300],
                "items": rows,
                "archive_ref": f"report:{r.get('task_id')}",
            }
        )
    return {
        "source": "code_extracted",
        "note": (
            "数字仅来自运营接口商品销数字段（goodsId/orderSales/orderNumbers/"
            "goodsPv/goodsUv/ratePer 等）。缺字段视为未知，禁止当 0；"
            "goodsPv/goodsUv 为昨日流量，与实时 orderSales/orderNumbers 不是同一窗口。"
        ),
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
            f"- {b.get('task_type')} {b.get('archive_ref')} snapshot={b.get('snapshot_date')}"
        )
        if b.get("summary"):
            lines.append(f"  summary: {b['summary'][:160]}")
        for it in b.get("items") or []:
            goods_id = it.get("goodsId") or "?"
            name = it.get("goodsName") or ""
            parts = [str(goods_id)]
            if name:
                parts.append(str(name))
            for key in (
                "orderSales",
                "orderNumbers",
                "orderPays",
                "goodsPv",
                "goodsUv",
                "ratePer",
                "statDay",
                "gbName",
            ):
                if key in it and it[key] is not None:
                    parts.append(f"{key}={it[key]}")
            lines.append("  · " + " ".join(parts))
    text = "\n".join(lines)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…(facts truncated)"
    return text
