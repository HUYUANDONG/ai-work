"""
对话入口：闸门（排队/控制）+ 记忆补水 → OpsSupervisor.handle_turn。

营销主链（爆品→库存→问建议→LLM建议→问文案→合规文案）由 OpsSupervisor 编排；
质检仍回 NEED_TASK 给 Java Worker。
"""

from __future__ import annotations

from typing import Any

from agents.chat import intent as intent_mod
from agents.supervisor.ops import OpsSupervisor
from harness.memory.summarize import deep_summarize_if_needed
from harness.runtime import AppRuntime
from schemas.chat import ChatRequest, ChatResponse, NeedTask


def _ops_supervisor(runtime: AppRuntime) -> OpsSupervisor:
    """进程内复用 OpsSupervisor（含 Workbench 全部叶子）。"""
    if isinstance(runtime.supervisor, OpsSupervisor):
        return runtime.supervisor
    runtime.supervisor = OpsSupervisor.create(
        llm=runtime.llm_client,
        council_llm_enabled=bool(
            getattr(runtime.settings, "council_llm_enabled", False)
        ),
    )
    return runtime.supervisor


def _is_control_message(message: str) -> bool:
    """是否像「取消/暂停/继续」控制指令。"""
    text = (message or "").strip().lower()
    return any(
        k in text
        for k in (
            "取消",
            "停止",
            "暂停",
            "继续",
            "恢复",
            "cancel",
            "pause",
            "resume",
            "continue",
            "别跑了",
        )
    )


def _control_action(message: str) -> str:
    """从话术解析 pause|cancel|resume。"""
    text = (message or "").strip().lower()
    if any(k in text for k in ("暂停", "pause")):
        return "pause"
    if any(k in text for k in ("继续", "恢复", "resume", "continue")):
        return "resume"
    return "cancel"


def _with_debug(resp: ChatResponse, intent_meta: dict[str, Any]) -> dict[str, Any]:
    data = resp.model_dump()
    data["debug"] = {"intent_meta": intent_meta}
    return data


async def _hydrate_session_memory(mem: Any, req: ChatRequest, runtime: AppRuntime) -> dict[str, Any]:
    """
    用 Java 下发的 STM/LTM 覆盖进程记忆；仅在高水位时 LLM 深度摘要。

    Args:
        mem: SessionMemory。
        req: 本轮请求。
        runtime: 运行时（token 预算 / keep_last）。

    Returns:
        dict: 摘要元信息（是否压缩、压力等）。
    """
    keep = int(runtime.settings.chat_working_keep_last)
    if req.last_intent:
        mem.last_intent = req.last_intent
    if req.last_task_input:
        mem.last_task_input = dict(req.last_task_input)
        if mem.last_task_input.get("advice_offer_pending") is True:
            mem.advice_offer_pending = True
        if mem.last_task_input.get("include_advise") is True:
            mem.advice_offer_pending = False
        ops_phase = mem.last_task_input.get("ops_phase")
        if ops_phase:
            mem.ops_phase = str(ops_phase)
        ops_ctx = mem.last_task_input.get("ops_context")
        if isinstance(ops_ctx, dict):
            mem.ops_context = dict(ops_ctx)
        report_id = mem.last_task_input.get("last_report_task_id")
        if report_id:
            mem.last_report_task_id = str(report_id)
    mem.summary = str(req.working_summary or "")
    mem.episodes = [dict(item) for item in (req.episodes or []) if isinstance(item, dict)]
    if req.history:
        mem.working = []
        for item in req.history:
            mem.add_turn_item(item, keep_last=keep)
    mem.add_turn("user", req.message, keep_last=keep)
    return await deep_summarize_if_needed(
        mem,
        llm=runtime.llm_client,
        budget=runtime.token_budget,
        keep_last=keep,
        pressure_threshold=float(runtime.settings.chat_summary_pressure),
    )


