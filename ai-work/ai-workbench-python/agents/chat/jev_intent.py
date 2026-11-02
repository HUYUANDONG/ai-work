"""
用 TypeSafe 官方 SDK（Jev）做对话意图 Choice 路由。

主流包名：``typesafe-sdk``；环境变量：``TYPESAFE_API_KEY``；模型默认 ``jev-latest``。
Jev 只返回有限选项 + confidence；默认参数与是否建任务仍由代码决定。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

INTENT_CRITERIA: dict[str, str] = {
    "EXPLOSION": (
        "User wants hit-product / explosion screening, growth ranking, "
        "weekly focus list, GMV/profit/clearance campaign from store metrics."
    ),
    "QUALITY": (
        "User wants a formal quality inspection report on SKUs: loss-making, "
        "stockout, returns, reviews, or full quality checklist — usually says 质检."
    ),
    "SKU_DEEP": (
        "User wants a quick deep-dive analysis or advice on one (or few) named SKUs "
        "right now: 分析/看看/建议 this product — not a full store screening task."
    ),
    "FOLLOWUP": (
        "User asks about a previous analysis result in this chat: why a rank, "
        "what a score means, clarify a suggestion — not a new full run."
    ),
    "META": ("User asks what the assistant can do, how to use it, or metric口径 / policy."),
    "OUT_OF_SCOPE": (
        "Request is unrelated: coding, crawlers, listing/price changes, external "
        "competitors scraping, general chat, or actions this workbench cannot do."
    ),
    "CLARIFY": (
        "Intent is ambiguous between explosion, quality, and sku deep-dive, or missing "
        "critical info so we must ask one clarifying question before creating a task."
    ),
}


@dataclass(frozen=True)
class IntentDecision:
    """意图判定结果。"""

    intent: str
    confidence: float
    source: str
    probabilities: dict[str, float] | None = None
    error: str | None = None


def _run_jev_sync(*, state: str, model: str) -> IntentDecision:
    """
    同步调用 Jev Choice。

    Args:
        state: 送给 Jev 的精简状态文本。
        model: 模型名，通常 jev-latest。

    Returns:
        IntentDecision: 选项与置信度。

    Raises:
        Exception: SDK 或网络错误向上抛，由调用方决定降级。
    """
    from typesafe_sdk import Choice, TypeSafeClient

    with TypeSafeClient(model=model) as client:
        response = client.system_one(
            state=state,
            questions={
                "intent": Choice(
                    instructions=(
                        "Primary intent for an ecommerce ops workbench that only "
                        "does store explosion campaign lists and product quality checks."
                    ),
                    criteria=INTENT_CRITERIA,
                ),
            },
        )

    answer = response.choices["intent"]
    choice = str(answer.choice)
    confidence = float(getattr(answer, "confidence", 0.0) or 0.0)
    probs_raw = getattr(answer, "probabilities", None) or {}
    probabilities = {str(k): float(v) for k, v in dict(probs_raw).items()}
    return IntentDecision(
        intent=choice,
        confidence=confidence,
        source="jev",
        probabilities=probabilities,
    )


async def classify_with_jev(
    message: str,
    *,
    model: str = "jev-latest",
    min_confidence: float = 0.75,
) -> IntentDecision:
    """
    异步包装 Jev 意图分类；低置信度改为 CLARIFY。

    Args:
        message: 用户原文。
        model: Jev 模型。
        min_confidence: 低于此值则 intent=CLARIFY。

    Returns:
        IntentDecision: 最终用于路由的意图。
    """
    state = (
        "Workbench capabilities: explosion campaign from SKU window metrics; "
        "quality inspection. Not for coding, listing, or external crawl.\n"
        f"User message:\n{(message or '').strip()}"
    )
    decision = await asyncio.to_thread(_run_jev_sync, state=state, model=model)
    if decision.confidence < min_confidence:
        return IntentDecision(
            intent="CLARIFY",
            confidence=decision.confidence,
            source="jev_low_confidence",
            probabilities=decision.probabilities,
            error=None,
        )
    if decision.intent not in INTENT_CRITERIA:
        return IntentDecision(
            intent="CLARIFY",
            confidence=decision.confidence,
            source="jev_invalid_choice",
            probabilities=decision.probabilities,
            error=f"unexpected choice: {decision.intent}",
        )
    return decision


def classify_with_rules_fallback(message: str) -> IntentDecision:
    """
    无 Key / Jev 失败时的规则降级（仅本地兜底，正式环境应开 Jev）。

    Args:
        message: 用户原文。

    Returns:
        IntentDecision: source=rules_fallback。
    """
    from agents.chat.intent import classify_message_rules

    intent = classify_message_rules(message)
    return IntentDecision(
        intent=intent,
        confidence=0.0,
        source="rules_fallback",
        probabilities=None,
    )


async def resolve_intent(
    message: str,
    *,
    api_key: str,
    enabled: bool,
    model: str,
    min_confidence: float,
    allow_rules_fallback: bool,
) -> IntentDecision:
    """
    统一入口：优先 Jev，否则规则降级或强制澄清。

    Args:
        message: 用户原文。
        api_key: TYPESAFE_API_KEY。
        enabled: 是否启用 Jev。
        model: Jev 模型名。
        min_confidence: 置信度门槛。
        allow_rules_fallback: 无 Key 或调用失败时是否用规则。

    Returns:
        IntentDecision: 路由意图。
    """
    if not enabled or not (api_key or "").strip():
        if allow_rules_fallback:
            return classify_with_rules_fallback(message)
        return IntentDecision(
            intent="CLARIFY",
            confidence=0.0,
            source="jev_disabled",
            error="TYPESAFE_API_KEY missing or Jev disabled",
        )

    try:
        return await classify_with_jev(
            message,
            model=model,
            min_confidence=min_confidence,
        )
    except Exception as exc:  # noqa: BLE001 — 降级路径需吞掉并记录
        logger.exception("Jev intent classification failed: %s", exc)
        if allow_rules_fallback:
            fb = classify_with_rules_fallback(message)
            return IntentDecision(
                intent=fb.intent,
                confidence=0.0,
                source="rules_fallback_after_error",
                error=str(exc),
            )
        return IntentDecision(
            intent="CLARIFY",
            confidence=0.0,
            source="jev_error",
            error=str(exc),
        )
