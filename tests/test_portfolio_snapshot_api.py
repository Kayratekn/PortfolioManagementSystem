from __future__ import annotations

import inspect
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.dependencies import get_portfolio_valuation_service
from src.main import app
from src.model.portfolio_snapshot import PortfolioSnapshot
from src.services.benchmark_comparison_service import BenchmarkComparisonService
from src.services.portfolio_performance_service import PortfolioPerformanceService
from src.services.portfolio_valuation_service import PortfolioValuationService


SNAPSHOT_DATE = "2026-09-07"


class FakeValuationService:
    def __init__(self, results: dict[str, SimpleNamespace]) -> None:
        self.results = results
        self.calls: list[str] = []

    def get_valuation_in_currency(self, **kwargs: object) -> SimpleNamespace:
        currency = kwargs["target_currency"]
        assert isinstance(currency, str)
        self.calls.append(currency)
        return self.results[currency]


def _complete(total: Decimal) -> SimpleNamespace:
    return SimpleNamespace(status="COMPLETE", total_portfolio_value=total)


def _incomplete() -> SimpleNamespace:
    return SimpleNamespace(status="INCOMPLETE", total_portfolio_value=None)


def _valuation_service(*, incomplete: bool = False) -> FakeValuationService:
    return FakeValuationService(
        {
            "TRY": _complete(Decimal("123.45678901")),
            "USD": _incomplete() if incomplete else _complete(Decimal("4.56789012")),
            "EUR": _complete(Decimal("5.67890123")),
            "GBP": _complete(Decimal("6.78901234")),
        }
    )


def _use_valuation_service(valuation_service: FakeValuationService) -> None:
    app.dependency_overrides[get_portfolio_valuation_service] = lambda: valuation_service


def _register_user(client, *, email: str, username: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": "StrongPass123"},
    )
    assert response.status_code == 201


def _login_user(client, *, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_portfolio(client, token: str, *, name: str = "Snapshot Portfolio") -> int:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_owner_portfolio(client, *, email: str, username: str) -> tuple[str, int]:
    _register_user(client, email=email, username=username)
    token = _login_user(client, email=email)
    return token, _create_portfolio(client, token)


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _post_url(portfolio_id: int, snapshot_date: str = SNAPSHOT_DATE) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/snapshots?snapshot_date={snapshot_date}"


def _get_url(portfolio_id: int, *, start_date: str, end_date: str) -> str:
    return (
        f"/api/v1/portfolios/{portfolio_id}/snapshots?"
        f"start_date={start_date}&end_date={end_date}"
    )


def _add_snapshot(
    db_session: Session,
    *,
    portfolio_id: int,
    snapshot_date: date,
    total_try: Decimal = Decimal("100.00000000"),
) -> PortfolioSnapshot:
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=snapshot_date,
        total_value_try=total_try,
        total_value_usd=Decimal("10.00000000"),
        total_value_eur=Decimal("9.00000000"),
        total_value_gbp=Decimal("8.00000000"),
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


def test_authenticated_post_generates_snapshot_and_serializes_decimal_totals_exactly(
    client,
    db_session: Session,
) -> None:
    valuation_service = _valuation_service()
    _use_valuation_service(valuation_service)
    token, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-post@example.com", username="snapshot-post"
    )

    response = client.post(_post_url(portfolio_id), headers=_headers(token))

    assert response.status_code == 201
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["snapshot_date"] == SNAPSHOT_DATE
    assert body["total_value_try"] == "123.45678901"
    assert body["total_value_usd"] == "4.56789012"
    assert body["total_value_eur"] == "5.67890123"
    assert body["total_value_gbp"] == "6.78901234"
    assert isinstance(body["total_value_try"], str)
    assert not isinstance(body["total_value_try"], float)
    assert body["created_at"] is not None
    assert valuation_service.calls == ["TRY", "USD", "EUR", "GBP"]
    persisted = db_session.scalar(
        select(PortfolioSnapshot).where(PortfolioSnapshot.id == body["id"])
    )
    assert persisted is not None
    assert persisted.total_value_try == Decimal("123.45678901")


def test_repeated_same_date_post_is_idempotent_and_keeps_one_snapshot_row(
    client,
    db_session: Session,
) -> None:
    valuation_service = _valuation_service()
    _use_valuation_service(valuation_service)
    token, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-repeat@example.com", username="snapshot-repeat"
    )

    first = client.post(_post_url(portfolio_id), headers=_headers(token))
    second = client.post(_post_url(portfolio_id), headers=_headers(token))

    assert first.status_code == second.status_code == 201
    assert second.json() == first.json()
    assert valuation_service.calls == ["TRY", "USD", "EUR", "GBP"]
    assert len(
        list(
            db_session.scalars(
                select(PortfolioSnapshot).where(
                    PortfolioSnapshot.portfolio_id == portfolio_id,
                    PortfolioSnapshot.snapshot_date == date.fromisoformat(SNAPSHOT_DATE),
                )
            )
        )
    ) == 1


def test_post_requires_authentication(client) -> None:
    response = client.post(_post_url(999999))

    assert response.status_code == 401


