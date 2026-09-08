from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.dependencies import get_ai_sentiment_service
from src.integrations.ai_client import (
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)
from src.main import app
from src.model.ai_analysis import AiAnalysis
from src.model.expert_source import ExpertSource
from src.model.sentiment_post import SentimentPost
from src.services.ai_analysis_persistence_service import AiAnalysisPersistenceService
from src.repositories.ai_analysis_repository import AiAnalysisRepository
from src.repositories.sentiment_post_repository import SentimentPostRepository
from src.services.ai_sentiment_service import AiSentimentService


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
URL = "/api/v1/ai/sentiment"
NOW = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)


class FakeAiClient:
    def __init__(self, response: dict[str, Any] | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((endpoint, payload))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def valid_ai_response(**overrides: Any) -> dict[str, Any]:
    response = {
        "overall_score": 0.25,
        "overall_label": "neutral",
        "details": [],
        "model_version": " sentiment-model-v1 ",
        "formula_version": None,
        "internal_prompt": "must not leave the AI boundary",
    }
    response.update(overrides)
    return response


def register_login(client, *, email: str, username: str) -> tuple[dict[str, Any], str]:
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )
    assert registered.status_code == 201
    logged_in = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert logged_in.status_code == 200
    return registered.json(), logged_in.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_source(
    db_session: Session,
    *,
    handle: str,
    source_key: str = "X",
    is_active: bool = True,
) -> ExpertSource:
    source = ExpertSource(
        source_key=source_key,
        author_name=f"{handle} name",
        author_handle=handle,
        profile_url=f"https://example.test/{handle}",
        is_active=is_active,
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


def create_post(
    db_session: Session,
    *,
    source: ExpertSource,
    external_id: str,
    content: str,
    published_at: datetime,
    content_type: str = "SOCIAL",
) -> SentimentPost:
    post = SentimentPost(
        expert_source_id=source.id,
        source_key=source.source_key,
        external_id=external_id,
        url=f"https://example.test/posts/{external_id}",
        title=f"Title {external_id}",
        content=content,
        author_name=source.author_name,
        author_handle=source.author_handle,
        published_at=published_at,
        fetched_at=NOW,
        content_type=content_type,
        language="en",
    )
    db_session.add(post)
    db_session.commit()
    db_session.refresh(post)
    return post


def follow(client, token: str, source_id: int) -> dict[str, Any]:
    response = client.post(
        "/api/v1/user-expert-sources",
        headers=auth_headers(token),
        json={"expert_source_id": source_id},
    )
    assert response.status_code == 201
    return response.json()


def install_service(client, db_session: Session, fake: FakeAiClient) -> None:
    app.dependency_overrides[get_ai_sentiment_service] = lambda: AiSentimentService(
        sentiment_post_repository=SentimentPostRepository(db_session),
        ai_client=fake,
        persistence_service=AiAnalysisPersistenceService(
            db=db_session,
            repository=AiAnalysisRepository(db_session),
        ),
        now_utc=lambda: NOW,
    )


def clear_service_override() -> None:
    app.dependency_overrides.pop(get_ai_sentiment_service, None)


def sentiment_analyses(db_session: Session) -> list[AiAnalysis]:
    return list(
        db_session.scalars(
            select(AiAnalysis)
            .where(AiAnalysis.analysis_type == "sentiment")
            .order_by(AiAnalysis.id.asc())
        )
    )


def test_sentiment_requires_authentication(client) -> None:
    response = client.post(URL)

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_sentiment_uses_only_authorized_recent_x_social_posts_in_deterministic_order(
    client,
    db_session: Session,
) -> None:
    current_user, current_token = register_login(
        client,
        email="sentiment-owner@example.com",
        username="sentiment-owner",
    )
    _foreign_user, foreign_token = register_login(
        client,
        email="sentiment-foreign@example.com",
        username="sentiment-foreign",
    )
    included = create_source(db_session, handle="included")
    disabled = create_source(db_session, handle="disabled")
    inactive = create_source(db_session, handle="inactive")
    non_x = create_source(db_session, handle="non-x", source_key="RSS")
    non_social = create_source(db_session, handle="non-social")
    foreign = create_source(db_session, handle="foreign")

    newest = create_post(
        db_session,
        source=included,
        external_id="newest",
        content="newest content",
        published_at=NOW - timedelta(hours=1),
    )
    same_time_first = create_post(
        db_session,
        source=included,
        external_id="same-first",
        content="same-time first",
        published_at=NOW - timedelta(hours=2),
    )
    same_time_second = create_post(
        db_session,
        source=included,
        external_id="same-second",
        content="same-time second",
        published_at=NOW - timedelta(hours=2),
    )
    duplicate_first = create_post(
        db_session,
        source=included,
        external_id="duplicate-first",
        content="duplicate content",
        published_at=NOW - timedelta(hours=3),
    )
    duplicate_second = create_post(
        db_session,
        source=included,
        external_id="duplicate-second",
        content="duplicate content",
        published_at=NOW - timedelta(hours=4),
    )
    boundary = create_post(
        db_session,
        source=included,
        external_id="boundary",
        content="boundary content",
        published_at=NOW - timedelta(hours=72),
    )
    create_post(
        db_session,
        source=included,
        external_id="too-old",
        content="too old content",
        published_at=NOW - timedelta(hours=72, microseconds=1),
    )
    create_post(
        db_session,
        source=disabled,
        external_id="disabled",
        content="disabled content",
        published_at=NOW - timedelta(hours=1),
    )
    create_post(
        db_session,
        source=inactive,
        external_id="inactive",
        content="inactive content",
        published_at=NOW - timedelta(hours=1),
    )
    create_post(
        db_session,
        source=non_x,
        external_id="non-x",
        content="non x content",
        published_at=NOW - timedelta(hours=1),
    )
    create_post(
        db_session,
        source=non_social,
        external_id="non-social",
        content="non social content",
        published_at=NOW - timedelta(hours=1),
        content_type="RSS",
    )
    create_post(
        db_session,
        source=foreign,
        external_id="foreign",
        content="foreign content",
        published_at=NOW - timedelta(hours=1),
    )

    follow(client, current_token, included.id)
    disabled_relation = follow(client, current_token, disabled.id)
    follow(client, current_token, inactive.id)
    follow(client, current_token, non_x.id)
    follow(client, current_token, non_social.id)
    follow(client, foreign_token, foreign.id)
    disabled_response = client.patch(
        f"/api/v1/user-expert-sources/{disabled_relation['user_expert_source_id']}",
        headers=auth_headers(current_token),
        json={"is_enabled": False},
    )
    assert disabled_response.status_code == 200
    inactive.is_active = False
    db_session.commit()

    expected_texts = [
        newest.content,
        same_time_second.content,
        same_time_first.content,
        duplicate_first.content,
        duplicate_second.content,
        boundary.content,
    ]
    fake = FakeAiClient(
        valid_ai_response(
            details=[
                {
                    "text": newest.content,
                    "label": "positive",
                    "confidence": -3.5,
                }
            ]
        )
    )
    install_service(client, db_session, fake)
    try:
        response = client.post(URL, headers=auth_headers(current_token))
    finally:
        clear_service_override()

    assert response.status_code == 200
    assert response.json()["overall_score"] == "0.25"
    assert len(fake.calls) == 1
    endpoint, payload = fake.calls[0]
    assert endpoint == "/api/ai/sentiment"
    assert payload == {"texts": expected_texts}
    assert payload["texts"].count("duplicate content") == 2
    assert current_user["id"] not in payload.values()


def test_zero_eligible_posts_returns_422_without_ai_or_persistence(client, db_session: Session) -> None:
    _user, token = register_login(
        client,
        email="sentiment-empty@example.com",
        username="sentiment-empty",
    )
    fake = FakeAiClient(valid_ai_response())
    install_service(client, db_session, fake)
    try:
        response = client.post(URL, headers=auth_headers(token))
    finally:
        clear_service_override()

    assert response.status_code == 422
    assert response.json()["detail"] == "No eligible sentiment posts available."
    assert fake.calls == []
    assert sentiment_analyses(db_session) == []


def test_detail_text_with_surrounding_whitespace_is_rejected_without_persistence(
    client,
    db_session: Session,
) -> None:
    _user, token = register_login(
        client,
        email="sentiment-whitespace@example.com",
        username="sentiment-whitespace",
    )
    source = create_source(db_session, handle="whitespace")
    create_post(
        db_session,
        source=source,
        external_id="whitespace",
        content="authorized content",
        published_at=NOW,
    )
    follow(client, token, source.id)
    fake = FakeAiClient(
        valid_ai_response(
            details=[
                {
                    "text": " authorized content ",
                    "label": "positive",
                    "confidence": 0.9,
                }
            ]
        )
    )
    install_service(client, db_session, fake)
    try:
        response = client.post(URL, headers=auth_headers(token))
    finally:
        clear_service_override()

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert sentiment_analyses(db_session) == []
def test_valid_sentiment_response_has_aggregate_only_public_and_persisted_data(
    client,
    db_session: Session,
) -> None:
    user, token = register_login(
        client,
        email="sentiment-valid@example.com",
        username="sentiment-valid",
    )
    source = create_source(db_session, handle="valid")
    post = create_post(
        db_session,
        source=source,
        external_id="valid",
        content="authorized content",
        published_at=NOW,
    )
    follow(client, token, source.id)
    fake = FakeAiClient(
        valid_ai_response(
            details=[
                {
                    "text": post.content,
                    "label": "positive",
                    "confidence": 0.9,
                    "internal_detail": "ignored",
                }
            ]
        )
    )
    install_service(client, db_session, fake)
    try:
        response = client.post(URL, headers=auth_headers(token))
    finally:
        clear_service_override()

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "analysis_id",
        "overall_score",
        "overall_label",
        "model_version",
        "formula_version",
    }
    assert body["overall_score"] == "0.25"
    assert body["overall_label"] == "neutral"
    assert body["model_version"] == "sentiment-model-v1"
    assert body["formula_version"] is None
    assert {"details", "text", "user_id", "post_id", "internal_prompt"}.isdisjoint(body)

    analysis = db_session.get(AiAnalysis, body["analysis_id"])
    assert analysis is not None
    assert analysis.user_id == user["id"]
    assert analysis.portfolio_id is None
    assert analysis.analysis_type == "sentiment"
    assert analysis.result_payload == {
        "overall_score": "0.25",
        "overall_label": "neutral",
    }
    assert analysis.explanation_text is None
    assert analysis.disclaimer is None
    assert analysis.model_version == "sentiment-model-v1"
    assert analysis.formula_version is None
    assert post.content not in str(analysis.result_payload)
    assert "details" not in str(analysis.result_payload)


