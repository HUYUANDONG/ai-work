"""报告 upsert / 会话报告 DTO。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ExplosionReportPayload(BaseModel):
    """爆品报告整包。"""

    header: dict[str, Any]
    items: list[dict[str, Any]] = Field(default_factory=list)


class QualityReportPayload(BaseModel):
    """质检报告整包。"""

    header: dict[str, Any]
    items: list[dict[str, Any]] = Field(default_factory=list)


class ConversationReportItem(BaseModel):
    """会话内一份报告摘要。"""

    task_id: str
    task_type: Literal["EXPLOSION", "QUALITY"]
    created_at: str | None = None
    header: dict[str, Any] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)


class ConversationReportsResponse(BaseModel):
    """本会话最近报告。"""

    conversation_id: str
    reports: list[ConversationReportItem] = Field(default_factory=list)