def _finish(
    mem: Any,
    resp: ChatResponse,
    intent_meta: dict[str, Any],
) -> dict[str, Any]:
    """回写会话相位标志与 working_summary 后再序列化响应。"""
    mem.awaiting_clarify = bool(resp.clarify_pending)
    # 把 ops 相位写回 last_task_input，便于 Java STM 跨进程恢复
    mem.last_task_input = {
        **dict(mem.last_task_input or {}),
        "ops_phase": getattr(mem, "ops_phase", None) or "IDLE",
        "advice_offer_pending": bool(mem.advice_offer_pending),
    }
    if getattr(mem, "ops_context", None):
        slim_ctx: dict[str, Any] = {
            k: mem.ops_context[k]
            for k in ("goal_mode", "time_window_days", "focus_slots", "advise_text")
            if k in mem.ops_context
        }
        cands = mem.ops_context.get("candidates")
        if isinstance(cands, list):
            slim_ctx["candidates"] = [
                {
                    "sku_id": c.get("sku_id"),
                    "title": c.get("title"),
                    "explosion_score": c.get("explosion_score"),
                    "quality_risk_level": c.get("quality_risk_level"),
                    "rank": c.get("rank"),
                    "in_focus_slot": c.get("in_focus_slot"),
                }
                for c in cands[:20]
                if isinstance(c, dict)
            ]
        mem.last_task_input["ops_context"] = slim_ctx

    if mem.summary:
        resp.working_summary = mem.summary
    through_id = getattr(mem, "summary_through_message_id", None)
    if through_id:
        resp.summary_through_message_id = int(through_id)
    summarize_meta = getattr(mem, "last_summarize_meta", None)
    if summarize_meta:
        intent_meta = {**intent_meta, "summarize": summarize_meta}
    return _with_debug(resp, intent_meta)


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

    # 长任务进行中：取消/暂停提示 Java 写标志；「再试一次」开新任务；其它追问才入队
    if (req.queue_message or req.active_task_id) and not intent_mod.is_retry_message(
        req.message
    ):
        if _is_control_message(req.message) and req.active_task_id:
            action = _control_action(req.message)
            try:
                await runtime.java_client.request_task_control(
                    req.active_task_id,
                    action=action,
                    reason=req.message.strip()[:80],
                )
            except Exception:
                pass
            if action == "pause":
                reply = "已请求暂停，将在当前思考步骤结束后停下。"
            elif action == "resume":
                reply = "已请求继续：将从上次暂停的节点断点续跑。"
            else:
                reply = "已请求取消，将尽快停止分析。"
            return _with_debug(
                ChatResponse(
                    intent="QUEUED",
                    reply=reply,
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
                        "allow_resume": True,
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
                    "上一轮分析还在跑，这句先记下了。"
                    f"{'队列约 ' + str(depth) + ' 条。' if depth else ''}"
                    "要重跑请直接说「再试一次」；要停掉请说「取消」。"
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
    mem.last_summarize_meta = await _hydrate_session_memory(mem, req, runtime)

    # 历史兜底：assistant 问过建议确认
    if not mem.advice_offer_pending and mem.ops_phase not in {
        "AWAITING_ADVISE_CONFIRM",
        "AWAITING_COPY_CONFIRM",
    }:
        for item in reversed(list(req.history or []) + list(mem.working or [])):
            if str(item.get("role") or "") != "assistant":
                continue
            content = str(item.get("content") or "")
            if intent_mod.ADVICE_OFFER_QUESTION in content:
                mem.advice_offer_pending = True
                mem.ops_phase = "AWAITING_ADVISE_CONFIRM"
            elif "合规爆品文案" in content and "回复「要」" in content:
                mem.ops_phase = "AWAITING_COPY_CONFIRM"
            break

    result = await _ops_supervisor(runtime).handle_turn(
        runtime=runtime,
        req=req,
        mem=mem,
    )

    reply = str(result.get("reply") or "")
    intent = str(result.get("intent") or "CLARIFY")
    mem.add_turn("assistant", reply, intent=intent)

    need_raw = result.get("need_task")
    need_task = None
    if isinstance(need_raw, dict):
        need_task = NeedTask.model_validate(need_raw)
    elif isinstance(need_raw, NeedTask):
        need_task = need_raw

    intent_meta = {
        "source": "ops_supervisor",
        "confidence": 1.0,
        "session_phase": result.get("phase") or mem.ops_phase,
        **(result.get("debug") or {}),
    }

    return _finish(
        mem,
        ChatResponse(
            intent=intent,
            reply=reply,
            need_task=need_task,
            clarify_pending=bool(result.get("clarify_pending")),
        ),
        intent_meta,
    )
