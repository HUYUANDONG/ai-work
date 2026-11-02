"""DTO / Pydantic 模型。"""

from schemas.chat import ChatRequest, ChatResponse, NeedTask
from schemas.features import FeaturesQueryRequest, FeaturesQueryResponse, ProductFeaturesResponse
from schemas.reports import ConversationReportsResponse, ExplosionReportPayload, QualityReportPayload
from schemas.tasks import ClaimedTask, ClaimTaskRequest, CompleteTaskRequest, FailTaskRequest

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "NeedTask",
    "FeaturesQueryRequest",
    "FeaturesQueryResponse",
    "ProductFeaturesResponse",
    "ExplosionReportPayload",
    "QualityReportPayload",
    "ConversationReportsResponse",
    "ClaimTaskRequest",
    "ClaimedTask",
    "CompleteTaskRequest",
    "FailTaskRequest",
]

