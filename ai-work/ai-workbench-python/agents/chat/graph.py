"""
对话领域图：意图分类 → 分支 → 短回复 和/或 NEED_TASK / 单品深挖。

不拉全店特征做筛选；SKU_DEEP 仅查单品；长任务交给 Java + Worker。
"""

from __future__ import annotations

from typing import Any

from agents.chat import intent as intent_mod
from agents.chat.decision_intent import resolve_intent
from agents.chat.followup import answer_followup
from agents.chat.sku_deep import analyze_sku
from agents.chat.sku_parse import (
    extract_sku_ids,
    looks_like_sku_deep,
    looks_like_storewide_quality,
)
from harness.runtime import AppRuntime
from schemas.chat import ChatRequest, ChatResponse, NeedTask
from tools.reports import get_conversation_reports


def _is_control_message(message: str) -> bool:
    """是否像「取消/暂停」控制指令（仍交给 Java 写 cancel/pause 标志）。"""
    text = (message or "").strip()
    return any(k in text for k in ("取消", "停止", "暂停", "cancel", "pause", "别跑了"))


def _with_debug(resp: ChatResponse, intent_meta: dict[str, Any]) -> dict[str, Any]:
    data = resp.model_dump()
    data["debug"] = {"intent_meta": intent_meta}
    return data


