"""
对话 Controller（HTTP 层）。

职责：只接请求、调 Service、返回响应；不写意图、不查特征。

调用链::

    Java POST /internal/chat
      → 本文件 chat()
      → ChatService.handle_message()
      → agents.chat.graph.run_chat()
"""

# APIRouter: 一组路由；Depends: 注入 ChatService
from fastapi import APIRouter, Depends

# 从 app.state.runtime 组装 ChatService
from api.deps import get_chat_service

# 请求/响应 DTO
from schemas.chat import ChatRequest, ChatResponse

# 应用服务：编排对话用例
from services.chat_service import ChatService

# 完整路径：POST /internal/chat
router = APIRouter(prefix="/internal", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    """
    对话入口（供 Java 调用，不是浏览器直连）。

    FastAPI 先把 JSON 校验成 ChatRequest，再注入 ChatService。
    本函数不拉销售额/流量，只转发到 Service。

    Args:
        body: conversation_id / user_id / message。
        chat_service: 由 Depends(get_chat_service) 注入。

    Returns:
        ChatResponse: intent、reply、可选 need_task。
    """
    return await chat_service.handle_message(body)

