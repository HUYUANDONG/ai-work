"""
爆品叶子：规则榜之后一次 LLM —— 解读 + 有限重排进槽（不改 explosion_score）。

不再使用 Signal/Risk/Strategy 三会签。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.base import BaseAgent
from clients.llm_client import LlmClient
from harness.memory.long_term import prompt_with_memory
from harness.memory.slim import slim_candidates_for_llm
from schemas.agent import AgentResult

logger = logging.getLogger(__name__)

EXPLOSION_SYSTEM = """你是店内爆品顾问。候选已由代码规则打分并排序，explosion_score 与相对强弱为权威。
任务：
1) 写一段中文解读（≤200字），说明为何推这些焦点款、风险注意点
2) 在候选 sku_id 内挑选本周焦点（有限重排进槽），可微调进槽名单，但禁止改分数、禁止引入榜外 SKU

必须输出 JSON（不要其它文字）：
{
  "analysis": "解读正文",
  "focus_sku_ids": ["SKU-1", "SKU-2"],
  "actions": [{"sku_id":"SKU-1","action_bucket":"PUSH|FIX_THEN_PUSH|WATCH","reason":"一句"}]
}
约束：
- focus_sku_ids 长度 ≤ focus_slots，且必须是候选里已有的 sku_id
- quality_risk_level=HIGH 不得标 PUSH，用 FIX_THEN_PUSH 或 WATCH
- 缺字段写「未知」；禁止编造数字
"""


def _default_bucket(c: dict[str, Any]) -> str:
    risk = str(c.get("quality_risk_level") or "NONE")
    score = float(c.get("explosion_score") or 0)
    if risk == "HIGH":
        return "FIX_THEN_PUSH" if score >= 45 else "WATCH"
    if risk == "MID":
        return "FIX_THEN_PUSH" if score >= 55 else "WATCH"
    if score >= 70:
        return "PUSH"
    if score >= 50:
        return "WATCH"
    return "WATCH"


def apply_focus_and_actions(
    candidates: list[dict[str, Any]],
    *,
    focus_slots: int,
    focus_sku_ids: list[str] | None = None,
    actions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    落实进槽与动作桶；不改 explosion_score。

    Args:
        candidates: 规则排序后的候选（原地更新）。
        focus_slots: 槽位数。
        focus_sku_ids: LLM 选定的进槽顺序；非法 id 忽略。
        actions: 可选动作桶覆盖。

    Returns:
        list[dict]: 同一 candidates 引用。
    """
    slots = max(1, min(int(focus_slots or 5), 10))
    by_sku = {str(c.get("sku_id")): c for c in candidates if c.get("sku_id") is not None}
    action_by = {
        str(a.get("sku_id")): a
        for a in (actions or [])
        if isinstance(a, dict) and a.get("sku_id")
    }

    for c in candidates:
        sku = str(c.get("sku_id"))
        act = action_by.get(sku) or {}
        bucket = str(act.get("action_bucket") or c.get("action_bucket") or _default_bucket(c))
        risk = str(c.get("quality_risk_level") or "NONE")
        score = float(c.get("explosion_score") or 0)
        if bucket == "PUSH" and risk in {"HIGH", "MID"}:
            bucket = "FIX_THEN_PUSH"
        if bucket == "PUSH" and score < 70:
            bucket = "WATCH"
        if bucket == "FIX_THEN_PUSH" and score < 50 and risk != "HIGH":
            bucket = "WATCH"
        c["action_bucket"] = bucket
        c["risk_veto"] = risk == "HIGH"
        if act.get("reason"):
            c["ai_reason"] = str(act.get("reason"))
        c["in_focus_slot"] = False

    ordered_focus: list[str] = []
    for sid in focus_sku_ids or []:
        sid = str(sid)
        if sid in by_sku and sid not in ordered_focus:
            ordered_focus.append(sid)
    used = 0
    for sid in ordered_focus:
        c = by_sku[sid]
        if c["action_bucket"] not in {"PUSH", "FIX_THEN_PUSH"}:
            continue
        if used < slots:
            c["in_focus_slot"] = True
            used += 1
    if used < slots:
        for c in sorted(
            candidates,
            key=lambda x: float(x.get("explosion_score") or 0),
            reverse=True,
        ):
            if c.get("in_focus_slot"):
                continue
            if c["action_bucket"] in {"PUSH", "FIX_THEN_PUSH"} and used < slots:
                c["in_focus_slot"] = True
                used += 1

    # 展示序：进槽优先，再按规则分
    candidates.sort(
        key=lambda x: (
            0 if x.get("in_focus_slot") else 1,
            -float(x.get("explosion_score") or 0),
        )
    )
    for i, c in enumerate(candidates, start=1):
        c["rank"] = i
        c["mode_rank"] = i
    return candidates


