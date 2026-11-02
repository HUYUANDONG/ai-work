"""特征查询相关 DTO（与 internal-api-contract 对齐）。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FeaturesQueryRequest(BaseModel):
    """批量特征查询请求。"""

    stat_date: str | None = None
    on_sale_only: bool = True
    category_id: str | None = None
    sku_ids: list[str] | None = None


class FeaturesQueryResponse(BaseModel):
    """批量特征查询响应。"""

    snapshot_date: str | None = None
    row_count: int = 0
    items: list[dict[str, Any]] = Field(default_factory=list)
    mock: bool = False


class ProductFeaturesResponse(BaseModel):
    """单品特征响应。"""

    snapshot_date: str | None = None
    item: dict[str, Any] | None = None
    mock: bool = False

