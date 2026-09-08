from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.dependencies import get_ai_client
from src.main import app
from src.model.ai_analysis import AiAnalysis
from src.repositories.ai_analysis_repository import AiAnalysisRepository


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def register_user(client, *, email: str, username: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(client, *, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_portfolio(client, token: str, *, name: str = "History Portfolio") -> dict[str, Any]:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": name, "base_currency": "TRY"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def create_user_with_portfolio(
    client,
    *,
    email: str,
    username: str,
    portfolio_name: str = "History Portfolio",
) -> tuple[dict[str, Any], str, dict[str, Any]]:
    user = register_user(client, email=email, username=username)
    token = login_user(client, email=email)
    portfolio = create_portfolio(client, token, name=portfolio_name)
    return user, token, portfolio


def add_analysis(
    db_session: Session,
    *,
    user_id: int,
    portfolio_id: int | None,
    created_at: datetime,
    analysis_type: str = "portfolio-analysis",
    result_payload: dict[str, Any] | None = None,
    explanation_text: str | None = "Explanation",
    disclaimer: str | None = "Educational only.",
    model_version: str = "model-v1",
    formula_version: str | None = "formula-v1",
) -> AiAnalysis:
    analysis = AiAnalysis(
        user_id=user_id,
        portfolio_id=portfolio_id,
        analysis_type=analysis_type,
        result_payload=result_payload if result_payload is not None else {"score": 1, "nested": {"a": [1, 2]}},
        explanation_text=explanation_text,
        disclaimer=disclaimer,
        model_version=model_version,
        formula_version=formula_version,
        created_at=created_at,
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)
    return analysis


def analysis_url(analysis_id: int) -> str:
    return f"/api/v1/ai/analyses/{analysis_id}"


def portfolio_history_url(portfolio_id: int) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/ai/analyses"


def assert_public_analysis_fields(item: dict[str, Any]) -> None:
    assert set(item) == {
        "analysis_id",
        "portfolio_id",
        "analysis_type",
        "result_payload",
        "explanation_text",
        "disclaimer",
        "model_version",
        "formula_version",
        "created_at",
    }
    assert "user_id" not in item


def test_ai_analysis_history_endpoints_require_authentication(client) -> None:
    responses = [
        client.get("/api/v1/ai/analyses"),
        client.get("/api/v1/ai/analyses/1"),
        client.get(portfolio_history_url(1)),
    ]

    assert all(response.status_code == 401 for response in responses)
    assert all(response.json()["detail"] == AUTH_DETAIL for response in responses)


def test_global_history_is_user_scoped_paginated_and_deterministically_ordered(
    client,
    db_session: Session,
) -> None:
    user, token, portfolio = create_user_with_portfolio(
        client,
        email="history-owner@example.com",
        username="history-owner",
    )
    other_user, _other_token, other_portfolio = create_user_with_portfolio(
        client,
        email="history-other@example.com",
        username="history-other",
    )
    older = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=portfolio["id"],
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
    )
    same_time_first = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=None,
        created_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc),
    )
    same_time_second = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=portfolio["id"],
        created_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc),
    )
    other_analysis = add_analysis(
        db_session,
        user_id=other_user["id"],
        portfolio_id=other_portfolio["id"],
        created_at=datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc),
    )

    response = client.get("/api/v1/ai/analyses?skip=1&limit=2", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["skip"] == 1
    assert body["limit"] == 2
    assert [item["analysis_id"] for item in body["items"]] == [same_time_first.id, older.id]
    assert same_time_second.id not in [item["analysis_id"] for item in body["items"]]
    assert other_analysis.id not in [item["analysis_id"] for item in body["items"]]
    assert all("user_id" not in item for item in body["items"])


def test_detail_returns_owned_public_analysis_payload_and_metadata(client, db_session: Session) -> None:
    user, token, portfolio = create_user_with_portfolio(
        client,
        email="history-detail@example.com",
        username="history-detail",
    )
    result_payload = {"weights": {"AAL": "0.50"}, "metrics": [1, {"x": True}]}
    analysis = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=portfolio["id"],
        analysis_type="robustness",
        result_payload=deepcopy(result_payload),
        explanation_text="Readable explanation",
        disclaimer="Use at your own risk.",
        model_version="model-v2",
        formula_version="formula-v2",
        created_at=datetime(2026, 9, 7, 12, 30, tzinfo=timezone.utc),
    )

    response = client.get(analysis_url(analysis.id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert_public_analysis_fields(body)
    assert body["analysis_id"] == analysis.id
    assert body["portfolio_id"] == portfolio["id"]
    assert body["analysis_type"] == "robustness"
    assert body["result_payload"] == result_payload
    assert body["explanation_text"] == "Readable explanation"
    assert body["disclaimer"] == "Use at your own risk."
    assert body["model_version"] == "model-v2"
    assert body["formula_version"] == "formula-v2"
    assert body["created_at"].startswith("2026-09-07T12:30:00")


def test_detail_missing_and_cross_user_return_same_404(client, db_session: Session) -> None:
    owner, _owner_token, portfolio = create_user_with_portfolio(
        client,
        email="history-detail-owner@example.com",
        username="history-detail-owner",
    )
    _other, other_token, _other_portfolio = create_user_with_portfolio(
        client,
        email="history-detail-other@example.com",
        username="history-detail-other",
    )
    analysis = add_analysis(
        db_session,
        user_id=owner["id"],
        portfolio_id=portfolio["id"],
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
    )

    missing_response = client.get(analysis_url(999999), headers=auth_headers(other_token))
    cross_user_response = client.get(analysis_url(analysis.id), headers=auth_headers(other_token))

    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "AI analysis not found."
    assert cross_user_response.status_code == 404
    assert cross_user_response.json()["detail"] == "AI analysis not found."


def test_nullable_fields_serialize_as_null(client, db_session: Session) -> None:
    user, token, _portfolio = create_user_with_portfolio(
        client,
        email="history-null@example.com",
        username="history-null",
    )
    analysis = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=None,
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
        explanation_text=None,
        disclaimer=None,
        formula_version=None,
    )

    response = client.get(analysis_url(analysis.id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] is None
    assert body["explanation_text"] is None
    assert body["disclaimer"] is None
    assert body["formula_version"] is None


def test_portfolio_history_verifies_ownership_before_listing(client, db_session: Session) -> None:
    owner, _owner_token, owner_portfolio = create_user_with_portfolio(
        client,
        email="history-portfolio-owner@example.com",
        username="history-portfolio-owner",
    )
    _other, other_token, _other_portfolio = create_user_with_portfolio(
        client,
        email="history-portfolio-other@example.com",
        username="history-portfolio-other",
    )
    add_analysis(
        db_session,
        user_id=owner["id"],
        portfolio_id=owner_portfolio["id"],
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
    )

    cross_user_response = client.get(
        portfolio_history_url(owner_portfolio["id"]),
        headers=auth_headers(other_token),
    )
    missing_response = client.get(portfolio_history_url(999999), headers=auth_headers(other_token))

    assert cross_user_response.status_code == 404
    assert cross_user_response.json()["detail"] == "Portfolio not found."
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Portfolio not found."


def test_portfolio_history_scopes_by_portfolio_and_user_with_total(client, db_session: Session) -> None:
    user, token, first_portfolio = create_user_with_portfolio(
        client,
        email="history-portfolio-scope@example.com",
        username="history-portfolio-scope",
    )
    second_portfolio = create_portfolio(client, token, name="Second Portfolio")
    other_user, _other_token, other_portfolio = create_user_with_portfolio(
        client,
        email="history-portfolio-scope-other@example.com",
        username="history-portfolio-scope-other",
    )
    matching_newer = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=first_portfolio["id"],
        created_at=datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc),
    )
    matching_older = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=first_portfolio["id"],
        created_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc),
    )
    add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=second_portfolio["id"],
        created_at=datetime(2026, 9, 7, 11, 0, tzinfo=timezone.utc),
    )
    add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=None,
        created_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
    )
    add_analysis(
        db_session,
        user_id=other_user["id"],
        portfolio_id=first_portfolio["id"],
        created_at=datetime(2026, 9, 7, 13, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        f"{portfolio_history_url(first_portfolio['id'])}?skip=0&limit=100",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert body["skip"] == 0
    assert body["limit"] == 100
    assert [item["analysis_id"] for item in body["items"]] == [matching_newer.id, matching_older.id]
    assert all(item["portfolio_id"] == first_portfolio["id"] for item in body["items"])
    assert all(set(item) == {
        "analysis_id",
        "portfolio_id",
        "analysis_type",
        "result_payload",
        "explanation_text",
        "disclaimer",
        "model_version",
        "formula_version",
        "created_at",
    } for item in body["items"])


def test_empty_owned_portfolio_history_returns_empty_page(client) -> None:
    _user, token, portfolio = create_user_with_portfolio(
        client,
        email="history-empty@example.com",
        username="history-empty",
    )

    response = client.get(portfolio_history_url(portfolio["id"]), headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json() == {"total": 0, "skip": 0, "limit": 50, "items": []}


def test_history_reads_do_not_create_or_modify_ai_analysis_rows(client, db_session: Session) -> None:
    user, token, portfolio = create_user_with_portfolio(
        client,
        email="history-readonly@example.com",
        username="history-readonly",
    )
    analysis = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=portfolio["id"],
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
        result_payload={"before": {"value": 1}},
        explanation_text="Before",
        disclaimer="Disclaimer",
        model_version="model-readonly",
        formula_version="formula-readonly",
    )
    before_count = db_session.query(AiAnalysis).count()
    before = {
        "user_id": analysis.user_id,
        "portfolio_id": analysis.portfolio_id,
        "analysis_type": analysis.analysis_type,
        "result_payload": deepcopy(analysis.result_payload),
        "explanation_text": analysis.explanation_text,
        "disclaimer": analysis.disclaimer,
        "model_version": analysis.model_version,
        "formula_version": analysis.formula_version,
        "created_at": analysis.created_at,
    }

    list_response = client.get("/api/v1/ai/analyses", headers=auth_headers(token))
    detail_response = client.get(analysis_url(analysis.id), headers=auth_headers(token))
    portfolio_response = client.get(portfolio_history_url(portfolio["id"]), headers=auth_headers(token))
    db_session.expire_all()
    refreshed = db_session.get(AiAnalysis, analysis.id)

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert portfolio_response.status_code == 200
    assert db_session.query(AiAnalysis).count() == before_count
    assert refreshed is not None
    assert {
        "user_id": refreshed.user_id,
        "portfolio_id": refreshed.portfolio_id,
        "analysis_type": refreshed.analysis_type,
        "result_payload": refreshed.result_payload,
        "explanation_text": refreshed.explanation_text,
        "disclaimer": refreshed.disclaimer,
        "model_version": refreshed.model_version,
        "formula_version": refreshed.formula_version,
        "created_at": refreshed.created_at,
    } == before


def test_repository_get_by_id_for_user_isolates_rows(db_session: Session, client) -> None:
    owner, _owner_token, portfolio = create_user_with_portfolio(
        client,
        email="history-repo-owner@example.com",
        username="history-repo-owner",
    )
    other, _other_token, _other_portfolio = create_user_with_portfolio(
        client,
        email="history-repo-other@example.com",
        username="history-repo-other",
    )
    analysis = add_analysis(
        db_session,
        user_id=owner["id"],
        portfolio_id=portfolio["id"],
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
    )
    repository = AiAnalysisRepository(db_session)

    assert repository.get_by_id_for_user(analysis_id=analysis.id, user_id=owner["id"]) == analysis
    assert repository.get_by_id_for_user(analysis_id=analysis.id, user_id=other["id"]) is None
    assert repository.get_by_id_for_user(analysis_id=999999, user_id=owner["id"]) is None


def test_history_endpoints_do_not_need_ai_client_dependency(client, db_session: Session) -> None:
    user, token, portfolio = create_user_with_portfolio(
        client,
        email="history-no-ai-client@example.com",
        username="history-no-ai-client",
    )
    analysis = add_analysis(
        db_session,
        user_id=user["id"],
        portfolio_id=portfolio["id"],
        created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc),
    )

    def fail_ai_client():
        raise AssertionError("AI client must not be resolved for history reads")

    app.dependency_overrides[get_ai_client] = fail_ai_client
    try:
        responses = [
            client.get("/api/v1/ai/analyses", headers=auth_headers(token)),
            client.get(analysis_url(analysis.id), headers=auth_headers(token)),
            client.get(portfolio_history_url(portfolio["id"]), headers=auth_headers(token)),
        ]
    finally:
        app.dependency_overrides.pop(get_ai_client, None)

    assert [response.status_code for response in responses] == [200, 200, 200]


def test_no_migration_added_for_ai_analysis_history_slice() -> None:
    assert not (PROJECT_ROOT / "alembic" / "versions" / "20260907_0024_create_ai_analysis_history.py").exists()
    assert not (PROJECT_ROOT / "alembic" / "versions" / "20260908_0024_create_ai_analysis_history.py").exists()