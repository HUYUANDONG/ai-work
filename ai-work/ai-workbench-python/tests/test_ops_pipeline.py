"""运营流水线：OpsSupervisor 状态机 + 代码排序 + 文案合规。"""

from __future__ import annotations

import unittest

from agents.copy.agent import CopyAgent, parse_compliance_result
from agents.recommend.agent import RecommendAgent
from agents.supervisor.ops import (
    PHASE_AWAITING_ADVISE,
    PHASE_AWAITING_COPY,
    PHASE_DONE,
    OpsSupervisor,
)
from harness.memory.rails import SessionMemory
from harness.runtime import AppRuntime
from schemas.chat import ChatRequest


def _runtime() -> AppRuntime:
    rt = AppRuntime.create()
    rt.java_client.mock_features = True
    rt.settings.decision_intent_enabled = False
    rt.settings.decision_allow_rules_fallback = True
    return rt


class RecommendScoringTest(unittest.IsolatedAsyncioTestCase):
    async def test_rank_uses_scoring_rules_not_llm(self) -> None:
        items = [
            {
                "sku_id": "S1",
                "title": "热销A",
                "on_sale": True,
                "gmv_30d": 50000,
                "gmv_prev_30d": 20000,
                "clicks_30d": 8000,
                "orders_30d": 400,
            },
            {
                "sku_id": "S2",
                "title": "冷门B",
                "on_sale": True,
                "gmv_30d": 100,
                "clicks_30d": 50,
                "orders_30d": 2,
            },
        ]
        res = await RecommendAgent().run(items=items, top_n=5, focus_slots=1)
        self.assertEqual(res.source, "scoring_rules")
        cands = res.data["candidates"]
        self.assertGreaterEqual(len(cands), 1)
        self.assertEqual(cands[0]["sku_id"], "S1")
        self.assertTrue(cands[0]["in_focus_slot"])


class CopyComplianceTest(unittest.IsolatedAsyncioTestCase):
    def test_parse_compliance_json(self) -> None:
        parsed = parse_compliance_result(
            '{"compliant": false, "issues": ["含绝对化"], "revised_copy": "口碑好物现货可冲"}',
            draft="最好的第一名",
        )
        self.assertFalse(parsed["compliant"])
        self.assertEqual(parsed["revised_copy"], "口碑好物现货可冲")
        self.assertIn("含绝对化", parsed["issues"])

    def test_parse_compliance_fallback(self) -> None:
        parsed = parse_compliance_result("not-json", draft="原稿")
        self.assertEqual(parsed["revised_copy"], "原稿")
        self.assertIn("compliance_parse_failed", parsed["issues"])

    async def test_template_when_no_llm(self) -> None:
        res = await CopyAgent().run(
            bundles=[
                {
                    "sku_id": "SKU-1",
                    "detail": {"title": "保温杯", "selling_points": ["锁温"]},
                    "reviews": [{"content": "保温不错会回购"}],
                }
            ],
            llm=None,
        )
        self.assertTrue(res.success)
        self.assertEqual(res.source, "template")
        self.assertIn("保温杯", res.data["copies"][0]["copy"])


class OpsSupervisorFlowTest(unittest.IsolatedAsyncioTestCase):
    async def test_registers_ops_and_workbench_leaves(self) -> None:
        sup = OpsSupervisor.create(llm=None)
        for name in (
            "explosion",
            "decision",
            "data_task",
            "recommend",
            "inventory",
            "advise",
            "copy",
            "sku_deep",
            "followup",
        ):
            self.assertTrue(sup.has_agent(name), name)
        for name in ("signal", "risk", "strategy", "analyze"):
            self.assertFalse(sup.has_agent(name), name)

    async def test_marketing_then_advise_then_copy_gates(self) -> None:
        rt = _runtime()
        mem = SessionMemory(conversation_id="ops-1")
        sup = OpsSupervisor.create(llm=None)

        turn1 = await sup.handle_turn(
            runtime=rt,
            req=ChatRequest(
                conversation_id="ops-1",
                user_id="u1",
                message="近7天爆品",
            ),
            mem=mem,
        )
        self.assertEqual(turn1["intent"], "EXPLOSION")
        self.assertEqual(turn1["phase"], PHASE_AWAITING_ADVISE)
        self.assertEqual(mem.ops_phase, PHASE_AWAITING_ADVISE)
        self.assertIn("投放建议", turn1["reply"])
        self.assertIn("爆品解读", turn1["reply"])
        self.assertTrue(mem.ops_context.get("candidates"))
        self.assertTrue(mem.ops_context.get("analysis_text"))

        turn2 = await sup.handle_turn(
            runtime=rt,
            req=ChatRequest(
                conversation_id="ops-1",
                user_id="u1",
                message="要",
            ),
            mem=mem,
        )
        self.assertEqual(turn2["phase"], PHASE_AWAITING_COPY)
        self.assertIn("文案", turn2["reply"])

        turn3 = await sup.handle_turn(
            runtime=rt,
            req=ChatRequest(
                conversation_id="ops-1",
                user_id="u1",
                message="要",
            ),
            mem=mem,
        )
        self.assertEqual(turn3["phase"], PHASE_DONE)
        self.assertIn("合规", turn3["reply"])
        self.assertEqual(mem.ops_phase, PHASE_DONE)

    async def test_decline_advise(self) -> None:
        rt = _runtime()
        mem = SessionMemory(conversation_id="ops-2")
        mem.ops_phase = PHASE_AWAITING_ADVISE
        mem.ops_context = {"candidates": [{"sku_id": "A", "in_focus_slot": True}]}
        mem.advice_offer_pending = True
        sup = OpsSupervisor.create(llm=None)
        out = await sup.handle_turn(
            runtime=rt,
            req=ChatRequest(conversation_id="ops-2", user_id="u1", message="不用"),
            mem=mem,
        )
        self.assertEqual(out["phase"], PHASE_DONE)
        self.assertIn("不写投放建议", out["reply"])


class ChatOpsEntryTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_chat_delegates_to_ops(self) -> None:
        from agents.chat.graph import run_chat

        rt = _runtime()
        data = await run_chat(
            {
                "conversation_id": "chat-ops-1",
                "user_id": "u1",
                "message": "近7天爆品",
            },
            rt,
        )
        self.assertEqual(data["intent"], "EXPLOSION")
        self.assertIn("投放建议", data["reply"])
        self.assertIsNone(data.get("need_task"))
        mem = rt.memory_store.get("chat-ops-1")
        self.assertEqual(mem.ops_phase, PHASE_AWAITING_ADVISE)


if __name__ == "__main__":
    unittest.main()
