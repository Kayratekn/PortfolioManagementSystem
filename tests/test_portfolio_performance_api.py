from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.portfolio_cash_flow import PortfolioCashFlow


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
START_DATE = "2026-01-02"
END_DATE = "2026-01-02"


def register_user(client, *, email: str, username: str, password: str = "StrongPass123", preferred_currency: str = "TRY") -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password, "preferred_currency": preferred_currency},
    )
    assert response.status_code == 201
    return response.json()


def login_user(client, *, email: str, password: str = "StrongPass123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_portfolio(client, token: str, *, name: str = "Performance Portfolio"):
    return client.post("/api/v1/portfolios", json={"name": name}, headers=auth_headers(token))


def create_owner_portfolio(client, *, email: str, username: str) -> tuple[str, int]:
    register_user(client, email=email, username=username)
    token = login_user(client, email=email)
    portfolio_response = create_portfolio(client, token)
    assert portfolio_response.status_code == 201
    return token, portfolio_response.json()["id"]


def performance_url(portfolio_id: int, *, start_date: str = START_DATE, end_date: str = END_DATE) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/performance?start_date={start_date}&end_date={end_date}"


def add_cash_flow(db_session: Session, *, portfolio_id: int, flow_type: str = "DEPOSIT", amount: Decimal = Decimal("100.00000000"), flow_date: date = date(2026, 1, 2)) -> PortfolioCashFlow:
    cash_flow = PortfolioCashFlow(
        portfolio_id=portfolio_id,
        flow_type=flow_type,
        amount=amount,
        currency="TRY",
        flow_date=flow_date,
    )
    db_session.add(cash_flow)
    db_session.commit()
    db_session.refresh(cash_flow)
    return cash_flow


def test_performance_requires_authentication(client) -> None:
    response = client.get(performance_url(999999))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_another_user_cannot_read_performance(client) -> None:
    owner_token, portfolio_id = create_owner_portfolio(client, email="performance-owner@example.com", username="performance-owner")
    assert owner_token
    register_user(client, email="performance-other@example.com", username="performance-other")
    other_token = login_user(client, email="performance-other@example.com")

    response = client.get(performance_url(portfolio_id), headers=auth_headers(other_token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_missing_start_or_end_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="performance-missing-date@example.com", username="performance-missing-date")

    missing_start = client.get(f"/api/v1/portfolios/{portfolio_id}/performance?end_date=2026-01-02", headers=auth_headers(token))
    missing_end = client.get(f"/api/v1/portfolios/{portfolio_id}/performance?start_date=2026-01-02", headers=auth_headers(token))

    assert missing_start.status_code == 422
    assert missing_end.status_code == 422


def test_reversed_date_range_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="performance-reversed@example.com", username="performance-reversed")

    response = client.get(performance_url(portfolio_id, start_date="2026-01-03", end_date="2026-01-02"), headers=auth_headers(token))

    assert response.status_code == 422


def test_more_than_366_inclusive_days_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="performance-too-large@example.com", username="performance-too-large")

    response = client.get(performance_url(portfolio_id, start_date="2026-01-01", end_date="2027-01-02"), headers=auth_headers(token))

    assert response.status_code == 422


def test_exactly_366_inclusive_days_is_accepted(client) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="performance-366@example.com", username="performance-366")

    response = client.get(performance_url(portfolio_id, start_date="2026-01-01", end_date="2027-01-01"), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NOT_APPLICABLE"
    assert len(body["points"]) == 366


def test_cash_only_deposit_serializes_decimal_fields_as_strings(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="performance-cash@example.com", username="performance-cash")
    add_cash_flow(db_session, portfolio_id=portfolio_id, amount=Decimal("100.00000000"), flow_date=date(2026, 1, 2))

    response = client.get(performance_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    point = body["points"][0]
    assert body["portfolio_id"] == portfolio_id
    assert body["base_currency"] == "TRY"
    assert body["start_date"] == START_DATE
    assert body["end_date"] == END_DATE
    assert body["status"] == "COMPLETE"
    assert body["cumulative_return"] == "0"
    assert point["date"] == START_DATE
    assert point["portfolio_value"] == "100.00000000"
    assert point["external_flow"] == "100.00000000"
    assert point["daily_return"] == "0"
    assert point["cumulative_return"] == "0"
    assert point["status"] == "COMPLETE"
    assert point["unavailable_reason"] is None
    assert isinstance(point["daily_return"], str)
    assert not isinstance(point["daily_return"], float)

def test_invalid_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="performance-invalid-date@example.com", username="performance-invalid-date")

    response = client.get(performance_url(portfolio_id, start_date="not-a-date", end_date="2026-01-02"), headers=auth_headers(token))

    assert response.status_code == 422
