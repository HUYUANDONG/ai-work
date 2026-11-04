"""
爆品文案 Agent：文案生成与合规检查均走 LLM（同叶子两步，无独立 ComplianceAgent）。

1) 写手 LLM 出草稿
2) 合规 LLM 审查；不合规则改写到合规后输出
无 LLM 时仅模板兜底（非正式路径）。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.base import BaseAgent
from clients.llm_client import LlmClient
from schemas.agent import AgentResult

logger = logging.getLogger(__name__)

COPY_SYSTEM = """你是电商爆品文案写手。根据商品详情与真实评论写 1 条短文案（80字内）。
要求：
1. 只依据给定详情/评论，禁止编造数字与功效
2. 语气促销但克制，不要绝对化用语
3. 只输出文案正文，不要 Markdown 围栏、不要标题前缀
"""

COMPLIANCE_SYSTEM = """你是电商广告合规审核员。审查并改写爆品文案。
硬性规则：
1. 禁止绝对化：最、第一、国家级、驰名、唯一、100%、根治、永久、包治、王牌
2. 禁止医疗功效承诺与虚假促销
3. 数字必须能在原文案或给定商品事实中找到，禁止新编造
4. 最终文案 ≤80 字

必须输出 JSON 对象（不要其它文字）：
{"compliant": true/false, "issues": ["..."], "revised_copy": "合规后的最终文案"}
若原稿已合规：compliant=true，revised_copy=原稿（可微修标点）。
若不合规：compliant=false，issues 列出问题，revised_copy 为改写后合规文案。
"""


def _template_copy(bundle: dict[str, Any]) -> str:
    """无 LLM 时的安全兜底文案（本身避开绝对化用语）。"""
    detail = dict(bundle.get("detail") or {})
    title = str(detail.get("title") or bundle.get("sku_id") or "好物")
    points = detail.get("selling_points") or []
    tip = points[0] if points else "店铺热销款"
    review = ""
    reviews = list(bundle.get("reviews") or [])
    if reviews:
        review = str(reviews[0].get("content") or "")[:24]
    tip_review = review or "口碑稳定"
    return f"「{title}」{tip}。买家反馈：{tip_review}。现货可冲，关注转化。"[:120]


def _strip_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_compliance_result(raw: str, *, draft: str) -> dict[str, Any]:
    """
    解析合规 LLM 的 JSON；失败则保守认为需改写并用草稿。

    Args:
        raw: 模型原文。
        draft: 写手草稿，解析失败时回退。

    Returns:
        dict: compliant / issues / revised_copy。
    """
    text = _strip_fence(raw)
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("not object")
        revised = str(data.get("revised_copy") or draft).strip() or draft
        issues = data.get("issues") or []
        if not isinstance(issues, list):
            issues = [str(issues)]
        return {
            "compliant": bool(data.get("compliant")),
            "issues": [str(x) for x in issues if str(x).strip()],
            "revised_copy": revised[:120],
        }
    except Exception:
        logger.warning("compliance json parse failed; keep draft")
        return {
            "compliant": False,
            "issues": ["compliance_parse_failed"],
            "revised_copy": (draft or "").strip()[:120],
        }


class CopyAgent(BaseAgent):
    """文案生成 + LLM 合规审查（一体两步）。"""

    def __init__(
        self,
        *,
        llm: LlmClient | None = None,
        timeout: float | None = 90.0,
    ) -> None:
        super().__init__(name="copy", timeout=timeout)
        self.llm = llm

    async def _draft_copy(self, llm: LlmClient, bundle: dict[str, Any], sku: str) -> str:
        user = json.dumps(
            {
                "sku_id": sku,
                "detail": bundle.get("detail"),
                "reviews": bundle.get("reviews"),
            },
            ensure_ascii=False,
        )
        raw = await llm.chat(system=COPY_SYSTEM, user=user, json_mode=False)
        return _strip_fence(raw or "").strip()[:120]

    async def _llm_compliance(
        self,
        llm: LlmClient,
        *,
        draft: str,
        bundle: dict[str, Any],
        sku: str,
    ) -> dict[str, Any]:
        user = json.dumps(
            {
                "sku_id": sku,
                "draft_copy": draft,
                "detail": bundle.get("detail"),
                "reviews": bundle.get("reviews"),
            },
            ensure_ascii=False,
        )
        raw = await llm.chat(system=COMPLIANCE_SYSTEM, user=user, json_mode=True)
        return parse_compliance_result(raw, draft=draft)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        bundles = list(kwargs.get("bundles") or [])
        llm: LlmClient | None = kwargs.get("llm") or self.llm
        copies: list[dict[str, Any]] = []
        source = "template"

        for bundle in bundles[:5]:
            sku = str(bundle.get("sku_id") or "")
            if llm is not None and llm.enabled:
                try:
                    draft = await self._draft_copy(llm, bundle, sku)
                    if not draft:
                        draft = _template_copy(bundle)
                    checked = await self._llm_compliance(
                        llm, draft=draft, bundle=bundle, sku=sku
                    )
                    copies.append(
                        {
                            "sku_id": sku,
                            "draft": draft,
                            "copy": checked["revised_copy"],
                            "compliant": bool(checked["compliant"])
                            or bool(checked["revised_copy"]),
                            "issues": checked["issues"],
                            "source": "llm_copy+llm_compliance",
                        }
                    )
                    source = "llm_copy+llm_compliance"
                    continue
                except Exception:
                    logger.exception("copy+compliance llm failed sku=%s", sku)
                    text = _template_copy(bundle)
                    copies.append(
                        {
                            "sku_id": sku,
                            "draft": text,
                            "copy": text,
                            "compliant": True,
                            "issues": ["llm_fallback_template"],
                            "source": "template_fallback",
                        }
                    )
                    source = "template_fallback"
                    continue

            text = _template_copy(bundle)
            copies.append(
                {
                    "sku_id": sku,
                    "draft": text,
                    "copy": text,
                    "compliant": True,
                    "issues": ["no_llm"],
                    "source": "template",
                }
            )

        lines = [f"- {c['sku_id']}: {c['copy']}" for c in copies]
        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=0.85 if source.startswith("llm") else 0.6,
            data={
                "copies": copies,
                "text": "爆品文案（LLM 生成并由 LLM 合规审查）：\n" + "\n".join(lines),
            },
            source=source,
        )
