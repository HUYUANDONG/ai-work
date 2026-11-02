"""任务领取 / 完成 DTO。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ClaimTaskRequest(BaseModel):
    """Worker 领任务请求。"""

    task_types: list[str]
    workflow_version: str
    worker_id: str = "py-worker"


class ClaimedTask(BaseModel):
    """领取到的任务载荷。"""

    task_id: str
    run_id: str
    task_type: Literal["EXPLOSION", "QUALITY"]
    lease_token: str
    lease_seconds: int = 60
    conversation_id: str | None = None
    user_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)


class CompleteTaskRequest(BaseModel):
    """任务成功完成。"""

    lease_token: str
    summary: str = ""
    result_meta: dict[str, Any] = Field(default_factory=dict)


class FailTaskRequest(BaseModel):
    """任务失败。"""

    lease_token: str
    error_code: str
    message: str

