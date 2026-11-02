"""
FastAPI 依赖注入（类似 Nest 的构造注入）。
"""

from fastapi import Request

from harness.runtime import AppRuntime
from services.chat_service import ChatService
from services.explosion_service import ExplosionService
from services.health_service import HealthService
from services.quality_service import QualityService
from services.sku_deep_service import SkuDeepService


def get_runtime(request: Request) -> AppRuntime:
    """从 app.state 取出 lifespan 创建的 AppRuntime。"""
    return request.app.state.runtime


def get_chat_service(request: Request) -> ChatService:
    """注入 ChatService。"""
    return ChatService(get_runtime(request))


def get_explosion_service(request: Request) -> ExplosionService:
    """注入 ExplosionService。"""
    return ExplosionService(get_runtime(request))


def get_quality_service(request: Request) -> QualityService:
    """注入 QualityService。"""
    return QualityService(get_runtime(request))


def get_sku_deep_service(request: Request) -> SkuDeepService:
    """注入 SkuDeepService。"""
    return SkuDeepService(get_runtime(request))


def get_health_service() -> HealthService:
    """注入 HealthService。"""
    return HealthService()

