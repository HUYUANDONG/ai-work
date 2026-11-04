"""
Explosion LangGraph：

load_features → score → explosion → (include_advise? advise → report : report)
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


def _after_explosion(
    state: ExplosionState,
) -> Literal["advise", "report"]:
    task_input = state.get("task_input") or {}
    if bool(task_input.get("include_advise")):
        return "advise"
    return "report"


def build_explosion_graph() -> Any:
    """编译带 Checkpointer 的 Explosion 图。"""
    g: StateGraph = StateGraph(ExplosionState)

    g.add_node("load_features", N.node_load_features)
    g.add_node("score", N.node_score)
    g.add_node("explosion", N.node_explosion)
    g.add_node("load_advise_context", N.node_load_advise_context)
    g.add_node("write_advise", N.node_write_advise)
    g.add_node("report_upsert", N.node_report_upsert)
    g.add_node("end_fail", lambda s: s)

    g.add_edge(START, "load_features")
    g.add_conditional_edges(
        "load_features",
        _after_load,
        {"score": "score", "end_fail": "end_fail"},
    )
    g.add_edge("end_fail", END)
    g.add_edge("score", "explosion")
    g.add_conditional_edges(
        "explosion",
        _after_explosion,
        {"advise": "load_advise_context", "report": "report_upsert"},
    )
    g.add_edge("load_advise_context", "write_advise")
    g.add_edge("write_advise", "report_upsert")
    g.add_edge("report_upsert", END)

    return g.compile(checkpointer=get_checkpointer())


_EXPLOSION_APP: Any = None


def get_explosion_app() -> Any:
    """进程内单例编译图。"""
    global _EXPLOSION_APP
    if _EXPLOSION_APP is None:
        _EXPLOSION_APP = build_explosion_graph()
    return _EXPLOSION_APP
