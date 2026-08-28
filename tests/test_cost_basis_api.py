from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.transaction import Transaction


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
AS_OF_DATE = "2026-08-25"


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


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_portfolio(
    client,
    token: str,
    *,
    name: str = "Cost Basis Portfolio",
    base_currency: str | None = None,
):
    payload = {"name": name}
    if base_currency is not None:
        payload["base_currency"] = base_currency
    return client.post(
        "/api/v1/portfolios",
        json=payload,
        headers=auth_headers(token),
    )


def create_owner_portfolio(client, *, email: str, username: str) -> tuple[str, int]:
    register_user(client, email=email, username=username)
    token = login_user(client, email=email)
    portfolio_response = create_portfolio(client, token)
    assert portfolio_response.status_code == 201
    return token, portfolio_response.json()["id"]


def cost_basis_url(portfolio_id: int, as_of_date: str = AS_OF_DATE) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/cost-basis?as_of_date={as_of_date}"


def create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_name: str | None = None,
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name or f"{asset_code} Example Asset",
        asset_type=asset_type,
        fund_kind=fund_kind,
        currency=currency,
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def add_transaction(
    db_session: Session,
    *,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str = "BUY",
    quantity: Decimal = Decimal("10.00000000"),
    unit_price: Decimal = Decimal("20.00000000"),
    transaction_date: date = date(2026, 8, 20),
) -> Transaction:
    transaction = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=unit_price,
        transaction_date=transaction_date,
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction


def test_cost_basis_requires_authentication(client) -> None:
    response = client.get(cost_basis_url(999999))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_another_user_cannot_read_cost_basis(client) -> None:
    owner_token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-api-owner@example.com",
        username="cost-basis-api-owner",
    )
    assert owner_token
    register_user(
        client,
        email="cost-basis-api-other@example.com",
        username="cost-basis-api-other",
    )
    other_token = login_user(client, email="cost-basis-api-other@example.com")

    response = client.get(
        cost_basis_url(portfolio_id),
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_missing_as_of_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-missing-date@example.com",
        username="cost-basis-missing-date",
    )

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/cost-basis",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_invalid_as_of_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-invalid-date@example.com",
        username="cost-basis-invalid-date",
    )

    response = client.get(
        cost_basis_url(portfolio_id, as_of_date="not-a-date"),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_empty_portfolio_returns_complete_empty_items(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-empty@example.com",
        username="cost-basis-empty",
    )

    response = client.get(
        cost_basis_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["as_of_date"] == AS_OF_DATE
    assert body["status"] == "COMPLETE"
    assert body["items"] == []


def test_single_buy_exposes_cost_basis(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-single-buy@example.com",
        username="cost-basis-single-buy",
    )
    asset = create_asset(db_session, asset_code="CBA")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("20.00000000"),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["status"] == "COMPLETE"
    assert item["quantity"] == "10.00000000"
    assert item["total_cost_basis"] == "200.0000000000000000"
    assert item["average_cost_per_unit"] == "20.00000000"


def test_multiple_buy_moving_weighted_average_exposed(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-multiple-buy@example.com",
        username="cost-basis-multiple-buy",
    )
    asset = create_asset(db_session, asset_code="CBB")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        unit_price=Decimal("30.00000000"),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["quantity"] == "20.00000000"
    assert item["total_cost_basis"] == "500.0000000000000000"
    assert item["average_cost_per_unit"] == "25.00000000"


def test_partial_sell_keeps_remaining_average_unchanged(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-partial-sell@example.com",
        username="cost-basis-partial-sell",
    )
    asset = create_asset(db_session, asset_code="CBC")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        unit_price=Decimal("30.00000000"),
    )
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("999.00000000"),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["quantity"] == "10.00000000"
    assert item["total_cost_basis"] == "250.0000000000000000"
    assert item["average_cost_per_unit"] == "25.00000000"


def test_future_buy_after_as_of_date_is_excluded(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-future-buy@example.com",
        username="cost-basis-future-buy",
    )
    asset = create_asset(db_session, asset_code="CBD")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_date=date(2026, 8, 20),
    )
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        unit_price=Decimal("30.00000000"),
        transaction_date=date(2026, 8, 27),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["quantity"] == "5.00000000"
    assert item["total_cost_basis"] == "50.0000000000000000"
    assert item["average_cost_per_unit"] == "10.00000000"


def test_future_sell_after_as_of_date_does_not_change_historical_result(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-future-sell@example.com",
        username="cost-basis-future-sell",
    )
    asset = create_asset(db_session, asset_code="CBE")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        unit_price=Decimal("999.00000000"),
        transaction_date=date(2026, 8, 27),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["quantity"] == "10.00000000"
    assert item["total_cost_basis"] == "200.0000000000000000"
    assert item["average_cost_per_unit"] == "20.00000000"


def test_fully_sold_asset_is_omitted(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-full-sell@example.com",
        username="cost-basis-full-sell",
    )
    asset = create_asset(db_session, asset_code="CBF")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETE"
    assert body["items"] == []


def test_missing_asset_currency_returns_unavailable_item(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-missing-currency@example.com",
        username="cost-basis-missing-currency",
    )
    asset = create_asset(db_session, asset_code="CBG", currency=None)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["status"] == "INCOMPLETE"
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "ASSET_CURRENCY_UNAVAILABLE"
    assert item["total_cost_basis"] is None
    assert item["average_cost_per_unit"] is None


def test_decimal_response_values_are_json_strings_never_floats(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-decimal-strings@example.com",
        username="cost-basis-decimal-strings",
    )
    asset = create_asset(db_session, asset_code="CBH")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("1.23456789"),
        unit_price=Decimal("9.87654321"),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    decimal_fields = [
        item["quantity"],
        item["total_cost_basis"],
        item["average_cost_per_unit"],
    ]
    assert all(isinstance(value, str) for value in decimal_fields)
    assert not any(isinstance(value, float) for value in decimal_fields)


def test_multiple_assets_remain_separate_without_portfolio_total(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-multiple-assets@example.com",
        username="cost-basis-multiple-assets",
    )
    try_asset = create_asset(db_session, asset_code="CBI", currency="TRY")
    usd_asset = create_asset(db_session, asset_code="CBJ", currency="USD")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=try_asset.id,
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("10.00000000"),
    )
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=usd_asset.id,
        quantity=Decimal("3.00000000"),
        unit_price=Decimal("7.00000000"),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert "total_cost_basis" not in body
    assert len(body["items"]) == 2
    assert body["items"][0]["asset_currency"] == "TRY"
    assert body["items"][0]["total_cost_basis"] == "20.0000000000000000"
    assert body["items"][1]["asset_currency"] == "USD"
    assert body["items"][1]["total_cost_basis"] == "21.0000000000000000"


def test_non_tefas_manual_asset_with_known_currency_works(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="cost-basis-manual-asset@example.com",
        username="cost-basis-manual-asset",
    )
    asset = create_asset(
        db_session,
        asset_code="MSFT",
        asset_name="Microsoft",
        asset_type="STOCK",
        fund_kind=None,
        currency="USD",
        data_source="MANUAL",
    )
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("100.00000000"),
    )

    response = client.get(cost_basis_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["asset_code"] == "MSFT"
    assert item["asset_currency"] == "USD"
    assert item["total_cost_basis"] == "200.0000000000000000"
    assert item["average_cost_per_unit"] == "100.00000000"