def _template_analysis(candidates: list[dict[str, Any]], *, goal_mode: str) -> str:
    focus = [c for c in candidates if c.get("in_focus_slot")] or candidates[:5]
    if not focus:
        return "本轮没有可解读的焦点商品。"
    lines = [f"按代码评分选出 {len(focus)} 个本周重点（目标 {goal_mode}）："]
    for c in focus[:5]:
        lines.append(
            f"- #{c.get('rank')} {c.get('sku_id')} {c.get('title') or ''} "
            f"分={c.get('explosion_score')} 动作={c.get('action_bucket')} "
            f"风险={c.get('quality_risk_level') or 'NONE'}"
        )
    return "\n".join(lines)


def _parse_llm(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class ExplosionAgent(BaseAgent):
    """爆品解读 + 有限进槽重排。"""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        timeout: float | None = 60.0,
    ) -> None:
        super().__init__(name="explosion", timeout=timeout)
        self.llm = llm

    async def _execute(self, **kwargs: Any) -> AgentResult:
        candidates = [dict(c) for c in (kwargs.get("candidates") or [])]
        focus_slots = int(kwargs.get("focus_slots") or 5)
        goal_mode = str(kwargs.get("goal_mode") or "GMV")
        inventory_summary = str(kwargs.get("inventory_summary") or "").strip()
        llm: LlmClient | None = kwargs.get("llm") or self.llm
        system = prompt_with_memory(EXPLOSION_SYSTEM, str(kwargs.get("memory_preface") or ""))

        # 默认先按规则分进槽，LLM 可再微调
        apply_focus_and_actions(candidates, focus_slots=focus_slots)

        analysis = ""
        source = "template"
        if llm is not None and llm.enabled and candidates:
            try:
                slim = slim_candidates_for_llm(
                    candidates, max_items=max(3, min(12, len(candidates)))
                )
                user = json.dumps(
                    {
                        "goal_mode": goal_mode,
                        "focus_slots": focus_slots,
                        "inventory_summary": inventory_summary or None,
                        "candidates": slim,
                        "rule": "do not change explosion_score; focus only within candidates",
                    },
                    ensure_ascii=False,
                )
                raw = await llm.chat(
                    system=system, user=user, json_mode=True
                )
                parsed = _parse_llm(raw or "")
                analysis = str(parsed.get("analysis") or "").strip()
                focus_ids = [
                    str(x) for x in (parsed.get("focus_sku_ids") or []) if str(x)
                ]
                actions = list(parsed.get("actions") or [])
                apply_focus_and_actions(
                    candidates,
                    focus_slots=focus_slots,
                    focus_sku_ids=focus_ids or None,
                    actions=actions or None,
                )
                if analysis:
                    source = "llm"
            except Exception:
                logger.exception("explosion agent llm failed")
                source = "template_fallback"
                apply_focus_and_actions(candidates, focus_slots=focus_slots)

        if not analysis:
            analysis = _template_analysis(candidates, goal_mode=goal_mode)

        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.85 if source == "llm" else 0.65,
            data={
                "text": analysis,
                "candidates": candidates,
                "focus_slots": focus_slots,
            },
            source=source,
        )
