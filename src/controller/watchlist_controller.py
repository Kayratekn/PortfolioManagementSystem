from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from src.config.dependencies import get_current_user, get_watchlist_service
from src.model.user import User
from src.request.watchlist_request import WatchlistCreateRequest
from src.response.watchlist_response import WatchlistItemResponse, WatchlistResponse
from src.services.watchlist_service import WatchlistService


router = APIRouter(prefix="/api/v1/watchlist", tags=["watchlist"])


@router.post("", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
def create_watchlist_item(
    payload: WatchlistCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    watchlist_service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> WatchlistItemResponse:
    return watchlist_service.create_item(asset_id=payload.asset_id, current_user=current_user)


@router.get("", response_model=WatchlistResponse)
def list_watchlist_items(
    current_user: Annotated[User, Depends(get_current_user)],
    watchlist_service: Annotated[WatchlistService, Depends(get_watchlist_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> WatchlistResponse:
    return watchlist_service.list_items(current_user=current_user, skip=skip, limit=limit)


@router.delete("/{watchlist_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist_item(
    watchlist_item_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    watchlist_service: Annotated[WatchlistService, Depends(get_watchlist_service)],
) -> Response:
    watchlist_service.delete_item(watchlist_item_id=watchlist_item_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
