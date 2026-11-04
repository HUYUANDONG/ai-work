"""
运营流水线 Supervisor：

决策 → 拉数 → 推荐∥库存 → Explosion(解读+有限进槽重排)
→ 问建议 →（LLM 建议）→ 问文案 → 文案(含合规)

正式分：代码 scoring；爆品 Agent 不改 explosion_score，只解读/微调进槽。
"""

from __future__ import annotations

import logging
from typing import Any

from agents.advise.agent import AdviseAgent
from agents.chat import intent as intent_mod
from agents.chat.sku_parse import extract_sku_ids, looks_like_storewide_quality
from agents.copy.agent import CopyAgent
from agents.data_task.agent import DataTaskAgent
from agents.decision.agent import DecisionAgent
from agents.inventory.agent import InventoryAgent
from agents.recommend.agent import RecommendAgent
from agents.supervisor.workbench import WorkbenchSupervisor
from harness.runtime import AppRuntime
from schemas.chat import ChatRequest, NeedTask
from tools.reports import get_conversation_reports

logger = logging.getLogger(__name__)

PHASE_IDLE = "IDLE"
PHASE_AWAITING_ADVISE = "AWAITING_ADVISE_CONFIRM"
PHASE_AWAITING_COPY = "AWAITING_COPY_CONFIRM"
PHASE_DONE = "DONE"

ASK_ADVISE = intent_mod.ADVICE_OFFER_QUESTION
ASK_COPY = "需要为焦点商品生成合规爆品文案吗？回复「要」或「不用」即可。"


