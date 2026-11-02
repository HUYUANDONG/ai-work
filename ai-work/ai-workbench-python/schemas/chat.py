"""
对话入口请求/响应 DTO（Java → Python）。
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

Intent = Literal[
    "EXPLOSION",
    "QUALITY",
    "SKU_DEEP",
    "FOLLOWUP",
    "META",
    "OUT_OF_SCOPE",
    "CLARIFY",
    "QUEUED",
]


class ChatRequest(BaseModel):
    """
    Java 转发的用户对话请求。

    Attributes:
        conversation_id: 会话 ID。
        user_id: 电商用户 ID。
        message: 本轮用户原文。
        history: 可选最近若干轮。
        last_intent: Java 记下的上一轮任务意图（EXPLOSION/QUALITY）。
        last_task_input: 上一轮任务入参，供短句补参叠加。
        active_task_id: 若本会话有进行中的长任务，Java 带上以便排队/提示。
        queue_message: Java 已把本消息放入追问队列时为 true（Python 只回执，不建新任务）。
    """

    conversation_id: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    history: list[dict[str, Any]] = Field(default_factory=list)
    last_intent: str | None = None
    last_task_input: dict[str, Any] | None = None
    active_task_id: str | None = None
    queue_message: bool = False


class NeedTask(BaseModel):
    """需要 Java 创建的长任务。"""

    task_type: Literal["EXPLOSION", "QUALITY"]
    input: dict[str, Any]


class ChatResponse(BaseModel):
    """
    对话结构化输出。

    Attributes:
        intent: 意图分类。
        reply: 给用户的短文。
        need_task: 非空时由 Java 建 ai_task。
        clarify_pending: 为 true 时禁止 need_task。
        queue_ack: 追问已排队时的回执信息。
        ui_hints: 前端提示（如下载、思考流、取消按钮）。
    """

    intent: Intent
    reply: str
    need_task: NeedTask | None = None
    clarify_pending: bool = False
    queue_ack: dict[str, Any] | None = None
    ui_hints: dict[str, Any] | None = None

