"""BaseAgent 与 TaskAgent 注册表。"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any

from agents.base import BaseAgent
from agents.explosion.agent import ExplosionAgent
from agents.task_agent import (
    CallableTaskAgent,
    get_task_agent,
    register_task_agent,
    supported_task_types,
)
from schemas.agent import AgentResult


class _Boom(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="boom", timeout=1.0)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        raise RuntimeError("boom")

    def _fallback(
        self, latency_ms: float, exc: BaseException, **kwargs: Any
    ) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=str(exc),
            source="fallback",
            latency_ms=latency_ms,
        )


class _Slow(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="slow", timeout=0.05)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        await asyncio.sleep(1.0)
        return AgentResult(agent_name=self.name, success=True)

    def _fallback(
        self, latency_ms: float, exc: BaseException, **kwargs: Any
    ) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            success=False,
            error=type(exc).__name__,
            source="fallback",
            latency_ms=latency_ms,
        )


class _Ok(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="ok", timeout=1.0)

    async def _execute(self, **kwargs: Any) -> AgentResult:
        return AgentResult(agent_name=self.name, success=True, data={"x": 1})


class BaseAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_success_sets_latency(self) -> None:
        r = await _Ok().run()
        self.assertTrue(r.success)
        self.assertGreaterEqual(r.latency_ms, 0.0)

    async def test_exception_fallback(self) -> None:
        r = await _Boom().run()
        self.assertFalse(r.success)
        self.assertEqual(r.source, "fallback")
        self.assertIn("boom", r.error or "")

    async def test_timeout_fallback(self) -> None:
        r = await _Slow().run()
        self.assertFalse(r.success)
        self.assertEqual(r.error, "TimeoutError")


class ExplosionAgentTest(unittest.IsolatedAsyncioTestCase):
    async def test_rules_focus_without_llm(self) -> None:
        r = await ExplosionAgent().run(
            candidates=[
                {
                    "sku_id": "A",
                    "explosion_score": 80,
                    "quality_risk_level": "NONE",
                    "rank": 1,
                }
            ],
            focus_slots=1,
            llm=None,
        )
        self.assertTrue(r.success)
        self.assertEqual(r.source, "template")
        self.assertTrue(r.data["candidates"][0]["in_focus_slot"])


class TaskRegistryTest(unittest.TestCase):
    def test_builtins_registered(self) -> None:
        known = supported_task_types()
        self.assertIn("EXPLOSION", known)
        self.assertIn("QUALITY", known)

    def test_custom_registration(self) -> None:
        async def _run(ctx, runtime):  # noqa: ANN001
            return {"ok": True}

        register_task_agent(CallableTaskAgent("CUSTOM_X", _run))
        self.assertIsNotNone(get_task_agent("CUSTOM_X"))

    def test_route_unknown(self) -> None:
        self.assertIsNone(get_task_agent("NO_SUCH"))


if __name__ == "__main__":
    unittest.main()
