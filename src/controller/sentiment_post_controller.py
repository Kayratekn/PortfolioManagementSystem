from typing import Annotated

from fastapi import APIRouter, Depends, Query

from src.config.dependencies import get_current_user, get_sentiment_post_service
from src.model.user import User
from src.response.expert_source_response import SentimentPostListResponse
from src.services.sentiment_post_service import SentimentPostService

router = APIRouter(prefix="/api/v1/sentiment", tags=["sentiment"])


@router.get("/posts", response_model=SentimentPostListResponse)
def list_sentiment_posts(current_user: Annotated[User, Depends(get_current_user)], service: Annotated[SentimentPostService, Depends(get_sentiment_post_service)], skip: int = Query(default=0, ge=0), limit: int = Query(default=50, ge=1, le=100)) -> SentimentPostListResponse:
    return service.list_feed(current_user=current_user, skip=skip, limit=limit)