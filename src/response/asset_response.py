from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    asset_code: str
    asset_name: str
    asset_type: str
    fund_kind: str | None
    isin: str | None
    currency: str | None
    data_source: str


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    skip: int
    limit: int
