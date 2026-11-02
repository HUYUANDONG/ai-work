"""
对话应用服务（Service 层）。

Controller 只收 HTTP；本类编排「一轮对话」用例：
调用领域层 agents.chat.graph，并把内部 debug 字段裁掉，只返回对外 DTO。

对应 Nest：ChatService（被 ChatController 注入使用）。
"""

from __future__ import annotations

# agents.chat.graph: 领域图——Jev 意图 + 缺参默认 + 组装 NEED_TASK
from agents.chat.graph import run_chat

# AppRuntime: 进程共享依赖（配置、JavaClient 等）
from harness.runtime import AppRuntime

# schemas.chat: 对外契约；用 model_fields 过滤 debug
from schemas.chat import ChatRequest, ChatResponse


class ChatService:
    """
    对话用例服务。

    一个请求对应一次 handle_message；不在这里写路由装饰器。
    """

    def __init__(self, runtime: AppRuntime) -> None:
        """
        Args:
            runtime: lifespan 里创建、经 deps 注入进来的共享运行时。
        """
        self._runtime = runtime

    async def handle_message(self, body: ChatRequest) -> ChatResponse:
        """
        处理一轮用户消息。

        步骤：
            1. 调 run_chat（可能返回 intent + reply + need_task + debug）
            2. 只保留 ChatResponse 声明过的字段（丢掉 debug）
            3. 再校验成 ChatResponse，保证出站契约稳定

        Args:
            body: 已由 Controller / FastAPI 校验过的请求 DTO。

        Returns:
            ChatResponse: 给 Java / 前端用的结构化结果。
        """
        raw = await run_chat(body, self._runtime)
        public = {k: v for k, v in raw.items() if k in ChatResponse.model_fields}
        return ChatResponse.model_validate(public)