def test_post_enforces_ownership_isolation(client) -> None:
    _use_valuation_service(_valuation_service())
    _, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-post-owner@example.com", username="snapshot-post-owner"
    )
    _register_user(
        client, email="snapshot-post-other@example.com", username="snapshot-post-other"
    )
    other_token = _login_user(client, email="snapshot-post-other@example.com")

    response = client.post(_post_url(portfolio_id), headers=_headers(other_token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_post_incomplete_generation_propagates_exact_422(client, db_session: Session) -> None:
    _use_valuation_service(_valuation_service(incomplete=True))
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="snapshot-incomplete@example.com",
        username="snapshot-incomplete",
    )

    response = client.post(_post_url(portfolio_id), headers=_headers(token))

    assert response.status_code == 422
    assert response.json()["detail"] == (
        "Portfolio snapshot cannot be generated from incomplete valuation."
    )
    assert db_session.scalar(select(PortfolioSnapshot)) is None


def test_authenticated_get_returns_inclusive_persisted_history_in_deterministic_order(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-list@example.com", username="snapshot-list"
    )
    first = _add_snapshot(
        db_session,
        portfolio_id=portfolio_id,
        snapshot_date=date(2026, 9, 5),
        total_try=Decimal("5.00000000"),
    )
    second = _add_snapshot(
        db_session,
        portfolio_id=portfolio_id,
        snapshot_date=date(2026, 9, 7),
        total_try=Decimal("7.00000000"),
    )

    response = client.get(
        _get_url(portfolio_id, start_date="2026-09-05", end_date="2026-09-07"),
        headers=_headers(token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "portfolio_id": portfolio_id,
        "start_date": "2026-09-05",
        "end_date": "2026-09-07",
        "items": [
            {
                "id": first.id,
                "portfolio_id": portfolio_id,
                "snapshot_date": "2026-09-05",
                "total_value_try": "5.00000000",
                "total_value_usd": "10.00000000",
                "total_value_eur": "9.00000000",
                "total_value_gbp": "8.00000000",
                "created_at": first.created_at.isoformat().replace("+00:00", "Z"),
            },
            {
                "id": second.id,
                "portfolio_id": portfolio_id,
                "snapshot_date": "2026-09-07",
                "total_value_try": "7.00000000",
                "total_value_usd": "10.00000000",
                "total_value_eur": "9.00000000",
                "total_value_gbp": "8.00000000",
                "created_at": second.created_at.isoformat().replace("+00:00", "Z"),
            },
        ],
    }


def test_get_empty_history_returns_empty_items(client) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-empty@example.com", username="snapshot-empty"
    )

    response = client.get(
        _get_url(portfolio_id, start_date=SNAPSHOT_DATE, end_date=SNAPSHOT_DATE),
        headers=_headers(token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "portfolio_id": portfolio_id,
        "start_date": SNAPSHOT_DATE,
        "end_date": SNAPSHOT_DATE,
        "items": [],
    }


def test_get_enforces_ownership_isolation(client) -> None:
    _, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-get-owner@example.com", username="snapshot-get-owner"
    )
    _register_user(
        client, email="snapshot-get-other@example.com", username="snapshot-get-other"
    )
    other_token = _login_user(client, email="snapshot-get-other@example.com")

    response = client.get(
        _get_url(portfolio_id, start_date=SNAPSHOT_DATE, end_date=SNAPSHOT_DATE),
        headers=_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_get_requires_start_and_end_date(client) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-required@example.com", username="snapshot-required"
    )

    missing_start = client.get(
        f"/api/v1/portfolios/{portfolio_id}/snapshots?end_date={SNAPSHOT_DATE}",
        headers=_headers(token),
    )
    missing_end = client.get(
        f"/api/v1/portfolios/{portfolio_id}/snapshots?start_date={SNAPSHOT_DATE}",
        headers=_headers(token),
    )

    assert missing_start.status_code == 422
    assert missing_end.status_code == 422


def test_get_rejects_start_after_end(client) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-reversed@example.com", username="snapshot-reversed"
    )

    response = client.get(
        _get_url(portfolio_id, start_date="2026-09-08", end_date=SNAPSHOT_DATE),
        headers=_headers(token),
    )

    assert response.status_code == 422


def test_get_accepts_366_inclusive_days_and_rejects_367(client) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client, email="snapshot-range@example.com", username="snapshot-range"
    )

    accepted = client.get(
        _get_url(portfolio_id, start_date="2026-01-01", end_date="2027-01-01"),
        headers=_headers(token),
    )
    rejected = client.get(
        _get_url(portfolio_id, start_date="2026-01-01", end_date="2027-01-02"),
        headers=_headers(token),
    )

    assert accepted.status_code == 200
    assert accepted.json()["items"] == []
    assert rejected.status_code == 422


def test_get_non_owner_invalid_range_returns_canonical_ownership_404(client) -> None:
    _, portfolio_id = _create_owner_portfolio(
        client,
        email="snapshot-invalid-owner@example.com",
        username="snapshot-invalid-owner",
    )
    _register_user(
        client,
        email="snapshot-invalid-other@example.com",
        username="snapshot-invalid-other",
    )
    other_token = _login_user(client, email="snapshot-invalid-other@example.com")

    response = client.get(
        _get_url(portfolio_id, start_date="2026-09-08", end_date=SNAPSHOT_DATE),
        headers=_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_valuation_performance_and_benchmark_services_remain_snapshot_independent() -> None:
    for service in (
        PortfolioValuationService,
        PortfolioPerformanceService,
        BenchmarkComparisonService,
    ):
        assert "portfolio_snapshot" not in inspect.getsource(service)
