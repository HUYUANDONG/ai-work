"""质检解释官（叶子 BaseAgent）：对问题 SKU 写 ai_comment。"""

from __future__ import annotations

import json
from typing import Any

from agents.base import BaseAgent
from clients.llm_client import LlmClient
from schemas.agent import AgentResult

EXPLAIN_SYSTEM = """你是质检顾问。对每个有问题的 SKU，根据 issues 写一句 ai_comment（中文，可执行）。
输出 JSON 对象：{"comments":{"SKU-001":"..."}, "summary":"整份报告一句话总结"}。
禁止改分数；禁止编造 rule_id。不要用 Markdown 围栏。"""


def template_comments(rows: list[dict[str, Any]]) -> tuple[dict[str, str], str]:
    """模板兜底评论。"""
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


class QualityExplainAgent(BaseAgent):
    """质检 LLM/模板解释叶子。"""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        timeout: float | None = 40.0,
    ) -> None:
        super().__init__(name="quality_explain", timeout=timeout)
        self.llm = llm

    async def _execute(self, **kwargs: Any) -> AgentResult:
        rows: list[dict[str, Any]] = list(kwargs.get("rows") or [])
        llm: LlmClient | None = kwargs.get("llm") or self.llm
        comments, summary = template_comments(rows)
        source = "template"

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
                raw = (raw or "").strip()
                if raw.startswith("```"):
                    raw = raw.strip("`")
                    if raw.startswith("json"):
                        raw = raw[4:].strip()
                parsed = json.loads(raw)
                if isinstance(parsed.get("comments"), dict):
                    comments.update({str(k): str(v) for k, v in parsed["comments"].items()})
                if parsed.get("summary"):
                    summary = str(parsed["summary"])
                source = "llm"
            except Exception as exc:
                source = "template_fallback"
                return AgentResult(
                    agent_name=self.name,
                    success=True,
                    confidence=0.55,
                    error=str(exc) or type(exc).__name__,
                    data={"comments": comments, "summary": summary, "rows": rows},
                    source=source,
                )

        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.85 if source == "llm" else 0.7,
            data={"comments": comments, "summary": summary, "rows": rows},
            source=source,
        )

    def _fallback(
        self,
        latency_ms: float,
        exc: BaseException,
        **kwargs: Any,
    ) -> AgentResult:
        rows: list[dict[str, Any]] = list(kwargs.get("rows") or [])
        comments, summary = template_comments(rows)
        return AgentResult(
            agent_name=self.name,
            success=True,
            latency_ms=latency_ms,
            error=str(exc) or type(exc).__name__,
            confidence=0.5,
            data={"comments": comments, "summary": summary, "rows": rows},
            source="template_fallback",
        )
