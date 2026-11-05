"""
叶子 Agent 基类（参考电商 multi-agent 的 BaseAgent 模式）。

职责：计时、可选超时、异常 → 软 ``AgentResult``。
运输层重试/熔断已在 ``LlmClient`` / ``JavaClient``，此处不再叠。
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from schemas.agent import AgentResult

if TYPE_CHECKING:
    from harness.runtime import AppRuntime

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    协作叶子统一入口：``run`` 包一层，子类只实现 ``_execute``。

    Attributes:
        name: 观测用 agent 名。
        timeout: 单次执行超时秒；``None`` 或 ``<=0`` 表示不限制。
        runtime: 可选共享依赖。
    """

    def __init__(
        self,
        name: str,
        *,
        timeout: float | None = 30.0,
        runtime: AppRuntime | None = None,
    ) -> None:
        self.name = name
        self.timeout = timeout
        self.runtime = runtime

    @abstractmethod
    async def _execute(self, **kwargs: Any) -> AgentResult:
        """核心逻辑；子类实现。"""

    async def run(self, **kwargs: Any) -> AgentResult:
        """
        公开入口：计时 + 可选超时 + 失败软降级。

        Returns:
            AgentResult: 成功或 ``_fallback`` 结果，不向外抛业务异常。
        """
        started = time.perf_counter()
        try:
            if self.timeout is not None and self.timeout > 0:
                result = await asyncio.wait_for(
                    self._execute(**kwargs),
                    timeout=self.timeout,
                )
            else:
                result = await self._execute(**kwargs)
            result.agent_name = result.agent_name or self.name
            result.latency_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "agent.success name=%s latency_ms=%.1f source=%s",
                self.name,
                result.latency_ms,
                result.source or "-",
            )
            return result
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            err_text = str(exc).strip() or type(exc).__name__
            logger.error(
                "agent.failed name=%s error=%s",
                self.name,
                err_text,
                exc_info=False,
            )
            return self._fallback(latency_ms, exc, **kwargs)

    def _fallback(
        self,
        latency_ms: float,
        exc: BaseException,
        **kwargs: Any,
    ) -> AgentResult:
        """
        默认软失败；子类可覆盖为规则降级结果。

        Args:
            latency_ms: 已耗时。
            exc: 原始异常。
            **kwargs: 原 ``run`` 参数，供规则兜底使用。
        """
        _ = kwargs
        return AgentResult(
            agent_name=self.name,
            success=False,
            latency_ms=latency_ms,
            error=str(exc) or type(exc).__name__,
            confidence=0.0,
            source="fallback",
        )
