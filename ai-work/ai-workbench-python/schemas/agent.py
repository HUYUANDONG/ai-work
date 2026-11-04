"""叶子 Agent 统一结果模型（便于 Supervisor / 并行 gather 聚合）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """
    协作叶子 Agent 的标准输出。

    Attributes:
        agent_name: 角色名（如 signal / risk）。
        success: 是否得到可用结果（含规则降级成功）。
        latency_ms: 端到端耗时。
        error: 失败时的错误信息。
        confidence: 可选置信度 0~1。
        data: 业务载荷（如 items / source）。
        source: 结果来源标记（llm / rules / rules_degraded / fallback）。
    """

    agent_name: str
    success: bool = True
    latency_ms: float = 0.0
    error: str = ""
    confidence: float = 0.0
    data: dict[str, Any] = Field(default_factory=dict)
    source: str = ""