class OpsSupervisor(WorkbenchSupervisor):
    """
    对话主路径编排器。

    在 WorkbenchSupervisor 上注册 ops 叶子，并实现 ``handle_turn``。
    """

    def __init__(
        self,
        *,
        llm: Any = None,
        council_llm_enabled: bool = False,
        timeout: float | None = 30.0,
    ) -> None:
        super().__init__(
            llm=llm,
            council_llm_enabled=council_llm_enabled,
            timeout=timeout,
        )
        self.register_agent(DecisionAgent(timeout=20.0))
        self.register_agent(DataTaskAgent(timeout=45.0))
        self.register_agent(RecommendAgent(timeout=15.0))
        self.register_agent(InventoryAgent(timeout=15.0))
        # explosion 已由 WorkbenchSupervisor 注册；此处覆盖超时即可
        self.register_agent(AdviseAgent(llm=llm, timeout=60.0))
        self.register_agent(CopyAgent(llm=llm, timeout=90.0))

    @classmethod
    def create(
        cls,
        *,
        llm: Any = None,
        council_llm_enabled: bool = False,
    ) -> "OpsSupervisor":
        return cls(llm=llm, council_llm_enabled=council_llm_enabled)

    async def handle_turn(
        self,
        *,
        runtime: AppRuntime,
        req: ChatRequest,
        mem: Any,
    ) -> dict[str, Any]:
        """
        处理一轮对话。

        Returns:
            dict: reply / intent / phase / clarify_pending / need_task / debug。
        """
        phase = str(getattr(mem, "ops_phase", None) or PHASE_IDLE)
        ctx = dict(getattr(mem, "ops_context", None) or {})

        # —— 门闩：等建议确认 ——
        if phase == PHASE_AWAITING_ADVISE:
            if intent_mod.is_advise_decline(req.message):
                mem.ops_phase = PHASE_DONE
                mem.advice_offer_pending = False
                return self._out(
                    "好的，先不写投放建议。之后想看文案或再筛爆品随时说。",
                    intent="FOLLOWUP",
                    phase=PHASE_DONE,
                    debug={"gate": "advise_decline"},
                )
            if intent_mod.is_advise_affirm(req.message):
                return await self._run_advise_then_ask_copy(runtime, req, mem, ctx)
            # 非要/不用：轻提示
            return self._out(
                ASK_ADVISE,
                intent="FOLLOWUP",
                phase=PHASE_AWAITING_ADVISE,
                debug={"gate": "advise_pending"},
            )

        # —— 门闩：等文案确认 ——
        if phase == PHASE_AWAITING_COPY:
            if intent_mod.is_advise_decline(req.message):
                mem.ops_phase = PHASE_DONE
                return self._out(
                    "好的，先不生成文案。有需要再说「要文案」。",
                    intent="FOLLOWUP",
                    phase=PHASE_DONE,
                    debug={"gate": "copy_decline"},
                )
            if intent_mod.is_advise_affirm(req.message) or "文案" in (req.message or ""):
                return await self._run_copy(runtime, req, mem, ctx)
            return self._out(
                ASK_COPY,
                intent="FOLLOWUP",
                phase=PHASE_AWAITING_COPY,
                debug={"gate": "copy_pending"},
            )

        # —— 主链：决策 → 拉数 → 推荐∥库存 ——
        decided = await self.run_agent("decision", runtime=runtime, req=req, mem=mem)
        intent = str((decided.data or {}).get("intent") or "CLARIFY")
        pipeline = str((decided.data or {}).get("pipeline") or "other")

        if pipeline != "ops_marketing":
            return await self._non_marketing_reply(
                runtime, req, mem, intent=intent, decision=decided.data or {}
            )

        days = intent_mod.parse_time_window_days(req.message) or int(
            (mem.last_task_input or {}).get("time_window_days") or 30
        )
        top_n = int((mem.last_task_input or {}).get("top_n") or 10)
        focus_slots = int((mem.last_task_input or {}).get("focus_slots") or 5)
        goal_mode = str((mem.last_task_input or {}).get("goal_mode") or "GMV")

        features_res = await self.run_agent(
            "data_task",
            runtime=runtime,
            task="marketing_features",
            user_id=req.user_id,
            time_window_days=days,
        )
        items = list((features_res.data or {}).get("features", {}).get("items") or [])

        # 推荐与库存并行：先推荐拿 sku，再拉库存策略后 inventory agent 解读
        rec = await self.run_agent(
            "recommend",
            items=items,
            top_n=top_n,
            focus_slots=focus_slots,
        )
        candidates = list((rec.data or {}).get("candidates") or [])
        sku_ids = [str(c.get("sku_id")) for c in candidates if c.get("sku_id")]

        inv_raw = await self.run_agent(
            "data_task",
            runtime=runtime,
            task="inventory",
            sku_ids=sku_ids,
        )
        inv = await self.run_agent(
            "inventory",
            inventory=(inv_raw.data or {}).get("inventory") or {},
        )
        inv_data = inv.data or {}

        exploded = await self.run_agent(
            "explosion",
            candidates=candidates,
            focus_slots=focus_slots,
            goal_mode=goal_mode,
            inventory_summary=str(inv_data.get("summary") or ""),
            llm=runtime.llm_client,
        )
        candidates = list((exploded.data or {}).get("candidates") or candidates)
        analysis_text = str((exploded.data or {}).get("text") or "").strip()

        reply = self._format_rec_inv_reply(candidates, inv_data)
        if analysis_text:
            reply = f"{reply}\n\n【爆品解读】\n{analysis_text}"
        reply = f"{reply}\n\n{ASK_ADVISE}"

        ctx = {
            "candidates": candidates,
            "inventory": inv_data,
            "goal_mode": goal_mode,
            "time_window_days": days,
            "focus_slots": focus_slots,
            "user_id": req.user_id,
            "conversation_id": req.conversation_id,
            "analysis_text": analysis_text,
            "explosion_source": exploded.source,
        }
        mem.ops_context = ctx
        mem.ops_phase = PHASE_AWAITING_ADVISE
        mem.advice_offer_pending = True
        mem.last_intent = "EXPLOSION"
        mem.last_task_input = {
            **dict(mem.last_task_input or {}),
            "time_window_days": days,
            "goal_mode": goal_mode,
            "focus_slots": focus_slots,
            "top_n": top_n,
        }

        return self._out(
            reply,
            intent="EXPLOSION",
            phase=PHASE_AWAITING_ADVISE,
            debug={
                "decision": decided.data,
                "rec_count": len(candidates),
                "inv_warnings": inv_data.get("warning_count"),
                "scoring": rec.source,
                "explosion_source": exploded.source,
            },
        )

    async def _run_advise_then_ask_copy(
        self,
        runtime: AppRuntime,
        req: ChatRequest,
        mem: Any,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        candidates = list(ctx.get("candidates") or [])
        focus_ids = [
            str(c.get("sku_id"))
            for c in candidates
            if c.get("in_focus_slot") and c.get("sku_id")
        ] or [str(c.get("sku_id")) for c in candidates[:5] if c.get("sku_id")]

        advise_ctx_res = await self.run_agent(
            "data_task",
            runtime=runtime,
            task="advise_context",
            user_id=str(ctx.get("user_id") or req.user_id or ""),
            sku_ids=focus_ids,
            days=7,
        )
        advise_context = (advise_ctx_res.data or {}).get("advise_context") or {}

        advised = await self.run_agent(
            "advise",
            candidates=candidates,
            advise_context=advise_context,
            goal_mode=str(ctx.get("goal_mode") or "GMV"),
            llm=runtime.llm_client,
        )
        text = str((advised.data or {}).get("text") or "").strip() or "暂时写不出投放建议。"
        reply = f"{text}\n\n{ASK_COPY}"

        ctx = {**ctx, "advise_text": text, "advise_source": advised.source}
        mem.ops_context = ctx
        mem.ops_phase = PHASE_AWAITING_COPY
        mem.advice_offer_pending = False

        return self._out(
            reply,
            intent="FOLLOWUP",
            phase=PHASE_AWAITING_COPY,
            debug={"advise_source": advised.source},
        )

    async def _run_copy(
        self,
        runtime: AppRuntime,
        req: ChatRequest,
        mem: Any,
        ctx: dict[str, Any],
    ) -> dict[str, Any]:
        candidates = list(ctx.get("candidates") or [])
        focus_ids = [
            str(c.get("sku_id"))
            for c in candidates
            if c.get("in_focus_slot") and c.get("sku_id")
        ] or [str(c.get("sku_id")) for c in candidates[:3] if c.get("sku_id")]

        bundle_res = await self.run_agent(
            "data_task",
            runtime=runtime,
            task="product_bundle",
            sku_ids=focus_ids,
        )
        bundles = list((bundle_res.data or {}).get("bundles") or [])
        copied = await self.run_agent(
            "copy",
            bundles=bundles,
            llm=runtime.llm_client,
        )
        text = str((copied.data or {}).get("text") or "文案生成失败。")
        mem.ops_phase = PHASE_DONE
        mem.ops_context = {**ctx, "copies": (copied.data or {}).get("copies")}
        return self._out(
            text,
            intent="FOLLOWUP",
            phase=PHASE_DONE,
            debug={"copy_source": copied.source},
        )

    async def _non_marketing_reply(
        self,
        runtime: AppRuntime,
        req: ChatRequest,
        mem: Any,
        *,
        intent: str,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """非营销主链：质检 NEED_TASK / 深挖 / 追问 / 能力 / 拒识。"""
        if intent == "QUALITY":
            return await self._quality_need_task(runtime, req, mem, decision=decision)

        if intent == "SKU_DEEP":
            skus = extract_sku_ids(req.message)
            if not skus:
                return self._out(
                    "请给出要分析的 SKU，例如：「帮我分析 SKU-001」。",
                    intent="CLARIFY",
                    phase=PHASE_IDLE,
                    clarify=True,
                    debug={"decision": decision},
                )
            deep = await self.run_sku_deep(
                runtime=runtime,
                sku_id=skus[0],
                user_question=req.message,
            )
            data = dict(deep.data or {})
            return self._out(
                str(data.get("reply") or ""),
                intent="SKU_DEEP",
                phase=PHASE_IDLE,
                debug={"decision": decision, "sku_deep": data.get("source")},
            )

        if intent == "FOLLOWUP":
            followed = await self.run_followup(
                runtime=runtime,
                conversation_id=req.conversation_id,
                user_id=req.user_id,
                message=req.message,
                history=req.history,
            )
            data = dict(followed.data or {})
            return self._out(
                str(data.get("reply") or ""),
                intent="FOLLOWUP",
                phase=PHASE_IDLE,
                debug={"decision": decision, "followup": data.get("source")},
            )

        if intent == "OUT_OF_SCOPE":
            return self._out(
                intent_mod.out_of_scope_reply(),
                intent="OUT_OF_SCOPE",
                phase=PHASE_IDLE,
                debug={"decision": decision},
            )

        if intent in {"META", "CAPABILITY", "CHITCHAT"}:
            return self._out(
                "我可以：① 店内爆品榜+库存预警；② LLM 投放建议；③ 合规爆品文案；"
                "④ 质检报告（Worker）；⑤ 单品深挖 / 报告追问。直接说「近7天爆品」即可开跑。",
                intent="META" if intent != "CHITCHAT" else intent,
                phase=PHASE_IDLE,
                debug={"decision": decision},
            )

        if intent == "CLARIFY":
            return self._out(
                "你是要**筛爆品**、**质检报告**，还是**分析某个 SKU**？可以说具体一点。",
                intent="CLARIFY",
                phase=PHASE_IDLE,
                clarify=True,
                debug={"decision": decision},
            )

        return self._out(
            "可以说「近7天爆品」开始运营流水线，或「分析 SKU-001」做单品深挖。",
            intent=intent or "CLARIFY",
            phase=PHASE_IDLE,
            clarify=True,
            debug={"decision": decision},
        )

    async def _quality_need_task(
        self,
        runtime: AppRuntime,
        req: ChatRequest,
        mem: Any,
        *,
        decision: dict[str, Any],
    ) -> dict[str, Any]:
        """质检仍走 Java Worker 长任务。"""
        skus = extract_sku_ids(req.message)
        storewide = looks_like_storewide_quality(req.message)
        if not skus and "这批" in (req.message or ""):
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

        if not skus and not storewide and "质检" in (req.message or ""):
            return self._out(
                "质检指定商品请带上 SKU（如「质检 SKU-001」）；扫全店问题品可以说「看看谁亏本或缺货」。",
                intent="CLARIFY",
                phase=PHASE_IDLE,
                clarify=True,
                debug={"decision": decision},
            )

        window = intent_mod.resolve_time_window_days(
            req.message,
            decision.get("window_days"),
        )
        prev_raw = mem.last_task_input if mem.last_intent == "QUALITY" else {}
        prev = prev_raw if isinstance(prev_raw, dict) else {}
        task_input: dict[str, Any] = {
            "time_window_days": window or prev.get("time_window_days") or 30,
            "sku_ids": skus or prev.get("sku_ids"),
            "on_sale_only": True,
            "storewide_problems": bool(storewide and not skus),
        }
        mem.last_intent = "QUALITY"
        mem.last_task_input = dict(task_input)
        mem.ops_phase = PHASE_IDLE
        return self._out(
            "已识别为质检。Java 建任务后将拉取特征、跑规则并生成质检报告。",
            intent="QUALITY",
            phase=PHASE_IDLE,
            need_task=NeedTask(task_type="QUALITY", input=task_input),
            debug={"decision": decision},
        )

    @staticmethod
    def _format_rec_inv_reply(
        candidates: list[dict[str, Any]],
        inv_data: dict[str, Any],
    ) -> str:
        if not candidates:
            return "这批窗口里没筛出足够营销信号的在售商品，可换时间窗或类目再试。"
        lines = ["本轮爆品榜（代码评分，非 LLM 口算）："]
        for c in candidates[:10]:
            slot = "★" if c.get("in_focus_slot") else "·"
            lines.append(
                f"{slot} #{c.get('rank')} {c.get('sku_id')} "
                f"{c.get('title') or ''} 分={c.get('explosion_score')} "
                f"风险={c.get('quality_risk_level')}"
            )
        lines.append("")
        lines.append("库存与限购：")
        lines.append(str(inv_data.get("summary") or "（无库存摘要）"))
        return "\n".join(lines)

    @staticmethod
    def _out(
        reply: str,
        *,
        intent: str,
        phase: str,
        clarify: bool = False,
        need_task: NeedTask | None = None,
        debug: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "reply": reply,
            "intent": intent,
            "phase": phase,
            "clarify_pending": clarify,
            "need_task": need_task.model_dump() if need_task is not None else None,
            "debug": debug or {},
        }
