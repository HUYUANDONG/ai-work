"""会话路由状态机与决策短上下文。"""

from __future__ import annotations

import unittest

from harness.memory.dialog_state import (
    PHASE_AWAITING_ADVISE,
    PHASE_AWAITING_CLARIFY,
    PHASE_AWAITING_COPY,
    PHASE_IDLE,
    build_router_snapshot,
    format_router_state,
)
from harness.memory.rails import SessionMemory


class DialogStateTest(unittest.TestCase):
    """显式相位优先于长 history。"""

    def test_phase_priority(self) -> None:
        self.assertEqual(
            build_router_snapshot(advice_offer_pending=True)["phase"],
            PHASE_AWAITING_ADVISE,
        )
        self.assertEqual(
            build_router_snapshot(
                advice_offer_pending=True,
                active_task_id="t1",
            )["phase"],
            PHASE_AWAITING_ADVISE,
        )
        self.assertEqual(
            build_router_snapshot(awaiting_clarify=True)["phase"],
            PHASE_AWAITING_CLARIFY,
        )
        self.assertEqual(build_router_snapshot()["phase"], PHASE_IDLE)

    def test_format_includes_advise_hint(self) -> None:
        snap = build_router_snapshot(
            last_intent="EXPLOSION",
            last_task_input={
                "time_window_days": 7,
                "goal_mode": "GMV",
                "focus_slots": 5,
                "include_advise": False,
                "noise": "drop-me",
            },
            advice_offer_pending=True,
        )
        text = format_router_state(snap)
        self.assertIn("AWAITING_ADVISE_CONFIRM", text)
        self.assertIn("time_window_days=7", text)
        self.assertNotIn("noise", text)
        self.assertIn("placement advise", text)

    def test_memory_router_snapshot(self) -> None:
        mem = SessionMemory(conversation_id="c1")
        mem.last_intent = "EXPLOSION"
        mem.advice_offer_pending = True
        mem.last_task_input = {"time_window_days": 7, "goal_mode": "GMV"}
        snap = mem.router_snapshot()
        self.assertEqual(snap["phase"], PHASE_AWAITING_ADVISE)
        self.assertEqual(snap["last_intent"], "EXPLOSION")

    def test_ops_phase_copy_gate(self) -> None:
        snap = build_router_snapshot(ops_phase=PHASE_AWAITING_COPY)
        self.assertEqual(snap["phase"], PHASE_AWAITING_COPY)
        self.assertTrue(snap["flags"]["awaiting_copy"])
        text = format_router_state(snap)
        self.assertIn("AWAITING_COPY_CONFIRM", text)
        self.assertIn("marketing copy", text)


if __name__ == "__main__":
    unittest.main()
