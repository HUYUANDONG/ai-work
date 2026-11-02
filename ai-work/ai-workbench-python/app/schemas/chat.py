"""兼容旧导入：请改用 ``schemas.chat``。"""

from schemas.chat import ChatRequest, ChatResponse, Intent, NeedTask

__all__ = ["ChatRequest", "ChatResponse", "Intent", "NeedTask"]
