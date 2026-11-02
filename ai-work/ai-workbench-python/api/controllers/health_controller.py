"""健康检查 Controller。"""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.deps import get_health_service
from services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    health_service: HealthService = Depends(get_health_service),
) -> JSONResponse:
    """
    运维探活。

    Args:
        health_service: 健康检查服务。

    Returns:
        JSONResponse: status 载荷。
    """
    payload, code = await health_service.check()
    return JSONResponse(content=payload, status_code=code)
