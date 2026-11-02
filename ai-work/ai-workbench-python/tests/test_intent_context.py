"""短句补参应继承上一轮筛爆品意图。"""

from __future__ import annotations

import unittest

from agents.chat.decision_intent import (
    IntentDecision,
    _parse_choice_answer,
    _parse_qwen_intent,
    build_systemone_url,
    continue_previous_task,
    overlay_keyword_intent,
    resolve_intent,
)
from agents.chat.intent import (
    build_explosion_input,
    classify_message_rules,
    infer_last_task_intent,
    is_parameter_followup,
    parse_time_window_days,
    resolve_time_window_days,
)
from schemas.chat import ChatRequest


class IntentContextTest(unittest.TestCase):
    """上下文补参。"""

    def test_parse_seven_days(self) -> None:
        self.assertEqual(parse_time_window_days("近7天"), 7)
        self.assertEqual(parse_time_window_days("近7天爆品"), 7)
        self.assertEqual(parse_time_window_days("近七天爆品"), 7)
        self.assertEqual(parse_time_window_days("最近一周"), 7)
        self.assertEqual(parse_time_window_days("近30天"), 30)
        self.assertEqual(resolve_time_window_days("筛爆品", 7), 7)
        self.assertEqual(
            build_explosion_input("近7天爆品")["time_window_days"],
            7,
        )

    def test_parameter_followup(self) -> None:
        self.assertTrue(is_parameter_followup("近7天"))
        self.assertTrue(is_parameter_followup("改成近7天再跑一版"))
        self.assertFalse(is_parameter_followup("质检一下"))

    def test_rules_inherit_explosion(self) -> None:
        self.assertEqual(
            classify_message_rules("近7天", last_intent="EXPLOSION"),
            "EXPLOSION",
        )
        self.assertEqual(classify_message_rules("近7天"), "CLARIFY")

    def test_merge_window_on_base(self) -> None:
        merged = build_explosion_input(
            "近7天",
            {"time_window_days": 30, "goal_mode": "GMV", "focus_slots": 5},
        )
        self.assertEqual(merged["time_window_days"], 7)
        self.assertEqual(merged["goal_mode"], "GMV")

    def test_chat_request_carries_context(self) -> None:
        req = ChatRequest.model_validate(
            {
                "conversation_id": "c-1",
                "user_id": "u-1",
                "message": "近7天",
                "last_intent": "EXPLOSION",
                "last_task_input": {"time_window_days": 30, "goal_mode": "GMV"},
                "history": [
                    {"role": "user", "content": "筛爆品"},
                    {
                        "role": "assistant",
                        "content": "已生成分析任务",
                        "intent": "EXPLOSION",
                    },
                ],
            }
        )
        self.assertEqual(req.last_intent, "EXPLOSION")
        self.assertEqual(req.last_task_input["time_window_days"], 30)
        self.assertEqual(infer_last_task_intent(req.history), "EXPLOSION")
        self.assertEqual(
            classify_message_rules(req.message, last_intent=req.last_intent),
            "EXPLOSION",
        )

    def test_infer_from_assistant(self) -> None:
        history = [
            {"role": "user", "content": "筛爆品"},
            {"role": "assistant", "content": "已生成分析任务请求，目标模式 GMV", "intent": "EXPLOSION"},
        ]
        self.assertEqual(infer_last_task_intent(history), "EXPLOSION")

    def test_overlay_explosion_from_clarify(self) -> None:
        raw = IntentDecision(
            intent="CLARIFY",
            confidence=0.29,
            source="decision_low_confidence",
            window_days=7,
        )
        fixed = overlay_keyword_intent(raw, "近7天爆品", None)
        self.assertEqual(fixed.intent, "EXPLOSION")
        self.assertEqual(fixed.window_days, 7)

    def test_continue_clarify(self) -> None:
        raw = IntentDecision(intent="CLARIFY", confidence=0.2, source="rules_fallback")
        continued = continue_previous_task(raw, "近7天", "EXPLOSION")
        self.assertEqual(continued.intent, "EXPLOSION")

    def test_systemone_url(self) -> None:
        self.assertEqual(
            build_systemone_url(),
            "https://dashscope.aliyuncs.com/compatible-mode/v1/systemone",
        )
        self.assertEqual(
            build_systemone_url(workspace_id="ws-1", region="cn-beijing"),
            "https://ws-1.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/systemone",
        )
        self.assertEqual(
            build_systemone_url(base_url="https://example.com/compatible-mode"),
            "https://example.com/compatible-mode/v1/systemone",
        )

    def test_parse_qwen_intent(self) -> None:
        decision = _parse_qwen_intent(
            '{"intent":"QUALITY","confidence":0.88,"window_days":7}'
        )
        self.assertEqual(decision.intent, "QUALITY")
        self.assertEqual(decision.source, "qwen")
        self.assertEqual(decision.window_days, 7)
        self.assertAlmostEqual(decision.confidence, 0.88)

    def test_parse_choice_answer(self) -> None:
        decision = _parse_choice_answer(
            {
                "answers": {
                    "intent": {
                        "choice": "EXPLOSION",
                        "confidence": 0.91,
                        "probabilities": {"EXPLOSION": 0.91, "CLARIFY": 0.09},
                    },
                    "window": {"choice": "7", "confidence": 0.99},
                }
            }
        )
        self.assertEqual(decision.intent, "EXPLOSION")
        self.assertEqual(decision.source, "decision")
        self.assertEqual(decision.window_days, 7)
        self.assertAlmostEqual(decision.confidence, 0.91)


class DecisionFallbackTest(unittest.IsolatedAsyncioTestCase):
    """无 Key 时走规则降级。"""

    async def test_missing_key_uses_rules(self) -> None:
        decision = await resolve_intent(
            "筛爆品",
            api_key="",
            enabled=True,
            model="decision-model-preview",
            min_confidence=0.75,
            allow_rules_fallback=True,
        )
        self.assertEqual(decision.intent, "EXPLOSION")
        self.assertEqual(decision.source, "rules_fallback")


if __name__ == "__main__":
    unittest.main()
