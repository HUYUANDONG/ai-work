"""
榜单解读叶子：规则排完序后，用 LLM 解释焦点款（禁止改分、禁止重排）。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from agents.base import BaseAgent
from clients.llm_client import LlmClient
from harness.memory.slim import slim_candidates_for_llm
from schemas.agent import AgentResult

logger = logging.getLogger(__name__)

ANALYZE_SYSTEM = """你是店内爆品分析顾问。下面候选已由代码规则打分并排序，名次与 explosion_score 为权威。
任务：用中文简短解读焦点商品（进槽的优先），帮助运营理解「为什么推这几个」。
硬性约束：
1. 禁止改名次、禁止改 explosion_score、禁止按你的偏好重排
2. 只能引用给定字段中的数字；缺字段写「未知」
3. 点出风险标签（quality_risk_level / 缺货等）与可执行注意点
4. 全文 ≤250 字；不要 Markdown 代码围栏；不要输出 JSON
结构建议：先总述 1 句，再按名次各 1 句要点。
"""


def _template_analysis(
    candidates: list[dict[str, Any]],
    *,
    goal_mode: str,
) -> str:
    """无 LLM 时的解读兜底。"""
    focus = [c for c in candidates if c.get("in_focus_slot")] or candidates[:5]
    if not focus:
        return "本轮没有可解读的焦点商品。"
    lines = [
        f"按代码评分选出 {len(focus)} 个本周重点（目标 {goal_mode}），名次以规则分为准："
    ]
    for c in focus[:5]:
        lines.append(
            f"- #{c.get('rank')} {c.get('sku_id')} {c.get('title') or ''}："
            f"分={c.get('explosion_score')}，风险={c.get('quality_risk_level') or 'NONE'}。"
        )
    lines.append("以上为规则榜解读；如需投放建议可继续确认。")
    return "\n".join(lines)


class AnalyzeAgent(BaseAgent):
    """规则榜后的 LLM 解读叶子。"""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        timeout: float | None = 45.0,
    ) -> None:
        super().__init__(name="analyze", timeout=timeout)
        self.llm = llm

    async def _execute(self, **kwargs: Any) -> AgentResult:
        candidates = list(kwargs.get("candidates") or [])
        goal_mode = str(kwargs.get("goal_mode") or "GMV")
        inventory_summary = str(kwargs.get("inventory_summary") or "").strip()
        llm: LlmClient | None = kwargs.get("llm") or self.llm

        slim = slim_candidates_for_llm(candidates, max_items=max(3, min(8, len(candidates))))
        text = ""
        source = "template"

        if llm is not None and llm.enabled and slim:
            try:
                user = json.dumps(
                    {
                        "goal_mode": goal_mode,
                        "note": "candidates already ranked by scoring_rules; do not reorder",
                        "candidates": slim,
                        "inventory_summary": inventory_summary or None,
                    },
                    ensure_ascii=False,
                )
                raw = await llm.chat(
                    system=ANALYZE_SYSTEM,
                    user=user,
                    json_mode=False,
                )
                text = (raw or "").strip()
                if text:
                    source = "llm"
            except Exception:
                logger.exception("analyze llm failed")
                text = ""
                source = "template_fallback"

        if not text:
            text = _template_analysis(candidates, goal_mode=goal_mode)
            if source == "llm":
                source = "template"

        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.85 if source == "llm" else 0.65,
            data={
                "text": text,
                # 原样带回，明确未改序
                "candidates": candidates,
            },
            source=source,
        )
