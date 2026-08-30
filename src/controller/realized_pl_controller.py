from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_current_user, get_realized_pl_service
from src.model.user import User
from src.response.realized_pl_response import RealizedPlResponse
from src.services.realized_pl_service import RealizedPlService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/realized-pl",
    tags=["realized-pl"],
)


@router.get("", response_model=RealizedPlResponse)
def get_realized_pl(
    portfolio_id: int,
    as_of_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    realized_pl_service: Annotated[
        RealizedPlService,
        Depends(get_realized_pl_service),
    ],
) -> RealizedPlResponse:
    result = realized_pl_service.get_realized_pl(
        portfolio_id=portfolio_id,
        current_user=current_user,
        as_of_date=as_of_date,
    )
    return RealizedPlResponse.model_validate(result)