@pytest.mark.parametrize("score", [-1, 1])
def test_overall_score_boundaries_are_accepted(client, db_session: Session, score: int) -> None:
    _user, token = register_login(
        client,
        email=f"sentiment-boundary-{score}@example.com",
        username=f"sentiment-boundary-{score}",
    )
    source = create_source(db_session, handle=f"boundary-{score}")
    create_post(
        db_session,
        source=source,
        external_id=f"boundary-{score}",
        content="boundary content",
        published_at=NOW,
    )
    follow(client, token, source.id)
    fake = FakeAiClient(valid_ai_response(overall_score=score))
    install_service(client, db_session, fake)
    try:
        response = client.post(URL, headers=auth_headers(token))
    finally:
        clear_service_override()

    assert response.status_code == 200
    assert Decimal(str(response.json()["overall_score"])) == Decimal(str(score))


@pytest.mark.parametrize(
    "response",
    [
        valid_ai_response(overall_score=Decimal("1.01")),
        valid_ai_response(overall_score=float("nan")),
        valid_ai_response(overall_label="mixed"),
        valid_ai_response(model_version="   "),
        valid_ai_response(formula_version="sentiment-formula-v1"),
        valid_ai_response(details="not-a-list"),
        valid_ai_response(details=[{"text": "   ", "label": "positive", "confidence": 0.5}]),
        valid_ai_response(details=[{"text": "not submitted", "label": "positive", "confidence": 0.5}]),
        valid_ai_response(details=[{"text": "authorized content", "label": "mixed", "confidence": 0.5}]),
        valid_ai_response(details=[{"text": "authorized content", "label": "positive", "confidence": float("nan")}]),
        {"overall_score": 0.2},
    ],
)
def test_invalid_ai_results_return_502_without_persistence(
    client,
    db_session: Session,
    response: dict[str, Any],
) -> None:
    _user, token = register_login(
        client,
        email=f"sentiment-invalid-{len(sentiment_analyses(db_session))}@example.com",
        username=f"sentiment-invalid-{len(sentiment_analyses(db_session))}",
    )
    source = create_source(db_session, handle=f"invalid-{len(sentiment_analyses(db_session))}")
    create_post(
        db_session,
        source=source,
        external_id=f"invalid-{len(sentiment_analyses(db_session))}",
        content="authorized content",
        published_at=NOW,
    )
    follow(client, token, source.id)
    fake = FakeAiClient(response)
    install_service(client, db_session, fake)
    try:
        result = client.post(URL, headers=auth_headers(token))
    finally:
        clear_service_override()

    assert result.status_code == 502
    assert result.json()["detail"] == "AI service returned an invalid response."
    assert sentiment_analyses(db_session) == []


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (AiServiceUnavailableError("down"), 503, "AI service temporarily unavailable."),
        (AiServiceRequestError("rejected", status_code=400), 502, "AI service rejected the backend request."),
        (AiServiceResponseError("invalid json"), 502, "AI service returned an invalid response."),
    ],
)
def test_ai_client_errors_are_mapped_without_persistence(
    client,
    db_session: Session,
    error: Exception,
    status_code: int,
    detail: str,
) -> None:
    _user, token = register_login(
        client,
        email=f"sentiment-error-{status_code}@example.com",
        username=f"sentiment-error-{status_code}",
    )
    source = create_source(db_session, handle=f"error-{status_code}")
    create_post(
        db_session,
        source=source,
        external_id=f"error-{status_code}",
        content="authorized content",
        published_at=NOW,
    )
    follow(client, token, source.id)
    fake = FakeAiClient(error)
    install_service(client, db_session, fake)
    try:
        response = client.post(URL, headers=auth_headers(token))
    finally:
        clear_service_override()

    assert response.status_code == status_code
    assert response.json()["detail"] == detail
    assert sentiment_analyses(db_session) == []


