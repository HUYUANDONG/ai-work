"""单品深挖：查 Java 特征 → 代码挂标摘要 → LLM/模板建议。"""

from __future__ import annotations

import json
import logging
from typing import Any

from clients.llm_client import LlmClient
from harness.runtime import AppRuntime
from scoring.explosion import score_sku
from scoring.quality import check_sku
from scoring.store_stats import build_store_stats
from tools.features import get_product_features, query_features

logger = logging.getLogger(__name__)

SYSTEM = """你是店内商品运营顾问。根据锁定的指标 JSON 给出简短中文建议。
硬性要求：不得编造数字；引用 JSON 中的字段；指出主要风险规则；给出 2～4 条可执行建议。
若高爆品分且高风险，必须写「先修再冲」。不要输出 Markdown 代码围栏。"""


def _template_advice(locked: dict[str, Any]) -> str:
    item = locked.get("item") or {}
    q = locked.get("quality") or {}
    exp = locked.get("explosion") or {}
    sku = item.get("sku_id")
    title = item.get("title") or ""
    score = exp.get("explosion_score")
    risk = q.get("quality_risk_level")
    rules = ", ".join(q.get("quality_rule_ids") or []) or "无"
    tip = "可关注转化与投放。" if risk in (None, "NONE", "LOW") else "建议先处理风险再放量。"
    return (
        f"**{sku}** {title}\n"
        f"- 爆品分（代码）：{score}\n"
        f"- 质检风险：{risk}（规则：{rules}）\n"
        f"- 建议：{tip}\n"
        f"- 近 30 天 GMV：{item.get('gmv_30d')}，点击：{item.get('clicks_30d')}，库存：{item.get('stock_qty')}"
    )


async def analyze_sku(
    runtime: AppRuntime,
    sku_id: str,
    *,
    user_question: str = "",
) -> dict[str, Any]:
    """
    对单个 SKU 做深挖分析。

    Args:
        runtime: AppRuntime。
        sku_id: SKU。
        user_question: 用户原问，供 LLM 参考。

    Returns:
        dict: reply / sku_id / locked / source。
    """
    feat = await get_product_features(runtime, sku_id)
    item = feat.get("item")
    if not item:
        return {
            "reply": f"未找到 {sku_id} 的快照特征，请确认 SKU 是否在售或快照是否已刷新。",
            "sku_id": sku_id,
            "source": "empty",
            "locked": None,
        }

    # 用少量同店数据估店铺均值（mock 下拉全量；正式可只拉同类目）
    try:
        batch = await query_features(
            runtime,
            on_sale_only=True,
            category_id=item.get("category_id"),
        )
        peers = batch.get("items") or [item]
    except Exception:
        logger.exception("peer features failed; use single item stats")
        peers = [item]

    store_stats = build_store_stats(peers)
    exp = score_sku(item, store_stats=store_stats)
    q = check_sku(item, store_stats=store_stats)

    locked = {
        "sku_id": sku_id,
        "snapshot_date": feat.get("snapshot_date"),
        "user_question": user_question,
        "item": {
            "sku_id": item.get("sku_id"),
            "title": item.get("title"),
            "category_id": item.get("category_id"),
            "gmv_30d": item.get("gmv_30d"),
            "gmv_prev_30d": item.get("gmv_prev_30d"),
            "clicks_30d": item.get("clicks_30d"),
            "orders_30d": item.get("orders_30d"),
            "stock_qty": item.get("stock_qty"),
            "price": item.get("price"),
            "cost": item.get("cost"),
            "review_score": item.get("review_score"),
        },
        "explosion": {
            "explosion_score": exp["explosion_score"],
            "score_breakdown": exp.get("score_breakdown"),
            "skipped_items": exp.get("skipped_items"),
        },
        "quality": {
            "quality_risk_level": q["quality_risk_level"],
            "quality_rule_ids": q["quality_rule_ids"],
            "issues": q.get("issues"),
        },
    }

    llm: LlmClient | None = runtime.llm_client
    source = "template"
    repairs: list[str] = []
    user_payload = json.dumps(locked, ensure_ascii=False)
    if llm is not None and llm.enabled:
        try:
            from harness.memory.repair import chat_with_repair

            async def _once(*, system: str, user: str) -> str:
                return await llm.chat(system=system, user=user)

            repaired = await chat_with_repair(_once, system=SYSTEM, user=user_payload)
            reply = repaired["text"]
            repairs = list(repaired.get("repairs") or [])
            source = "llm"
        except Exception:
            logger.exception("sku deep LLM failed")
            reply = _template_advice(locked)
            source = "template_fallback"
    else:
        reply = _template_advice(locked)

    return {
        "reply": reply,
        "sku_id": sku_id,
        "source": source,
        "locked": locked,
        "repairs": repairs,
    }

