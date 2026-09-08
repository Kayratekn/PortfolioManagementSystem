from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError

from src.integrations.ai_client import (
    AiClient,
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)
from src.model.user import User
from src.repositories.sentiment_post_repository import SentimentPostRepository
from src.response.ai_sentiment_response import (
    AiSentimentAiResult,
    AiSentimentResponse,
)
from src.services.ai_analysis_persistence_service import AiAnalysisPersistenceService


AI_SENTIMENT_ENDPOINT = "/api/ai/sentiment"
SENTIMENT_LOOKBACK = timedelta(hours=72)


class AiSentimentService:
    def __init__(
        self,
        *,
        sentiment_post_repository: SentimentPostRepository,
        ai_client: AiClient,
        persistence_service: AiAnalysisPersistenceService,
        now_utc: Callable[[], datetime] | None = None,
    ) -> None:
        self.sentiment_post_repository = sentiment_post_repository
        self.ai_client = ai_client
        self.persistence_service = persistence_service
        self.now_utc = now_utc or self._default_now_utc

    def analyze_sentiment(self, *, current_user: User) -> AiSentimentResponse:
        published_since = self.now_utc() - SENTIMENT_LOOKBACK
        posts = self.sentiment_post_repository.list_for_user_enabled_social_posts_since(
            user_id=current_user.id,
            published_since=published_since,
        )
        if not posts:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="No eligible sentiment posts available.",
            )

        texts = [post.content for post in posts]
        ai_result = self._validate_ai_response(self._call_ai_service({"texts": texts}))
        self._validate_detail_texts(ai_result=ai_result, submitted_texts=texts)

        serialized_result = ai_result.model_dump(mode="json")
        analysis = self.persistence_service.persist_analysis(
            user_id=current_user.id,
            portfolio_id=None,
            analysis_type="sentiment",
            result_payload={
                "overall_score": serialized_result["overall_score"],
                "overall_label": serialized_result["overall_label"],
            },
            explanation_text=None,
            disclaimer=None,
            model_version=ai_result.model_version,
            formula_version=None,
        )
        return AiSentimentResponse(
            analysis_id=analysis.id,
            overall_score=ai_result.overall_score,
            overall_label=ai_result.overall_label,
            model_version=ai_result.model_version,
            formula_version=None,
        )

    def _call_ai_service(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            return self.ai_client.post_json(AI_SENTIMENT_ENDPOINT, payload)
        except AiServiceUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI service temporarily unavailable.",
            ) from exc
        except AiServiceRequestError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service rejected the backend request.",
            ) from exc
        except AiServiceResponseError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid response.",
            ) from exc

    @staticmethod
    def _validate_ai_response(response: dict[str, Any]) -> AiSentimentAiResult:
        try:
            return AiSentimentAiResult.model_validate(response)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid response.",
            ) from exc

    @staticmethod
    def _validate_detail_texts(
        *,
        ai_result: AiSentimentAiResult,
        submitted_texts: list[str],
    ) -> None:
        submitted_text_set = set(submitted_texts)
        if any(detail.text not in submitted_text_set for detail in ai_result.details):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI service returned an invalid response.",
            )

    @staticmethod
    def _default_now_utc() -> datetime:
        return datetime.now(timezone.utc)