from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_current_user, get_portfolio_valuation_service
from src.model.user import User
from src.response.portfolio_valuation_response import PortfolioValuationResponse
from src.services.portfolio_valuation_service import PortfolioValuationService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/valuation",
    tags=["portfolio-valuation"],
)


@router.get("", response_model=PortfolioValuationResponse)
def get_portfolio_valuation(
    portfolio_id: int,
    valuation_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_valuation_service: Annotated[
        PortfolioValuationService,
        Depends(get_portfolio_valuation_service),
    ],
) -> PortfolioValuationResponse:
    result = portfolio_valuation_service.get_valuation(
        portfolio_id=portfolio_id,
        current_user=current_user,
        valuation_date=valuation_date,
    )
    return PortfolioValuationResponse.model_validate(result)