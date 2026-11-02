"""单品深挖应用服务（dev 联调）。"""

from __future__ import annotations

from typing import Any

from agents.chat.sku_deep import analyze_sku
from harness.runtime import AppRuntime


class SkuDeepService:
    """单品分析用例。"""

    def __init__(self, runtime: AppRuntime) -> None:
        self._runtime = runtime

    async def analyze(self, body: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            body: sku_id 或 message（含 SKU）。

        Returns:
            dict: analyze_sku 结果。
        """
        sku_id = body.get("sku_id")
        message = str(body.get("message") or "")
        if not sku_id:
            from agents.chat.sku_parse import extract_sku_ids

            ids = extract_sku_ids(message)
            if not ids:
                return {"ok": False, "message": "缺少 sku_id"}
            sku_id = ids[0]
        result = await analyze_sku(
            self._runtime, str(sku_id), user_question=message or f"分析 {sku_id}"
        )
        return {"ok": True, **result}

