"""Quality LangGraph：load → rule_check → explain → upsert。"""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from agents.quality import nodes as N
from agents.quality.state import QualityState
from harness.checkpoint import get_checkpointer


def _after_load(state: QualityState) -> Literal["rule_check", "end_fail"]:
    if state.get("status") == "FAILED_NO_FEATURES":
        return "end_fail"
    return "rule_check"


def build_quality_graph() -> Any:
    g: StateGraph = StateGraph(QualityState)
    g.add_node("load", N.node_load)
    g.add_node("rule_check", N.node_rule_check)
    g.add_node("explain", N.node_explain)
    g.add_node("upsert", N.node_upsert)
    g.add_node("end_fail", lambda s: s)

    g.add_edge(START, "load")
    g.add_conditional_edges(
        "load", _after_load, {"rule_check": "rule_check", "end_fail": "end_fail"}
    )
    g.add_edge("end_fail", END)
    g.add_edge("rule_check", "explain")
    g.add_edge("explain", "upsert")
    g.add_edge("upsert", END)
    return g.compile(checkpointer=get_checkpointer())


_APP: Any = None


def get_quality_app() -> Any:
    global _APP
    if _APP is None:
        _APP = build_quality_graph()
    return _APP

