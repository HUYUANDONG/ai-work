"""追问：分层记忆 + Session Facts + 预算裁剪 + 自修复。"""

from __future__ import annotations

import logging
from typing import Any

from clients.llm_client import LlmClient
from harness.memory.facts import extract_report_facts, render_facts_block
from harness.memory.fields import ops_goods_view
from harness.memory.repair import chat_with_repair
from harness.memory.slim import slim_reports_for_llm
from harness.memory.summarize import deep_summarize_if_needed
from harness.runtime import AppRuntime
from tools.reports import get_conversation_reports

logger = logging.getLogger(__name__)

SYSTEM = """你是运营助手。根据 [Session Facts] 与上下文回答追问。
硬性：数字只引用运营接口字段（goodsId、goodsName、orderSales、orderNumbers、orderPays、goodsPv、goodsUv、ratePer、statDay）。
缺字段视为未知，禁止当 0；禁止把昨日 goodsPv/goodsUv 与实时 orderSales/orderNumbers 说成同一窗口。
禁止编造未出现的商品；禁止建议改价上架等写回。简短中文。"""


def _template_followup(reports: list[dict[str, Any]], question: str) -> str:
    if not reports:
        return "本会话还没有分析报告。可以说「帮我筛本周重点」或「分析 SKU-xxx」。"
    r0 = reports[0]
    header = r0.get("header") or {}
    items = r0.get("items") or []
    lines = [
        f"最近一份 **{r0.get('task_type')}** 报告（task={r0.get('task_id')}）：",
        str(header.get("summary") or "（无 summary）"),
    ]
    for it in items[:5]:
        ops = ops_goods_view(it)
        gid = ops.get("goodsId") or it.get("sku_id") or "?"
        name = ops.get("goodsName") or ""
        sales = ops.get("orderSales")
        orders = ops.get("orderNumbers")
        lines.append(
            f"- {gid} {name}: orderSales={sales} orderNumbers={orders} "
            f"goodsPv={ops.get('goodsPv')} goodsUv={ops.get('goodsUv')}"
        )
    lines.append(f"（针对你的问题：{question[:80]}）")
    return "\n".join(lines)


async def answer_followup(
    runtime: AppRuntime,
    *,
    conversation_id: str,
    user_id: str,
    message: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    读取会话报告，用分层记忆组装上下文并回答。

    Returns:
        dict: reply / report_count / source / memory_meta。
    """
    data = await get_conversation_reports(
        runtime,
        conversation_id,
        user_id=user_id,
        limit=3,
    )
    reports = list(data.get("reports") or [])
    if not reports:
        return {
            "reply": "本会话还没有可追问的报告。先「筛爆品」或「分析/质检某个 SKU」即可。",
            "report_count": 0,
            "source": "empty",
        }

    mem = runtime.memory_store.get(conversation_id)
    keep = int(runtime.settings.chat_working_keep_last)
    # graph 已 hydrate；仅当 working 空时兜底同步
    if not mem.working:
        for h in history or []:
            role = str(h.get("role") or "user")
            content = str(h.get("content") or "")
            if content:
                mem.add_turn(role, content, keep_last=keep)
        mem.add_turn("user", message, keep_last=keep)
    summarize_meta = await deep_summarize_if_needed(
        mem,
        llm=runtime.llm_client,
        budget=runtime.token_budget,
        keep_last=keep,
        pressure_threshold=float(runtime.settings.chat_summary_pressure),
    )

    facts = extract_report_facts(reports)
    for b in facts.get("reports") or []:
        ref = str(b.get("archive_ref") or "")
        if ref:
            mem.add_archive(ref, {"task_type": b.get("task_type")})
    facts_text = render_facts_block(facts)

    slim_reports = slim_reports_for_llm(reports)
    layers = mem.build_prompt_layers(
        system=SYSTEM,
        facts_text=facts_text,
        question=message + "\n\n[Slim reports JSON]\n" + str(slim_reports),
        budget=runtime.token_budget,
    )

    llm: LlmClient | None = runtime.llm_client
    source = "template"
    repairs: list[str] = []
    if llm is not None and llm.enabled:
        try:

            async def _once(*, system: str, user: str) -> str:
                return await llm.chat(system=system, user=user)

            repaired = await chat_with_repair(
                _once, system=layers["system"], user=layers["user"]
            )
            reply = repaired["text"]
            repairs = list(repaired.get("repairs") or [])
            source = "llm"
            mem.add_turn("assistant", reply, keep_last=keep)
        except Exception:
            logger.exception("followup LLM failed")
            reply = _template_followup(reports, message)
            source = "template_fallback"
    else:
        reply = _template_followup(reports, message)

    return {
        "reply": reply,
        "report_count": len(reports),
        "source": source,
        "working_summary": mem.summary or None,
        "summary_through_message_id": getattr(mem, "summary_through_message_id", None),
        "memory_meta": {
            "committed_tokens": layers.get("committed_tokens"),
            "input_limit": layers.get("input_limit"),
            "truncated": layers.get("truncated"),
            "over_budget": layers.get("over_budget"),
            "summarize": summarize_meta,
            "archives": [a.get("ref") for a in mem.archives[-5:]],
            "repairs": repairs,
        },
    }