async def run_chat(
    payload: dict[str, Any] | ChatRequest,
    runtime: AppRuntime,
) -> dict[str, Any]:
    """
    执行一轮对话领域逻辑。

    Args:
        payload: Java 传来的消息。
        runtime: 共享运行时。

    Returns:
        dict: intent / reply / need_task / clarify_pending（及 debug）。
    """
    req = payload if isinstance(payload, ChatRequest) else ChatRequest.model_validate(payload)
    settings = runtime.settings

    # 长任务进行中：取消/暂停提示 Java 写标志；其它追问入队
    if req.queue_message or req.active_task_id:
        if _is_control_message(req.message) and req.active_task_id:
            pause = any(k in req.message for k in ("暂停", "pause"))
            action = "pause" if pause else "cancel"
            if runtime.java_client.mock_features:
                if pause:
                    runtime.java_client.mock_request_pause(req.active_task_id)
                else:
                    runtime.java_client.mock_request_cancel(req.active_task_id)
            return _with_debug(
                ChatResponse(
                    intent="QUEUED",
                    reply=("已请求暂停，将在当前思考步骤结束后停下。"
                           if pause else "已请求取消，将尽快停止分析。"),
                    need_task=None,
                    clarify_pending=False,
                    queue_ack={
                        "queued": False,
                        "control": action,
                        "active_task_id": req.active_task_id,
                    },
                    ui_hints={
                        "show_thinking": True,
                        "allow_pause": True,
                        "allow_cancel": True,
                        "active_task_id": req.active_task_id,
                        "control_requested": action,
                    },
                ),
                {"source": "control_gate", "confidence": 1.0},
            )

        depth = 0
        if runtime.java_client.mock_features:
            depth = runtime.java_client.mock_enqueue_user_message(
                req.conversation_id,
                {
                    "user_id": req.user_id,
                    "message": req.message,
                    "active_task_id": req.active_task_id,
                },
            )
        return _with_debug(
            ChatResponse(
                intent="QUEUED",
                reply=(
                    "当前正在分析中，你的问题已进入排队。"
                    f"{'队列约 ' + str(depth) + ' 条。' if depth else ''}"
                    "可点「暂停/取消」停止思考；结束后会按序处理追问。"
                ),
                need_task=None,
                clarify_pending=False,
                queue_ack={
                    "queued": True,
                    "active_task_id": req.active_task_id,
                    "queue_depth": depth or None,
                },
                ui_hints={
                    "show_thinking": True,
                    "allow_pause": True,
                    "allow_cancel": True,
                    "active_task_id": req.active_task_id,
                },
            ),
            {"source": "queue_gate", "confidence": 1.0},
        )

    mem = runtime.memory_store.get(req.conversation_id)
    if req.last_intent:
        mem.last_intent = req.last_intent
    if req.last_task_input:
        mem.last_task_input = dict(req.last_task_input)
    if req.history and len(mem.working) < 2:
        for item in req.history:
            role = str(item.get("role") or "user")
            content = str(item.get("content") or "")
            intent = item.get("intent")
            if content:
                mem.add_turn(
                    role,
                    content,
                    intent=str(intent) if intent else None,
                )
    mem.add_turn("user", req.message)
    last_intent = (
        req.last_intent
        or mem.last_intent
        or intent_mod.infer_last_task_intent(req.history)
        or intent_mod.infer_last_task_intent(mem.working)
    )

    decision = await resolve_intent(
        req.message,
        api_key=settings.dashscope_api_key,
        enabled=settings.decision_intent_enabled,
        model=settings.decision_model,
        min_confidence=settings.decision_min_confidence,
        allow_rules_fallback=settings.decision_allow_rules_fallback,
        base_url=settings.decision_base_url,
        workspace_id=settings.decision_workspace_id,
        region=settings.decision_region,
        history=mem.working[:-1],
        last_intent=last_intent,
        chat_base_url=settings.llm_base_url,
        chat_model=settings.llm_model,
    )

    kind = decision.intent
    # 规则/决策模型后置校正：有明确 SKU 深挖话术时优先 SKU_DEEP
    if kind in {"CLARIFY", "EXPLOSION", "QUALITY"} and looks_like_sku_deep(req.message):
        kind = "SKU_DEEP"
    if kind == "QUALITY" and looks_like_sku_deep(req.message) and "质检" not in req.message:
        kind = "SKU_DEEP"

    intent_meta = {
        "source": decision.source,
        "confidence": decision.confidence,
        "probabilities": decision.probabilities,
        "error": decision.error,
        "resolved_intent": kind,
    }

    if kind == "OUT_OF_SCOPE":
        return _with_debug(
            ChatResponse(
                intent="OUT_OF_SCOPE",
                reply=intent_mod.out_of_scope_reply(),
                need_task=None,
                clarify_pending=False,
            ),
            intent_meta,
        )

    if kind == "META":
        return _with_debug(
            ChatResponse(
                intent="META",
                reply=(
                    "我可以：① 爆品作战清单；② 指定商品质检报告；"
                    "③ 上来就问「分析 SKU-xxx」做单品建议；④ 追问本会话报告。"
                    "直接说需求即可。"
                ),
                need_task=None,
                clarify_pending=False,
            ),
            intent_meta,
        )

    if kind == "CLARIFY":
        reply = "你是要**筛爆品**、**质检报告**，还是**分析某个 SKU**？可以说具体一点。"
        if decision.source == "decision_disabled":
            reply = (
                "意图服务未配置（需要 DASHSCOPE_API_KEY）。"
                "请配置阿里云百炼决策模型，或开启规则降级。"
                "也可直接说「筛爆品」「质检」或「分析 SKU-xxx」。"
            )
        return _with_debug(
            ChatResponse(
                intent="CLARIFY",
                reply=reply,
                need_task=None,
                clarify_pending=True,
            ),
            intent_meta,
        )

    if kind == "SKU_DEEP":
        skus = extract_sku_ids(req.message)
        if not skus:
            return _with_debug(
                ChatResponse(
                    intent="CLARIFY",
                    reply="请给出要分析的 SKU，例如：「帮我分析 SKU-001」。",
                    need_task=None,
                    clarify_pending=True,
                ),
                intent_meta,
            )
        # 多 SKU 时本轮分析第一个，并提示可继续追问
        result = await analyze_sku(runtime, skus[0], user_question=req.message)
        reply = result["reply"]
        if len(skus) > 1:
            reply += f"\n（本轮先分析了 {skus[0]}；其余 {', '.join(skus[1:3])} 可再说一声继续。）"
        data = _with_debug(
            ChatResponse(
                intent="SKU_DEEP",
                reply=reply,
                need_task=None,
                clarify_pending=False,
            ),
            intent_meta,
        )
        data["debug"]["sku_deep"] = {
            "sku_id": result.get("sku_id"),
            "source": result.get("source"),
        }
        return data

    if kind == "FOLLOWUP":
        result = await answer_followup(
            runtime,
            conversation_id=req.conversation_id,
            user_id=req.user_id,
            message=req.message,
            history=req.history,
        )
        data = _with_debug(
            ChatResponse(
                intent="FOLLOWUP",
                reply=result["reply"],
                need_task=None,
                clarify_pending=False,
            ),
            intent_meta,
        )
        data["debug"]["followup"] = {
            "report_count": result.get("report_count"),
            "source": result.get("source"),
            "memory_meta": result.get("memory_meta"),
        }
        return data

    if kind == "QUALITY":
        skus = extract_sku_ids(req.message)
        storewide = looks_like_storewide_quality(req.message)
        if not skus and "这批" in req.message:
            try:
                reports = await get_conversation_reports(
                    runtime,
                    req.conversation_id,
                    user_id=req.user_id,
                    limit=1,
                )
                items = (reports.get("reports") or [{}])[0].get("items") or []
                skus = [str(x["sku_id"]) for x in items if x.get("sku_id")][:50]
            except Exception:
                skus = []

        if not skus and not storewide and "质检" in req.message:
            return _with_debug(
                ChatResponse(
                    intent="CLARIFY",
                    reply="质检指定商品请带上 SKU（如「质检 SKU-001」）；扫全店问题品可以说「看看谁亏本或缺货」。",
                    need_task=None,
                    clarify_pending=True,
                ),
                intent_meta,
            )

        window = intent_mod.resolve_time_window_days(req.message, decision.window_days)
        prev_raw = (req.last_task_input or mem.last_task_input) if last_intent == "QUALITY" else {}
        prev = prev_raw if isinstance(prev_raw, dict) else {}
        task_input: dict[str, Any] = {
            "time_window_days": window
            or prev.get("time_window_days")
            or 30,
            "sku_ids": skus or prev.get("sku_ids"),
            "on_sale_only": True,
            "storewide_problems": bool(storewide and not skus),
        }
        reply = "已识别为质检。Java 建任务后将拉取特征、跑规则并生成质检报告。"
        mem.last_intent = "QUALITY"
        mem.last_task_input = dict(task_input)
        mem.add_turn("assistant", reply, intent="QUALITY")
        return _with_debug(
            ChatResponse(
                intent="QUALITY",
                reply=reply,
                need_task=NeedTask(task_type="QUALITY", input=task_input),
                clarify_pending=False,
            ),
            intent_meta,
        )

    # EXPLOSION（默认主路径；短句「近7天」继承上一轮参数）
    prev_input = req.last_task_input or mem.last_task_input
    task_input = intent_mod.build_explosion_input(
        req.message,
        prev_input if last_intent == "EXPLOSION" else None,
    )
    window = intent_mod.resolve_time_window_days(req.message, decision.window_days)
    if window is not None:
        task_input["time_window_days"] = window
    user_set_window = window is not None
    reply = (
        f"{intent_mod.window_notice(int(task_input['time_window_days']), user_specified=user_set_window)}"
        f"目标模式 {task_input['goal_mode']}，本周槽位 {task_input['focus_slots']}。"
        "已生成分析任务请求，Java 建任务后由 Worker 继续。"
    )
    mem.last_intent = "EXPLOSION"
    mem.last_task_input = dict(task_input)
    mem.add_turn("assistant", reply, intent="EXPLOSION")
    return _with_debug(
        ChatResponse(
            intent="EXPLOSION",
            reply=reply,
            need_task=NeedTask(task_type="EXPLOSION", input=task_input),
            clarify_pending=False,
            ui_hints={
                "show_thinking": True,
                "allow_pause": True,
                "allow_cancel": True,
                "queue_followups": True,
            },
        ),
        intent_meta,
    )

