from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_current_user, get_portfolio_performance_service
from src.model.user import User
from src.response.portfolio_performance_response import PortfolioPerformanceResponse
from src.services.portfolio_performance_service import PortfolioPerformanceService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/performance",
    tags=["portfolio-performance"],
)


@router.get("", response_model=PortfolioPerformanceResponse)
def get_portfolio_performance(
    portfolio_id: int,
    start_date: date,
    end_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    portfolio_performance_service: Annotated[
        PortfolioPerformanceService,
        Depends(get_portfolio_performance_service),
    ],
) -> PortfolioPerformanceResponse:
    result = portfolio_performance_service.get_performance(
        portfolio_id=portfolio_id,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
    )
    return PortfolioPerformanceResponse.model_validate(result)