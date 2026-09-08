from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.config.dependencies import get_ai_analysis_history_service, get_current_user
from src.model.user import User
from src.response.ai_analysis_history_response import (
    AiAnalysisHistoryItemResponse,
    AiAnalysisHistoryListResponse,
)
from src.services.ai_analysis_history_service import AiAnalysisHistoryService


router = APIRouter(prefix="/api/v1/ai", tags=["ai-analysis-history"])
portfolio_router = APIRouter(
    prefix="/api/v1/portfolios/{portfolio_id}/ai",
    tags=["ai-analysis-history"],
)


@router.get("/analyses", response_model=AiAnalysisHistoryListResponse)
def list_ai_analyses(
    current_user: Annotated[User, Depends(get_current_user)],
    ai_analysis_history_service: Annotated[
        AiAnalysisHistoryService,
        Depends(get_ai_analysis_history_service),
    ],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AiAnalysisHistoryListResponse:
    return ai_analysis_history_service.list_current_user_analyses(
        current_user=current_user,
        skip=skip,
        limit=limit,
    )


@router.get("/analyses/{analysis_id}", response_model=AiAnalysisHistoryItemResponse)
def get_ai_analysis(
    analysis_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    ai_analysis_history_service: Annotated[
        AiAnalysisHistoryService,
        Depends(get_ai_analysis_history_service),
    ],
) -> AiAnalysisHistoryItemResponse:
    return ai_analysis_history_service.get_current_user_analysis_detail(
        analysis_id=analysis_id,
        current_user=current_user,
    )


@portfolio_router.get("/analyses", response_model=AiAnalysisHistoryListResponse)
def list_portfolio_ai_analyses(
    portfolio_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    ai_analysis_history_service: Annotated[
        AiAnalysisHistoryService,
        Depends(get_ai_analysis_history_service),
    ],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> AiAnalysisHistoryListResponse:
    return ai_analysis_history_service.list_owned_portfolio_analyses(
        portfolio_id=portfolio_id,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )