from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from src.config.dependencies import get_ai_sentiment_service, get_current_user
from src.model.user import User
from src.response.ai_sentiment_response import AiSentimentResponse
from src.services.ai_sentiment_service import AiSentimentService


router = APIRouter(prefix="/api/v1/ai", tags=["ai-sentiment"])


@router.post("/sentiment", response_model=AiSentimentResponse)
def analyze_sentiment(
    current_user: Annotated[User, Depends(get_current_user)],
    ai_sentiment_service: Annotated[
        AiSentimentService,
        Depends(get_ai_sentiment_service),
    ],
) -> AiSentimentResponse:
    return ai_sentiment_service.analyze_sentiment(current_user=current_user)