from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_current_user, get_holding_service
from src.model.user import User
from src.response.holding_response import HoldingListResponse
from src.services.holding_service import HoldingService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/holdings",
    tags=["holdings"],
)


@router.get("", response_model=HoldingListResponse)
def list_holdings(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    holding_service: Annotated[HoldingService, Depends(get_holding_service)],
) -> HoldingListResponse:
    return holding_service.list_holdings(
        portfolio_id=portfolio_id,
        current_user=current_user,
    )