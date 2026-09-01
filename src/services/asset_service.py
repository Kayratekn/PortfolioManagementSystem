from __future__ import annotations

from src.repositories.asset_repository import AssetRepository
from src.response.asset_response import AssetListResponse, AssetResponse


class AssetService:
    def __init__(self, asset_repository: AssetRepository) -> None:
        self.asset_repository = asset_repository

    def list_assets(
        self,
        *,
        skip: int,
        limit: int,
        search: str | None = None,
    ) -> AssetListResponse:
        assets = self.asset_repository.list_active_catalog(
            skip=skip,
            limit=limit,
            search=search,
        )
        total = self.asset_repository.count_active_catalog(search=search)
        return AssetListResponse(
            items=[AssetResponse.model_validate(asset) for asset in assets],
            total=total,
            skip=skip,
            limit=limit,
        )
