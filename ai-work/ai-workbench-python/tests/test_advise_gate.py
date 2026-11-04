"""方案 B：建议门闩与 include_advise。"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from agents.chat.intent import (
    ADVICE_OFFER_QUESTION,
    build_explosion_input,
    is_advise_affirm,
    is_advise_decline,
    wants_explosion_advise,
)
from agents.advise.llm import write_placement_advise
from agents.explosion.lg_graph import _after_explosion


class AdviseGateTest(unittest.TestCase):
    """关键词与图路由。"""

    def test_wants_advise_keywords(self) -> None:
        self.assertTrue(wants_explosion_advise("近7天爆品并给建议"))
        self.assertTrue(wants_explosion_advise("筛爆品怎么投"))
        self.assertFalse(wants_explosion_advise("近7天爆品"))

    def test_build_input_include_advise(self) -> None:
        yes = build_explosion_input("近7天爆品给投放建议")
        no = build_explosion_input("近7天爆品")
        self.assertTrue(yes["include_advise"])
        self.assertFalse(no["include_advise"])
        self.assertEqual(yes["time_window_days"], 7)

    def test_affirm_decline(self) -> None:
        self.assertTrue(is_advise_affirm("要"))
        self.assertTrue(is_advise_affirm("需要"))
        self.assertTrue(is_advise_decline("不用"))
        self.assertFalse(is_advise_affirm("质检一下"))
        self.assertIn("投放建议", ADVICE_OFFER_QUESTION)

    def test_graph_routes_by_include_advise(self) -> None:
        self.assertEqual(
            _after_explosion({"task_input": {"include_advise": False}}),
            "report",
        )
        self.assertEqual(
            _after_explosion({"task_input": {"include_advise": True}}),
            "advise",
        )

    def test_write_placement_falls_back_without_llm(self) -> None:
        async def _run() -> dict[str, Any]:
            return await write_placement_advise(
                candidates=[
                    {
                        "sku_id": "1",
                        "title": "鞋",
                        "explosion_score": 88,
                        "in_focus_slot": True,
                        "metrics": {"gmv_30d": 100, "orders_30d": 2, "clicks_30d": 40},
                    }
                ],
                advise_context={
                    "source": "dailyPlateList",
                    "plates": [
                        {
                            "stat_field_name": "首页",
                            "self_uv": 100,
                            "order_sales": 50,
                            "order_numbers": 1,
                        }
                    ],
                },
                llm=None,
            )

        out = asyncio.run(_run())
        self.assertEqual(out["source"], "template")
        self.assertIn("首页", out["text"])

    def test_write_placement_llm_failure_falls_back(self) -> None:
        llm = MagicMock()
        llm.enabled = True

        async def _boom(**_kwargs):
            raise RuntimeError("timeout")
            yield  # pragma: no cover — make it an async generator type for typing

        async def _fail_stream(**_kwargs):
            raise RuntimeError("timeout")
            if False:  # pragma: no cover
                yield ""

        llm.chat_stream = _fail_stream
        llm.chat = AsyncMock(side_effect=RuntimeError("timeout"))

        async def _run() -> dict[str, Any]:
            return await write_placement_advise(
                candidates=[{"sku_id": "1", "title": "A", "in_focus_slot": True}],
                advise_context={
                    "source": "dailyPlateList",
                    "plates": [{"stat_field_name": "频道A", "self_uv": 9}],
                },
                llm=llm,
            )

        out = asyncio.run(_run())
        self.assertEqual(out["source"], "template_fallback")
        self.assertIn("频道A", out["text"])

    def test_write_placement_llm_stream(self) -> None:
        llm = MagicMock()
        llm.enabled = True

        async def _stream(**_kwargs):
            for part in ("思考", "过程", "投放建议：首页"):
                yield part

        llm.chat_stream = _stream
        deltas: list[str] = []

        async def _on_delta(text: str) -> None:
            deltas.append(text)

        async def _run() -> dict[str, Any]:
            return await write_placement_advise(
                candidates=[{"sku_id": "1", "title": "A", "in_focus_slot": True}],
                advise_context={"source": "dailyPlateList", "plates": []},
                llm=llm,
                on_delta=_on_delta,
            )

        out = asyncio.run(_run())
        self.assertEqual(out["source"], "llm_stream")
        self.assertIn("投放建议", out["text"])
        self.assertEqual("".join(deltas), out["text"])


if __name__ == "__main__":
    unittest.main()
