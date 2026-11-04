"""决策 Agent：包装意图解析，判断是否走营销爆品主链。"""

from __future__ import annotations

from typing import Any

from agents.base import BaseAgent
from agents.chat.decision_intent import resolve_intent
from harness.memory.dialog_state import format_router_state
from harness.runtime import AppRuntime
from schemas.agent import AgentResult
from schemas.chat import ChatRequest

_MARKETING = frozenset({"EXPLOSION"})


class DecisionAgent(BaseAgent):
    """意图决策叶子。"""

    def __init__(self, *, timeout: float | None = 20.0) -> None:
        super().__init__(name="decision", timeout=timeout)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        runtime: AppRuntime = kwargs["runtime"]
        req: ChatRequest = kwargs["req"]
        mem = kwargs.get("mem")
        settings = runtime.settings
        session_state: dict[str, Any] | None = None
        if mem is not None and hasattr(mem, "router_snapshot"):
            session_state = mem.router_snapshot(
                active_task_id=req.active_task_id,
                queue_message=bool(req.queue_message),
            )

        decision = await resolve_intent(
            req.message,
            last_intent=(mem.last_intent if mem else None) or req.last_intent,
            enabled=settings.decision_intent_enabled,
            model=settings.decision_model,
            api_key=settings.resolved_llm_api_key or "",
            min_confidence=settings.decision_min_confidence,
            allow_rules_fallback=settings.decision_allow_rules_fallback,
            workspace_id=settings.decision_workspace_id or "",
            region=settings.decision_region,
            base_url=settings.decision_base_url or "",
            session_state=session_state,
            chat_base_url=settings.llm_base_url,
            chat_model=settings.llm_model,
            history=(mem.working[:-1] if mem and getattr(mem, "working", None) else None),
        )
        intent = str(decision.intent or "").upper()
        pipeline = "ops_marketing" if intent in _MARKETING else "other"
        return AgentResult(
            agent_name=self.name,
            success=True,
            confidence=float(getattr(decision, "confidence", 0.7) or 0.7),
            data={
                "intent": intent,
                "pipeline": pipeline,
                "confidence": getattr(decision, "confidence", 0.7),
                "source": getattr(decision, "source", "decision"),
                "window_days": getattr(decision, "window_days", None),
                "session_phase": (session_state or {}).get("phase"),
                "router_hint": format_router_state(session_state) if session_state else "",
            },
            source=str(getattr(decision, "source", "decision")),
        )
