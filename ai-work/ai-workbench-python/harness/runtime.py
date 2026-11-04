"""
进程共享依赖（AppRuntime）。

注意：这不是网上常说的「Agent Harness 平台」。
这里只是 settings + JavaClient + LlmClient 等共用依赖盒。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from clients.java_client import JavaClient
from clients.llm_client import LlmClient
from core.config import Settings, get_settings
from harness.memory.rails import MemoryStore
from harness.memory.tokens import TokenBudget

if TYPE_CHECKING:
    from agents.supervisor import OpsSupervisor, WorkbenchSupervisor


@dataclass
class AppRuntime:
    """
    进程内共享运行时依赖。

    Attributes:
        settings: 环境配置。
        java_client: 调用 Workbench 内部 HTTP。
        llm_client: 百炼 OpenAI 兼容聊天（报表叙事）。
        memory_store: 会话分层记忆。
        token_budget: 默认 LLM 输入预算。
        supervisor: 总指挥（本仓全部叶子经此调度）。
    """

    settings: Settings = field(default_factory=get_settings)
    java_client: JavaClient = field(default_factory=JavaClient)
    llm_client: LlmClient | None = None
    memory_store: MemoryStore = field(default_factory=MemoryStore)
    token_budget: TokenBudget = field(default_factory=TokenBudget)
    supervisor: OpsSupervisor | WorkbenchSupervisor | None = None

    @classmethod
    def create(cls, settings: Settings | None = None) -> "AppRuntime":
        """
        工厂方法：用给定或默认 Settings 构建。

        Args:
            settings: 可选配置。

        Returns:
            AppRuntime: 新实例。
        """
        from agents.supervisor.ops import OpsSupervisor

        cfg = settings or get_settings()
        llm = LlmClient(
            base_url=cfg.llm_base_url,
            api_key=cfg.resolved_llm_api_key,
            model=cfg.llm_model,
        )
        budget = TokenBudget(
            context_window=cfg.llm_context_window,
            reserve_output=cfg.llm_reserve_output,
        )
        supervisor = OpsSupervisor.create(
            llm=llm,
            council_llm_enabled=bool(getattr(cfg, "council_llm_enabled", False)),
        )
        return cls(
            settings=cfg,
            java_client=JavaClient(
                base_url=cfg.java_base_url,
                mock_features=cfg.java_mock_features,
            ),
            llm_client=llm,
            memory_store=MemoryStore(),
            token_budget=budget,
            supervisor=supervisor,
        )

    def report_dir(self) -> Path:
        """报表输出目录（相对 cwd 或绝对路径）。"""
        return Path(self.settings.report_output_dir)

