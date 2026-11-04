"""单品深挖：查 Java 特征 → 代码挂标摘要 → LLM/模板建议。"""

from __future__ import annotations

import json
import logging
from typing import Any

from clients.llm_client import LlmClient
from harness.memory.fields import ops_goods_view
from harness.runtime import AppRuntime
from scoring.quality import check_sku
from scoring.store_stats import build_store_stats
from tools.features import get_product_features, query_features

logger = logging.getLogger(__name__)

SYSTEM = """你是店内商品运营顾问。根据锁定的运营接口字段给出简短中文建议。
硬性要求：数字只引用 item 中的 goodsId/orderSales/orderNumbers/goodsPv/goodsUv/ratePer 等词典字段；
缺字段视为未知，禁止当 0；昨日 PV/UV 与实时销售额不是同一窗口。
指出 quality.issues 中的规则；给出 2～4 条可执行建议。不要输出 Markdown 代码围栏。"""


def _template_advice(locked: dict[str, Any]) -> str:
    item = locked.get("item") or {}
    q = locked.get("quality") or {}
    goods_id = item.get("goodsId") or locked.get("sku_id")
    name = item.get("goodsName") or ""
    risk = q.get("quality_risk_level")
    rules = ", ".join(q.get("quality_rule_ids") or []) or "无"
    tip = "可关注转化与投放。" if risk in (None, "NONE", "LOW") else "建议先处理风险再放量。"
    return (
        f"**{goods_id}** {name}\n"
        f"- orderSales={item.get('orderSales')} orderNumbers={item.get('orderNumbers')} "
        f"orderPays={item.get('orderPays')}\n"
        f"- goodsPv={item.get('goodsPv')} goodsUv={item.get('goodsUv')} ratePer={item.get('ratePer')} "
        f"（PV/UV 为昨日，销售为实时）\n"
        f"- 质检风险：{risk}（规则：{rules}）\n"
        f"- 建议：{tip}"
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
    q = check_sku(item, store_stats=store_stats)

    locked = {
        "sku_id": sku_id,
        "snapshot_date": feat.get("snapshot_date"),
        "user_question": user_question,
        "item": ops_goods_view(item),
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

