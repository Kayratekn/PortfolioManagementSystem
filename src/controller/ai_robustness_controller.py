from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_ai_robustness_service, get_current_user
from src.model.user import User
from src.request.ai_robustness_request import AiRobustnessRequest
from src.response.ai_robustness_response import AiRobustnessResponse
from src.services.ai_robustness_service import AiRobustnessService


router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/ai",
    tags=["ai-robustness"],
)


@router.post("/robustness", response_model=AiRobustnessResponse)
def analyze_robustness(
    portfolio_id: int,
    payload: AiRobustnessRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    ai_robustness_service: Annotated[
        AiRobustnessService,
        Depends(get_ai_robustness_service),
    ],
) -> AiRobustnessResponse:
    return ai_robustness_service.analyze_robustness(
        portfolio_id=portfolio_id,
        current_user=current_user,
        as_of_date=payload.as_of_date,
    )
