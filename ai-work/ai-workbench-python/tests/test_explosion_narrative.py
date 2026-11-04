"""爆品结论正文与会签槽位纠正。"""

from __future__ import annotations

import unittest

from agents.explosion.agent import apply_focus_and_actions
from agents.explosion.narrative import build_operator_report
from harness.memory.slim import slim_candidates_for_llm


class ExplosionNarrativeTest(unittest.TestCase):
    """用户可见回复必须含思考、商品名、趋势。"""

    def test_report_lists_products_and_thinking(self) -> None:
        text = build_operator_report(
            [
                {
                    "sku_id": "SKU-001",
                    "title": "示例爆款A",
                    "explosion_score": 60.78,
                    "quality_risk_level": "NONE",
                    "quality_rule_ids": [],
                    "action_bucket": "WATCH",
                    "in_focus_slot": False,
                    "metrics": {
                        "gmv_30d": 1782,
                        "gmv_prev_30d": 720,
                        "clicks_30d": 2400,
                        "clicks_prev_30d": 1100,
                        "orders_30d": 12,
                        "rate_per": 3.5,
                        "amount_unit": "yuan",
                    },
                    "score_breakdown": {
                        "sales_growth": {"raw_growth": 1.47},
                        "traffic_growth": {"raw_growth": 1.18},
                    },
                },
                {
                    "sku_id": "SKU-002",
                    "title": "高分但缺货B",
                    "explosion_score": 57.54,
                    "quality_risk_level": "HIGH",
                    "quality_rule_ids": ["STOCK_LOW"],
                    "action_bucket": "FIX_THEN_PUSH",
                    "in_focus_slot": True,
                    "primary_action": "先补货再放量",
                    "metrics": {
                        "gmv_30d": 1548,
                        "gmv_prev_30d": 600,
                        "clicks_30d": 1800,
                        "clicks_prev_30d": 900,
                        "orders_30d": 8,
                        "rate_per": 2.1,
                        "amount_unit": "yuan",
                    },
                },
            ],
            goal_mode="GMV",
            slots=5,
            plan={"llm_round": 1, "revision": 0},
            features={
                "snapshot_date": "2026-10-31",
                "source": "fixture",
                "row_count": 5,
            },
            thinking_events=[
                {"title": "正在拉取商品特征…", "detail": "候选池约 5 行", "visible": True},
                {"title": "正在打分并挂质检标签…", "visible": True},
            ],
            task_input={"time_window_days": 7},
        )
        self.assertIn("思考过程", text)
        self.assertIn("对照销量与流量证据", text)
        self.assertIn("窗口销售额", text)
        self.assertIn("页面转化率", text)
        self.assertIn("本周推荐", text)
        self.assertIn("示例爆款A", text)
        self.assertIn("高分但缺货B", text)
        self.assertIn("趋势", text)
        self.assertIn("联调快照", text)

    def test_focus_prefers_score_when_llm_picks_weak(self) -> None:
        candidates = [
            {
                "sku_id": "SKU-001",
                "explosion_score": 60.78,
                "quality_risk_level": "NONE",
            },
            {
                "sku_id": "SKU-003",
                "explosion_score": 48.2,
                "quality_risk_level": "MID",
            },
        ]
        apply_focus_and_actions(
            candidates,
            focus_slots=1,
            focus_sku_ids=["SKU-003"],
            actions=[
                {"sku_id": "SKU-003", "action_bucket": "FIX_THEN_PUSH"},
                {"sku_id": "SKU-001", "action_bucket": "WATCH"},
            ],
        )
        by_sku = {c["sku_id"]: c for c in candidates}
        # 分 < 50 的 FIX_THEN_PUSH（非 HIGH）压成 WATCH，不得进槽
        self.assertEqual(by_sku["SKU-003"]["action_bucket"], "WATCH")
        self.assertFalse(by_sku["SKU-003"]["in_focus_slot"])

    def test_hydrate_uses_order_sales(self) -> None:
        from scoring.pipeline import hydrate_ops_windows

        row = {"goodsId": "1001", "goodsName": "真品", "orderSales": 880, "orderNumbers": 3}
        hydrate_ops_windows(row)
        self.assertEqual(row["sku_id"], "1001")
        self.assertEqual(row["gmv_30d"], 880)
        self.assertEqual(row["orders_30d"], 3)

    def test_slim_keeps_score(self) -> None:
        rows = slim_candidates_for_llm(
            [
                {
                    "sku_id": "SKU-001",
                    "title": "示例爆款A",
                    "rank": 1,
                    "explosion_score": 60.78,
                    "quality_risk_level": "NONE",
                    "metrics": {
                        "gmv_30d": 880,
                        "gmv_prev_30d": 100,
                        "clicks_30d": 20,
                        "amount_unit": "yuan",
                    },
                    "feature_excerpt": {
                        "goodsFirstPic": "https://example.com/a.jpg",
                        "goodsLink": "http://example.com/g",
                        "gmv_30d": 880,
                        "brand": "示例牌",
                    },
                }
            ]
        )
        self.assertEqual(rows[0]["explosion_score"], 60.8)
        self.assertEqual(rows[0]["title"], "示例爆款A")
        self.assertEqual(rows[0].get("gmv_30d"), 880)
        self.assertEqual(rows[0].get("clicks_30d"), 20)
        self.assertNotIn("ops", rows[0])
        self.assertNotIn("goodsFirstPic", rows[0])
        self.assertNotIn("goodsLink", rows[0])

    def test_placement_uses_advise_plates(self) -> None:
        text = build_operator_report(
            [
                {
                    "sku_id": "SKU-001",
                    "title": "示例爆款A",
                    "explosion_score": 80,
                    "in_focus_slot": True,
                    "action_bucket": "PUSH",
                }
            ],
            goal_mode="GMV",
            slots=5,
            plan={"llm_round": 1, "revision": 0},
            features={"source": "goodsStatList"},
            advise_context={
                "source": "dailyPlateList",
                "plates": [
                    {
                        "stat_field_name": "首页爆款位",
                        "self_uv": 480,
                        "order_sales": 3200,
                        "order_numbers": 18,
                    }
                ],
                "store": {"hpage_uv": 8000, "conversion_rate": 1.5},
            },
        )
        self.assertIn("投放建议", text)
        self.assertIn("首页爆款位", text)
        self.assertIn("未验证该品是否已挂", text)

    def test_offer_advise_skips_placement(self) -> None:
        text = build_operator_report(
            [
                {
                    "sku_id": "SKU-001",
                    "title": "示例爆款A",
                    "explosion_score": 80,
                    "in_focus_slot": True,
                    "action_bucket": "PUSH",
                }
            ],
            goal_mode="GMV",
            slots=5,
            plan={"llm_round": 1},
            features={"source": "goodsStatList"},
            offer_advise=True,
            advice_offer_question="需要我结合日板块流量写投放建议吗？回复「要」或「不用」即可。",
            advise_context={
                "plates": [{"stat_field_name": "不应出现", "self_uv": 1}],
            },
        )
        self.assertIn("需要我结合日板块流量写投放建议吗", text)
        self.assertNotIn("不应出现", text)
        self.assertNotIn("**投放建议**", text)

    def test_advise_llm_text_preferred(self) -> None:
        text = build_operator_report(
            [{"sku_id": "1", "title": "A", "explosion_score": 90, "in_focus_slot": True}],
            goal_mode="GMV",
            slots=5,
            plan={},
            advise_llm_text="思考过程：…\n投放建议：优先试投首页。",
            advise_context={"plates": [{"stat_field_name": "模板板块"}]},
        )
        self.assertIn("优先试投首页", text)
        self.assertNotIn("模板板块", text)


if __name__ == "__main__":
    unittest.main()
