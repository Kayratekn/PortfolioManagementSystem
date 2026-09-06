from __future__ import annotations

from sqlalchemy.orm import Session

from src.model.benchmark import Benchmark


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
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def create_benchmark(
    db_session: Session,
    *,
    code: str,
    name: str,
    benchmark_type: str = "MARKET_INDEX",
    native_currency: str = "USD",
    index_owner: str = "TEST_OWNER",
    return_type: str = "PRICE_RETURN",
    provider: str = "YAHOO_FINANCE",
    provider_symbol: str,
    is_active: bool = True,
) -> Benchmark:
    benchmark = Benchmark(
        code=code,
        name=name,
        benchmark_type=benchmark_type,
        native_currency=native_currency,
        index_owner=index_owner,
        return_type=return_type,
        provider=provider,
        provider_symbol=provider_symbol,
        is_active=is_active,
    )
    db_session.add(benchmark)
    db_session.commit()
    db_session.refresh(benchmark)
    return benchmark


def test_benchmark_catalog_requires_authentication(client) -> None:
    response = client.get("/api/v1/benchmarks")

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Authentication credentials were not provided or are invalid."
    )


def test_authenticated_user_can_list_active_benchmarks_with_exact_public_fields(
    client,
    db_session: Session,
) -> None:
    register_user(client, email="benchmark-catalog@example.com", username="benchmark-catalog")
    token = login_user(client, email="benchmark-catalog@example.com")
    sp500 = create_benchmark(
        db_session,
        code="SP500",
        name="S&P 500",
        index_owner="SP_DOW_JONES_INDICES",
        provider_symbol="^GSPC",
    )
    bist100 = create_benchmark(
        db_session,
        code="BIST100",
        name="BIST 100",
        native_currency="TRY",
        index_owner="BORSA_ISTANBUL",
        provider_symbol="XU100.IS",
    )
    create_benchmark(
        db_session,
        code="NASDAQ100",
        name="NASDAQ-100",
        index_owner="NASDAQ",
        provider_symbol="^NDX",
        is_active=False,
    )

    response = client.get(
        "/api/v1/benchmarks",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["code"] for item in body["items"]] == ["BIST100", "SP500"]
    assert body["items"] == [
        {
            "id": bist100.id,
            "code": "BIST100",
            "name": "BIST 100",
            "benchmark_type": "MARKET_INDEX",
            "native_currency": "TRY",
            "index_owner": "BORSA_ISTANBUL",
            "return_type": "PRICE_RETURN",
        },
        {
            "id": sp500.id,
            "code": "SP500",
            "name": "S&P 500",
            "benchmark_type": "MARKET_INDEX",
            "native_currency": "USD",
            "index_owner": "SP_DOW_JONES_INDICES",
            "return_type": "PRICE_RETURN",
        },
    ]
    assert set(body.keys()) == {"items", "total"}
    for item in body["items"]:
        assert set(item.keys()) == {
            "id",
            "code",
            "name",
            "benchmark_type",
            "native_currency",
            "index_owner",
            "return_type",
        }
        assert "provider" not in item
        assert "provider_symbol" not in item
        assert "is_active" not in item