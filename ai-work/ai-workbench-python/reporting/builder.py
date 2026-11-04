"""组装爆品可下载报表。

对话回复不依赖 HTML 正文；LLM 出 HTML 在系统代理下超时取消会卡住 Worker，
因此固定用 Chart.js 模板，保证任务能 complete。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from clients.llm_client import LlmClient
from reporting.fallback_html import render_fallback_html
from reporting.html_report import write_html_file

logger = logging.getLogger(__name__)


def _locked_payload(
    *,
    task_id: str,
    ranked_result: dict[str, Any],
    task_input: dict[str, Any],
    snapshot_date: str | None,
) -> dict[str, Any]:
    """只把展示所需字段交给模型，避免塞过大 breakdown。"""
    candidates = []
    for c in ranked_result.get("candidates") or []:
        candidates.append(
            {
                "rank": c.get("rank"),
                "sku_id": c.get("sku_id"),
                "title": c.get("title"),
                "explosion_score": c.get("explosion_score"),
                "quality_risk_level": c.get("quality_risk_level"),
                "quality_rule_ids": c.get("quality_rule_ids"),
                "action_bucket": c.get("action_bucket"),
                "in_focus_slot": c.get("in_focus_slot"),
                "primary_action": c.get("primary_action"),
                "feature_excerpt": c.get("feature_excerpt"),
                "metrics": c.get("metrics"),
            }
        )
    return {
        "task_id": task_id,
        "snapshot_date": snapshot_date,
        "scoring_version": ranked_result.get("scoring_version"),
        "pool_size": ranked_result.get("pool_size"),
        "top_n": ranked_result.get("top_n"),
        "goal_mode": task_input.get("goal_mode"),
        "focus_slots": task_input.get("focus_slots"),
        "candidates": candidates,
        "required_charts": [
            {
                "id": "score_bar",
                "type": "bar",
                "title": "各 SKU 爆品分",
                "x": "sku_id",
                "y": "explosion_score",
            },
            {
                "id": "risk_donut",
                "type": "doughnut",
                "title": "质检风险分布",
                "field": "quality_risk_level",
            },
        ],
    }


def build_download_contract(task_id: str) -> dict[str, Any]:
    """
    给前端的下载约定（展示下载按钮用）。

    Args:
        task_id: 任务 ID。

    Returns:
        dict: available / url / method / filename / content_type / hint。
    """
    filename = f"explosion-report-{task_id}.html"
    return {
        "available": True,
        "url": f"/internal/dev/reports/{task_id}",
        "method": "GET",
        "filename": filename,
        "content_type": "text/html; charset=utf-8",
        "hint": "报表可供用户下载：展示下载按钮，点击后 GET 该 url（建议带鉴权头）。",
    }


async def build_explosion_report(
    *,
    task_id: str,
    ranked_result: dict[str, Any],
    task_input: dict[str, Any],
    snapshot_date: str | None,
    llm: LlmClient | None,
    output_dir: Path,
) -> dict[str, Any]:
    """
    生成 HTML 报表文件，并返回前端下载描述。

    Args:
        task_id: 任务 ID。
        ranked_result: 打分挂标结果。
        task_input: 任务输入。
        snapshot_date: 快照日。
        llm: 可选 LLM。
        output_dir: 输出目录。

    Returns:
        dict: report_path / download / html_source 等。
    """
    locked = _locked_payload(
        task_id=task_id,
        ranked_result=ranked_result,
        task_input=task_input,
        snapshot_date=snapshot_date,
    )

    html = render_fallback_html(locked)
    html_source = "template"
    if llm is not None and llm.enabled:
        logger.info("skip LLM HTML for task_id=%s; using Chart.js template", task_id)

    out_path = output_dir / f"{task_id}.html"
    write_html_file(out_path, html)
    download = build_download_contract(task_id)

    return {
        "report_path": str(out_path.resolve()),
        "download_path": download["url"],
        "download": download,
        "html_source": html_source,
        "analysis_source": html_source,
        "required_charts": locked["required_charts"],
    }

