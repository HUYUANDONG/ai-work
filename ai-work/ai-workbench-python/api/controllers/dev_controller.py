"""本地联调：质检、单品深挖、下载已有报表。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.deps import (
    get_explosion_service,
    get_quality_service,
    get_runtime,
    get_sku_deep_service,
)
from harness.runtime import AppRuntime
from services.explosion_service import ExplosionService
from services.quality_service import QualityService
from services.sku_deep_service import SkuDeepService

router = APIRouter(prefix="/internal/dev", tags=["dev"])


@router.post("/run-quality")
async def run_quality(
    body: dict[str, Any],
    quality_service: QualityService = Depends(get_quality_service),
) -> dict[str, Any]:
    """跑质检流水线。"""
    return await quality_service.run_pipeline(body)


@router.post("/sku-deep")
async def sku_deep(
    body: dict[str, Any],
    sku_deep_service: SkuDeepService = Depends(get_sku_deep_service),
) -> dict[str, Any]:
    """单品深挖（同步）。"""
    return await sku_deep_service.analyze(body)


@router.get("/reports/{task_id}")
async def download_report(
    task_id: str,
    explosion_service: ExplosionService = Depends(get_explosion_service),
) -> FileResponse:
    """下载已生成的 HTML 分析报表。"""
    path = explosion_service.resolve_report_file(task_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"report not found: {task_id}")
    return FileResponse(
        path=path,
        media_type="text/html; charset=utf-8",
        filename=f"explosion-report-{task_id}.html",
    )


@router.get("/thinking/{task_id}")
async def get_thinking(
    task_id: str,
    runtime: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    """mock：查看已推送的思考事件（正式由 Java SSE 推前端）。"""
    if not runtime.java_client.mock_features:
        raise HTTPException(status_code=400, detail="mock only")
    return {
        "task_id": task_id,
        "events": runtime.java_client.get_mock_progress(task_id),
    }


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    body: dict[str, Any] | None = None,
    runtime: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    """mock：请求取消。"""
    if not runtime.java_client.mock_features:
        raise HTTPException(status_code=400, detail="mock only")
    reason = (body or {}).get("reason") or "用户取消"
    runtime.java_client.mock_request_cancel(task_id, reason)
    return {"ok": True, "task_id": task_id, "control": "cancel"}


@router.post("/tasks/{task_id}/pause")
async def pause_task(
    task_id: str,
    body: dict[str, Any] | None = None,
    runtime: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    """mock：请求暂停。"""
    if not runtime.java_client.mock_features:
        raise HTTPException(status_code=400, detail="mock only")
    reason = (body or {}).get("reason") or "用户暂停"
    runtime.java_client.mock_request_pause(task_id, reason)
    return {"ok": True, "task_id": task_id, "control": "pause"}

