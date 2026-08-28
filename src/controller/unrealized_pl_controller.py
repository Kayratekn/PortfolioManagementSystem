from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_current_user, get_unrealized_pl_service
from src.model.user import User
from src.response.unrealized_pl_response import UnrealizedPlResponse
from src.services.unrealized_pl_service import UnrealizedPlService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/unrealized-pl",
    tags=["unrealized-pl"],
)


@router.get("", response_model=UnrealizedPlResponse)
def get_unrealized_pl(
    portfolio_id: int,
    as_of_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    unrealized_pl_service: Annotated[
        UnrealizedPlService,
        Depends(get_unrealized_pl_service),
    ],
) -> UnrealizedPlResponse:
    result = unrealized_pl_service.get_unrealized_pl(
        portfolio_id=portfolio_id,
        current_user=current_user,
        as_of_date=as_of_date,
    )
    return UnrealizedPlResponse.model_validate(result)