def test_repeated_successes_append_and_history_remains_user_scoped(client, db_session: Session) -> None:
    user, token = register_login(
        client,
        email="sentiment-repeat@example.com",
        username="sentiment-repeat",
    )
    _foreign_user, foreign_token = register_login(
        client,
        email="sentiment-repeat-foreign@example.com",
        username="sentiment-repeat-foreign",
    )
    source = create_source(db_session, handle="repeat")
    create_post(
        db_session,
        source=source,
        external_id="repeat",
        content="repeat content",
        published_at=NOW,
    )
    follow(client, token, source.id)
    fake = FakeAiClient(valid_ai_response())
    install_service(client, db_session, fake)
    try:
        first = client.post(URL, headers=auth_headers(token))
        second = client.post(URL, headers=auth_headers(token))
    finally:
        clear_service_override()

    assert first.status_code == second.status_code == 200
    assert first.json()["analysis_id"] != second.json()["analysis_id"]
    analyses = sentiment_analyses(db_session)
    assert len(analyses) == 2
    assert all(analysis.user_id == user["id"] for analysis in analyses)
    foreign_detail = client.get(
        f"/api/v1/ai/analyses/{first.json()['analysis_id']}",
        headers=auth_headers(foreign_token),
    )
    assert foreign_detail.status_code == 404
    assert foreign_detail.json()["detail"] == "AI analysis not found."