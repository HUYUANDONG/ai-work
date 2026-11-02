"""
进度感知熔断：有实质进展则重置计数；连续无进展才放弃。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ProgressBreaker:
    """
    通用熔断器。

    Attributes:
        max_idle: 连续无进展次数上限。
        idle: 当前连续空转次数。
        last_fingerprint: 上次进展指纹。
        history: 可选审计。
    """

    max_idle: int = 3
    idle: int = 0
    last_fingerprint: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def observe(self, fingerprint: str, *, label: str = "") -> str:
        """
        观察一步。

        Returns:
            str: CONTINUE | RESET_IDLE | TRIPPED。
        """
        fp = fingerprint or ""
        if fp and fp != self.last_fingerprint:
            self.last_fingerprint = fp
            self.idle = 0
            self.history.append({"label": label, "event": "progress", "fp": fp})
            return "RESET_IDLE"

        self.idle += 1
        self.history.append({"label": label, "event": "idle", "idle": self.idle})
        if self.idle >= self.max_idle:
            return "TRIPPED"
        return "CONTINUE"

    @property
    def tripped(self) -> bool:
        return self.idle >= self.max_idle
