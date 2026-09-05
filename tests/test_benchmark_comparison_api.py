from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.benchmark import Benchmark
from src.model.benchmark_price import BenchmarkPrice
from src.model.portfolio_cash_flow import PortfolioCashFlow


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."


def register_user(
    client,
    *,
    email: str,
    username: str,
    password: str = "StrongPass123",
    preferred_currency: str = "TRY",
) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": password,
            "preferred_currency": preferred_currency,
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(client, *, email: str, password: str = "StrongPass123") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_portfolio(client, token: str, *, name: str = "Comparison Portfolio") -> int:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": name},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["id"]


def create_owner_portfolio(client, *, email: str, username: str) -> tuple[str, int]:
    register_user(client, email=email, username=username)
    token = login_user(client, email=email)
    return token, create_portfolio(client, token)


def comparison_url(
    portfolio_id: int,
    *,
    benchmark_code: str = "BIST100",
    start_date: str = "2026-01-02",
    end_date: str = "2026-01-02",
) -> str:
    return (
        f"/api/v1/portfolios/{portfolio_id}/benchmark-comparison"
        f"?benchmark_code={benchmark_code}&start_date={start_date}&end_date={end_date}"
    )


def add_complete_cash_history(db_session: Session, *, portfolio_id: int) -> None:
    db_session.add(
        PortfolioCashFlow(
            portfolio_id=portfolio_id,
            flow_type="DEPOSIT",
            amount=Decimal("100.00000000"),
            currency="TRY",
            flow_date=date(2026, 1, 1),
        )
    )
    db_session.commit()


def add_benchmark(
    db_session: Session,
    *,
    code: str = "BIST100",
    is_active: bool = True,
) -> Benchmark:
    benchmark = Benchmark(
        code=code,
        name="BIST 100",
        benchmark_type="MARKET_INDEX",
        native_currency="TRY",
        index_owner="BORSA_ISTANBUL",
        return_type="PRICE_RETURN",
        provider="VERIFIED_PROVIDER",
        provider_symbol=code,
        is_active=is_active,
    )
    db_session.add(benchmark)
    db_session.commit()
    db_session.refresh(benchmark)
    return benchmark


def add_benchmark_price(
    db_session: Session,
    *,
    benchmark_id: int,
    price_date: date,
    close_value: Decimal,
) -> None:
    db_session.add(
        BenchmarkPrice(
            benchmark_id=benchmark_id,
            price_date=price_date,
            close_value=close_value,
            source="VERIFIED_PROVIDER",
        )
    )
    db_session.commit()


def test_benchmark_comparison_requires_authentication(client) -> None:
    response = client.get(comparison_url(999999))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_benchmark_comparison_returns_decimal_strings(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="comparison-api@example.com",
        username="comparison-api",
    )
    add_complete_cash_history(db_session, portfolio_id=portfolio_id)
    benchmark = add_benchmark(db_session)
    add_benchmark_price(
        db_session,
        benchmark_id=benchmark.id,
        price_date=date(2026, 1, 1),
        close_value=Decimal("100"),
    )
    add_benchmark_price(
        db_session,
        benchmark_id=benchmark.id,
        price_date=date(2026, 1, 2),
        close_value=Decimal("110"),
    )

    response = client.get(comparison_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["benchmark_id"] == benchmark.id
    assert body["benchmark_code"] == "BIST100"
    assert body["benchmark_name"] == "BIST 100"
    assert body["portfolio_base_currency"] == "TRY"
    assert body["benchmark_native_currency"] == "TRY"
    assert body["status"] == "COMPLETE"
    assert body["portfolio_status"] == "COMPLETE"
    assert body["benchmark_status"] == "COMPLETE"
    assert body["unavailable_reason"] is None
    assert body["portfolio_cumulative_return"] == "0"
    assert body["benchmark_cumulative_return"] == "0.1"
    assert body["excess_return"] == "-0.1"
    assert body["benchmark_baseline_date"] == "2026-01-01"
    assert body["benchmark_baseline_close_value"] == "100.00000000"
    assert body["benchmark_baseline_converted_close_value"] == "100.00000000"
    assert body["portfolio_points"][0]["normalized_value"] == "100"
    assert body["benchmark_points"][0]["normalized_value"] == "110.0"
    assert isinstance(body["benchmark_cumulative_return"], str)


def test_unknown_and_inactive_benchmark_return_404(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="comparison-unknown@example.com",
        username="comparison-unknown",
    )
    add_complete_cash_history(db_session, portfolio_id=portfolio_id)
    add_benchmark(db_session, code="INACTIVE", is_active=False)

    missing = client.get(
        comparison_url(portfolio_id, benchmark_code="UNKNOWN"),
        headers=auth_headers(token),
    )
    inactive = client.get(
        comparison_url(portfolio_id, benchmark_code="INACTIVE"),
        headers=auth_headers(token),
    )

    assert missing.status_code == 404
    assert missing.json()["detail"] == "Benchmark not found."
    assert inactive.status_code == 404
    assert inactive.json()["detail"] == "Benchmark not found."


def test_ownership_isolation_hides_benchmark_existence(client, db_session: Session) -> None:
    owner_token, portfolio_id = create_owner_portfolio(
        client,
        email="comparison-owner@example.com",
        username="comparison-owner",
    )
    assert owner_token
    register_user(client, email="comparison-other@example.com", username="comparison-other")
    other_token = login_user(client, email="comparison-other@example.com")
    add_benchmark(db_session)

    response = client.get(comparison_url(portfolio_id), headers=auth_headers(other_token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_missing_required_query_values_return_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="comparison-missing-query@example.com",
        username="comparison-missing-query",
    )

    missing_benchmark = client.get(
        f"/api/v1/portfolios/{portfolio_id}/benchmark-comparison?start_date=2026-01-02&end_date=2026-01-02",
        headers=auth_headers(token),
    )
    missing_start = client.get(
        f"/api/v1/portfolios/{portfolio_id}/benchmark-comparison?benchmark_code=BIST100&end_date=2026-01-02",
        headers=auth_headers(token),
    )
    missing_end = client.get(
        f"/api/v1/portfolios/{portfolio_id}/benchmark-comparison?benchmark_code=BIST100&start_date=2026-01-02",
        headers=auth_headers(token),
    )

    assert missing_benchmark.status_code == 422
    assert missing_start.status_code == 422
    assert missing_end.status_code == 422


def test_invalid_date_range_contract_matches_performance_api(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="comparison-date-range@example.com",
        username="comparison-date-range",
    )
    add_complete_cash_history(db_session, portfolio_id=portfolio_id)
    benchmark = add_benchmark(db_session)
    add_benchmark_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))

    reversed_range = client.get(
        comparison_url(portfolio_id, start_date="2026-01-03", end_date="2026-01-02"),
        headers=auth_headers(token),
    )
    too_large = client.get(
        comparison_url(portfolio_id, start_date="2026-01-01", end_date="2027-01-02"),
        headers=auth_headers(token),
    )
    invalid_date = client.get(
        comparison_url(portfolio_id, start_date="not-a-date", end_date="2026-01-02"),
        headers=auth_headers(token),
    )

    assert reversed_range.status_code == 422
    assert too_large.status_code == 422
    assert invalid_date.status_code == 422