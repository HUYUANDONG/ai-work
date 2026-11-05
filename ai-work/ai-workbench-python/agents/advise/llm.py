"""
投放建议 LLM：定槽后用瘦字段写「思考过程 + 投放建议」。

对话同步确认与任务内 include_advise=true 共用；失败回落模板。
优先 SSE token 流，便于 Java 转推前端。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from clients.llm_client import LlmClient
from harness.memory.long_term import prompt_with_memory
from harness.memory.slim import slim_candidates_for_llm

logger = logging.getLogger(__name__)


def _fallback_text(advise_context: dict[str, Any]) -> str:
    """延迟导入 narrative，避免与 supervisor/explosion 循环依赖。"""
    from agents.explosion.narrative import placement_block_fallback

    return placement_block_fallback(advise_context)

DeltaFn = Callable[[str], Awaitable[None]]

ADVISE_SYSTEM = """你是店内爆品投放顾问。根据给定的焦点商品与日板块流量，输出简短中文。
必须包含两段：
1）思考过程：点名商品并引用销售额/订单/UV/转化率（rate_per）等已给数字；
2）投放建议：结合板块名称与 UV/销售额，说明优先试投哪里（未验证商品是否已挂该板块，需说明）。
硬性约束：禁止编造未出现的数字或板块；缺字段写「未知」；不要输出 Markdown 代码围栏；全文控制在 400 字内。"""


def _slim_plates(plates: list[dict[str, Any]], *, limit: int = 8) -> list[dict[str, Any]]:
    """板块再瘦一层给 LLM。"""
    out: list[dict[str, Any]] = []
    for p in plates[:limit]:
        row = {
            k: p.get(k)
            for k in (
                "stat_field_name",
                "stat_field",
                "self_uv",
                "self_pv",
                "order_sales",
                "order_numbers",
            )
            if p.get(k) is not None
        }
        if row:
            out.append(row)
    return out


def _slim_store(store: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(store, dict) or not store:
        return {}
    return {
        k: store.get(k)
        for k in (
            "total_sales",
            "order_numbers",
            "hpage_uv",
            "spu_uv",
            "conversion_rate",
            "stat_day",
        )
        if store.get(k) is not None
    }


async def write_placement_advise(
    *,
    candidates: list[dict[str, Any]],
    advise_context: dict[str, Any],
    llm: LlmClient | None,
    goal_mode: str = "GMV",
    on_delta: DeltaFn | None = None,
    memory_preface: str = "",
) -> dict[str, Any]:
    """
    用 LLM（或模板）生成投放建议正文。

    Args:
        candidates: 会签后候选（优先 in_focus_slot）。
        advise_context: ``/features/advise`` 响应。
        llm: 可选 LLM 客户端。
        goal_mode: 目标模式。
        on_delta: 流式增量回调（推 SSE）。

    Returns:
        dict: text / source（llm|llm_stream|template|template_fallback）。
    """
    focus = [c for c in candidates if c.get("in_focus_slot")]
    pool = focus or list(candidates)[:5]
    slim = slim_candidates_for_llm(pool, max_items=max(3, min(8, len(pool))))
    plates = _slim_plates(list(advise_context.get("plates") or []))
    store = _slim_store(advise_context.get("store") if isinstance(advise_context.get("store"), dict) else {})
    payload = {
        "goal_mode": goal_mode,
        "focus": slim,
        "plates": plates,
        "store": store or None,
        "advise_source": advise_context.get("source"),
    }
    user = json.dumps({k: v for k, v in payload.items() if v is not None}, ensure_ascii=False)

    if llm is not None and getattr(llm, "enabled", False):
        try:
            chunks: list[str] = []
            async for delta in llm.chat_stream(
                system=prompt_with_memory(ADVISE_SYSTEM, memory_preface),
                user=user,
                json_mode=False,
            ):
                chunks.append(delta)
                if on_delta is not None and delta:
                    await on_delta(delta)
            text = "".join(chunks).strip()
            if text:
                return {"text": text, "source": "llm_stream"}
            # 空流再退非流式
            text = await llm.chat(
                system=prompt_with_memory(ADVISE_SYSTEM, memory_preface),
                user=user,
                json_mode=False,
            )
            text = (text or "").strip()
            if text:
                if on_delta is not None:
                    await on_delta(text)
                return {"text": text, "source": "llm"}
        except Exception:
            logger.exception("placement advise LLM failed")
            return {
                "text": _fallback_text(advise_context),
                "source": "template_fallback",
            }

    return {
        "text": _fallback_text(advise_context),
        "source": "template",
    }
