from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.config.dependencies import get_asset_service, get_current_user
from src.model.user import User
from src.response.asset_response import AssetListResponse
from src.services.asset_service import AssetService


router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.get("", response_model=AssetListResponse)
def list_assets(
    current_user: Annotated[User, Depends(get_current_user)],
    asset_service: Annotated[AssetService, Depends(get_asset_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    search: str | None = Query(default=None),
) -> AssetListResponse:
    return asset_service.list_assets(skip=skip, limit=limit, search=search)
