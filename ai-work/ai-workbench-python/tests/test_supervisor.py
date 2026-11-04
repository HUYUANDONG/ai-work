"""WorkbenchSupervisor：叶子注册与质检解释 Phase。"""

from __future__ import annotations

import unittest

from agents.supervisor import WorkbenchSupervisor


class WorkbenchSupervisorTest(unittest.IsolatedAsyncioTestCase):
    def test_registers_leaves(self) -> None:
        sup = WorkbenchSupervisor.create(llm=None)
        for name in ("explosion", "advise", "quality_explain", "sku_deep", "followup"):
            self.assertTrue(sup.has_agent(name), name)
        for name in ("signal", "risk", "strategy"):
            self.assertFalse(sup.has_agent(name), name)

    async def test_explosion_template_and_quality_explain(self) -> None:
        candidates = [
            {
                "sku_id": "A",
                "title": "热销",
                "explosion_score": 80,
                "quality_risk_level": "NONE",
                "quality_rule_ids": [],
                "rank": 1,
            }
        ]
        sup = WorkbenchSupervisor.create(llm=None)
        exploded = await sup.run_explosion(
            candidates=candidates, focus_slots=1, goal_mode="GMV"
        )
        self.assertTrue(exploded.success)
        out = list((exploded.data or {}).get("candidates") or [])
        self.assertTrue(out[0].get("in_focus_slot"))
        self.assertIn(out[0].get("action_bucket"), {"PUSH", "FIX_THEN_PUSH", "WATCH"})

        rows = [
            {
                "sku_id": "A",
                "risk_level": "HIGH",
                "explosion_score": 80,
                "issues": [{"rule_id": "STOCK_LOW"}],
            }
        ]
        explained = await sup.phase_quality_explain(rows)
        self.assertIn("A", explained["comments"])
        self.assertEqual(explained["explain_source"], "template")


if __name__ == "__main__":
    unittest.main()
