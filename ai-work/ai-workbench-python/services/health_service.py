"""健康检查应用服务。"""

from __future__ import annotations

from typing import Any

from core.config import Settings, get_settings
from db.session import ping_db


class HealthService:
    """组装 /health 载荷。"""

    def __init__(self, settings: Settings | None = None) -> None:
        """
        Args:
            settings: 可选注入；默认读单例。
        """
        self._settings = settings or get_settings()

    async def check(self) -> tuple[dict[str, Any], int]:
        """
        探测进程与 Checkpoint。

        Returns:
            tuple: (payload, http_status_code)。
        """
        settings = self._settings
        db_ok: bool | None = None
        if settings.checkpoint_database_url:
            db_ok = await ping_db()

        status = "ok"
        if settings.checkpoint_database_url and db_ok is False:
            status = "degraded"

        payload: dict[str, Any] = {
            "status": status,
            "profile": settings.profile,
            "checkpoint_configured": bool(settings.checkpoint_database_url),
            "checkpoint_ok": db_ok,
            "java_mock_features": settings.java_mock_features,
        }
        code = 200 if status == "ok" else 503
        return payload, code
