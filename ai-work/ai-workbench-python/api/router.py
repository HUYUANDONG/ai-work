"""汇总所有 Controller 路由（类似 Nest 根 Module 的 imports）。"""

from fastapi import APIRouter

from api.controllers import chat_controller, dev_controller, health_controller

api_router = APIRouter()
api_router.include_router(health_controller.router)
api_router.include_router(chat_controller.router)
api_router.include_router(dev_controller.router)
