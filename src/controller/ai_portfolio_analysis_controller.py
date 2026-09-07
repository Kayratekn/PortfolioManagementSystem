from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_ai_portfolio_analysis_service, get_current_user
from src.model.user import User
from src.request.ai_portfolio_analysis_request import AiPortfolioAnalysisRequest
from src.response.ai_portfolio_analysis_response import AiPortfolioAnalysisResponse
from src.services.ai_portfolio_analysis_service import AiPortfolioAnalysisService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/ai",
    tags=["ai-portfolio-analysis"],
)


@router.post("/portfolio-analysis", response_model=AiPortfolioAnalysisResponse)
def analyze_portfolio(
    portfolio_id: int,
    payload: AiPortfolioAnalysisRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    ai_portfolio_analysis_service: Annotated[
        AiPortfolioAnalysisService,
        Depends(get_ai_portfolio_analysis_service),
    ],
) -> AiPortfolioAnalysisResponse:
    return ai_portfolio_analysis_service.analyze_portfolio(
        portfolio_id=portfolio_id,
        current_user=current_user,
        as_of_date=payload.as_of_date,
    )