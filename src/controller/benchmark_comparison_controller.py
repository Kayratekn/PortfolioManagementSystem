from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.config.dependencies import get_benchmark_comparison_service, get_current_user
from src.model.user import User
from src.response.benchmark_comparison_response import BenchmarkComparisonResponse
from src.services.benchmark_comparison_service import BenchmarkComparisonService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/benchmark-comparison",
    tags=["benchmark-comparison"],
)


@router.get("", response_model=BenchmarkComparisonResponse)
def get_benchmark_comparison(
    portfolio_id: int,
    benchmark_code: Annotated[str, Query(min_length=1)],
    start_date: date,
    end_date: date,
    current_user: Annotated[User, Depends(get_current_user)],
    benchmark_comparison_service: Annotated[
        BenchmarkComparisonService,
        Depends(get_benchmark_comparison_service),
    ],
) -> BenchmarkComparisonResponse:
    result = benchmark_comparison_service.get_comparison(
        portfolio_id=portfolio_id,
        benchmark_code=benchmark_code,
        current_user=current_user,
        start_date=start_date,
        end_date=end_date,
    )
    return BenchmarkComparisonResponse.model_validate(result)