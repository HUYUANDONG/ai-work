"""
Explosion LangGraph 编排：

load_features → score → signal_risk → strategy → reduce_decide
                              ↑            │
                              └─ REVISE ───┘（条件边；STRATEGY_ONLY 只回 strategy）
                         FINISH → report_upsert → END
"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agents.explosion import nodes as N
from agents.explosion.state import ExplosionState
from harness.checkpoint import get_checkpointer


def _after_load(state: ExplosionState) -> Literal["score", "end_fail"]:
    if state.get("status") == "FAILED_NO_FEATURES" or state.get("next_action") == "abort":
        return "end_fail"
    return "score"


def _after_decide(
    state: ExplosionState,
) -> Literal["signal_risk", "strategy", "report"]:
    action = state.get("next_action") or "finish"
    if action == "signal_risk":
        return "signal_risk"
    if action == "strategy":
        return "strategy"
    return "report"


def build_explosion_graph() -> Any:
    """编译带 Checkpointer 的 Explosion 图。"""
    g: StateGraph = StateGraph(ExplosionState)

    g.add_node("load_features", N.node_load_features)
    g.add_node("score", N.node_score)
    g.add_node("signal_risk", N.node_signal_risk)
    g.add_node("strategy", N.node_strategy)
    g.add_node("reduce_decide", N.node_reduce_decide)
    g.add_node("report_upsert", N.node_report_upsert)
    g.add_node("end_fail", lambda s: s)  # 透传失败状态

    g.add_edge(START, "load_features")
    g.add_conditional_edges(
        "load_features",
        _after_load,
        {"score": "score", "end_fail": "end_fail"},
    )
    g.add_edge("end_fail", END)
    g.add_edge("score", "signal_risk")
    g.add_edge("signal_risk", "strategy")
    g.add_edge("strategy", "reduce_decide")
    g.add_conditional_edges(
        "reduce_decide",
        _after_decide,
        {
            "signal_risk": "signal_risk",
            "strategy": "strategy",
            "report": "report_upsert",
        },
    )
    g.add_edge("report_upsert", END)

    return g.compile(checkpointer=get_checkpointer())


_EXPLOSION_APP: Any = None


def get_explosion_app() -> Any:
    """进程内单例编译图。"""
    global _EXPLOSION_APP
    if _EXPLOSION_APP is None:
        _EXPLOSION_APP = build_explosion_graph()
    return _EXPLOSION_APP

