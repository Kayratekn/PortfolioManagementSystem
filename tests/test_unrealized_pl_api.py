from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
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
    name: str = "Unrealized P/L Portfolio",
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


def create_owner_portfolio(
    client,
    *,
    email: str,
    username: str,
    base_currency: str | None = None,
) -> tuple[str, int]:
    register_user(client, email=email, username=username)
    token = login_user(client, email=email)
    portfolio_response = create_portfolio(
        client,
        token,
        base_currency=base_currency,
    )
    assert portfolio_response.status_code == 201
    return token, portfolio_response.json()["id"]


def unrealized_pl_url(portfolio_id: int, as_of_date: str = AS_OF_DATE) -> str:
    return (
        f"/api/v1/portfolios/{portfolio_id}/unrealized-pl"
        f"?as_of_date={as_of_date}"
    )


def create_asset(
    db_session: Session,
    *,
    asset_code: str = "UPL",
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


def add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date = date(2026, 8, 25),
    price: Decimal = Decimal("25.00000000"),
    exchange_bulletin_price: Decimal | None = None,
) -> TefasFundDailyData:
    daily_data = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("25000.0000"),
        exchange_bulletin_price=exchange_bulletin_price,
    )
    db_session.add(daily_data)
    db_session.commit()
    db_session.refresh(daily_data)
    return daily_data


def only_item(body: dict) -> dict:
    assert len(body["items"]) == 1
    return body["items"][0]


def test_unrealized_pl_requires_authentication(client) -> None:
    response = client.get(unrealized_pl_url(999999))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_another_user_cannot_read_unrealized_pl(client) -> None:
    owner_token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-api-owner@example.com",
        username="unrealized-pl-api-owner",
    )
    assert owner_token
    register_user(
        client,
        email="unrealized-pl-api-other@example.com",
        username="unrealized-pl-api-other",
    )
    other_token = login_user(client, email="unrealized-pl-api-other@example.com")

    response = client.get(
        unrealized_pl_url(portfolio_id),
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_missing_as_of_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-missing-date@example.com",
        username="unrealized-pl-missing-date",
    )

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/unrealized-pl",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_invalid_as_of_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-invalid-date@example.com",
        username="unrealized-pl-invalid-date",
    )

    response = client.get(
        unrealized_pl_url(portfolio_id, as_of_date="not-a-date"),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_empty_portfolio_returns_complete_empty_items(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-empty@example.com",
        username="unrealized-pl-empty",
    )

    response = client.get(
        unrealized_pl_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["as_of_date"] == AS_OF_DATE
    assert body["status"] == "COMPLETE"
    assert body["items"] == []


def test_positive_unrealized_pl(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-positive@example.com",
        username="unrealized-pl-positive",
    )
    asset = create_asset(db_session, asset_code="UPA")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = only_item(body)
    assert body["status"] == "COMPLETE"
    assert item["native_market_value"] == "250.0000000000000000"
    assert item["native_unrealized_pl"] == "50.0000000000000000"


def test_zero_unrealized_pl(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-zero@example.com",
        username="unrealized-pl-zero",
    )
    asset = create_asset(db_session, asset_code="UPB")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("20.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert Decimal(item["native_unrealized_pl"]) == Decimal("0")


def test_negative_unrealized_pl(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-negative@example.com",
        username="unrealized-pl-negative",
    )
    asset = create_asset(db_session, asset_code="UPC")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("15.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["native_market_value"] == "150.0000000000000000"
    assert item["native_unrealized_pl"] == "-50.0000000000000000"


def test_multiple_buys_expose_moving_weighted_average_cost_basis(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-mwac@example.com",
        username="unrealized-pl-mwac",
    )
    asset = create_asset(db_session, asset_code="UPD")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        unit_price=Decimal("30.00000000"),
    )
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("40.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["quantity"] == "20.00000000"
    assert item["total_cost_basis"] == "500.0000000000000000"
    assert item["average_cost_per_unit"] == "25.00000000"
    assert item["native_market_value"] == "800.0000000000000000"
    assert item["native_unrealized_pl"] == "300.0000000000000000"


def test_partial_sell_keeps_cost_basis_and_ignores_sell_unit_price(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-sell@example.com",
        username="unrealized-pl-sell",
    )
    asset = create_asset(db_session, asset_code="UPE")
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
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("40.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["quantity"] == "10.00000000"
    assert item["total_cost_basis"] == "250.0000000000000000"
    assert item["average_cost_per_unit"] == "25.00000000"
    assert item["native_market_value"] == "400.0000000000000000"
    assert item["native_unrealized_pl"] == "150.0000000000000000"


def test_future_buy_is_excluded(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-future-buy@example.com",
        username="unrealized-pl-future-buy",
    )
    asset = create_asset(db_session, asset_code="UPF")
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
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("20.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["quantity"] == "5.00000000"
    assert item["total_cost_basis"] == "50.0000000000000000"
    assert item["native_market_value"] == "100.0000000000000000"
    assert item["native_unrealized_pl"] == "50.0000000000000000"


def test_future_sell_is_excluded_from_historical_result(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-future-sell@example.com",
        username="unrealized-pl-future-sell",
    )
    asset = create_asset(db_session, asset_code="UPG")
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
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["quantity"] == "10.00000000"
    assert item["total_cost_basis"] == "200.0000000000000000"
    assert item["native_unrealized_pl"] == "50.0000000000000000"


def test_fully_sold_asset_is_omitted(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-full-sell@example.com",
        username="unrealized-pl-full-sell",
    )
    asset = create_asset(db_session, asset_code="UPH")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
    )
    add_daily_data(db_session, asset_id=asset.id)

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETE"
    assert body["items"] == []


def test_latest_price_on_or_before_as_of_date_is_used(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-latest-price@example.com",
        username="unrealized-pl-latest-price",
    )
    asset = create_asset(db_session, asset_code="UPI")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 22),
        price=Decimal("21.00000000"),
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 24),
        price=Decimal("23.00000000"),
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 27),
        price=Decimal("99.00000000"),
    )

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["price"] == "23.00000000"
    assert item["price_date"] == "2026-08-24"
    assert item["native_unrealized_pl"] == "30.0000000000000000"


def test_yat_uses_nav(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-yat@example.com",
        username="unrealized-pl-yat",
    )
    asset = create_asset(db_session, asset_code="UPJ", fund_kind="YAT")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["price"] == "25.00000000"
    assert item["price_kind"] == "NAV"
    assert item["price_source"] == "TEFAS"


def test_byf_uses_exchange_bulletin_price(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-byf@example.com",
        username="unrealized-pl-byf",
    )
    asset = create_asset(db_session, asset_code="UPK", fund_kind="BYF")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=Decimal("30.00000000"),
    )

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    assert item["price"] == "30.00000000"
    assert item["price_kind"] == "EXCHANGE_MARKET"
    assert item["native_market_value"] == "300.0000000000000000"
    assert item["native_unrealized_pl"] == "100.0000000000000000"


def test_byf_missing_bulletin_price_is_price_unavailable_without_nav_fallback(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-byf-no-fallback@example.com",
        username="unrealized-pl-byf-no-fallback",
    )
    asset = create_asset(db_session, asset_code="UPL", fund_kind="BYF")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=None,
    )

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = only_item(body)
    assert body["status"] == "INCOMPLETE"
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "PRICE_UNAVAILABLE"
    assert item["price"] is None
    assert item["native_market_value"] is None
    assert item["native_unrealized_pl"] is None


def test_missing_selected_price_returns_price_unavailable(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-no-price@example.com",
        username="unrealized-pl-no-price",
    )
    asset = create_asset(db_session, asset_code="UPM")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = only_item(body)
    assert body["status"] == "INCOMPLETE"
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "PRICE_UNAVAILABLE"
    assert item["total_cost_basis"] == "200.0000000000000000"
    assert item["average_cost_per_unit"] == "20.00000000"
    assert item["price"] is None


def test_missing_asset_currency_returns_asset_currency_unavailable(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-missing-currency@example.com",
        username="unrealized-pl-missing-currency",
    )
    asset = create_asset(db_session, asset_code="UPN", currency=None)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = only_item(body)
    assert body["status"] == "INCOMPLETE"
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "ASSET_CURRENCY_UNAVAILABLE"
    assert item["total_cost_basis"] is None
    assert item["average_cost_per_unit"] is None
    assert item["native_market_value"] is None
    assert item["native_unrealized_pl"] is None


def test_manual_non_tefas_asset_returns_unsupported_asset(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-manual@example.com",
        username="unrealized-pl-manual",
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
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = only_item(body)
    assert body["status"] == "INCOMPLETE"
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "UNSUPPORTED_ASSET"
    assert item["total_cost_basis"] == "200.0000000000000000"
    assert item["price"] is None


def test_usd_asset_in_try_portfolio_without_fx_returns_complete_native_pl(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-usd-no-fx@example.com",
        username="unrealized-pl-usd-no-fx",
        base_currency="TRY",
    )
    asset = create_asset(db_session, asset_code="USD", currency="USD")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = only_item(body)
    assert body["status"] == "COMPLETE"
    assert item["asset_currency"] == "USD"
    assert item["native_market_value"] == "250.0000000000000000"
    assert item["native_unrealized_pl"] == "50.0000000000000000"


def test_mixed_complete_unavailable_result_keeps_complete_item_pl(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-mixed@example.com",
        username="unrealized-pl-mixed",
    )
    complete_asset = create_asset(db_session, asset_code="UPO")
    unavailable_asset = create_asset(db_session, asset_code="UPP")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=complete_asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=unavailable_asset.id)
    add_daily_data(
        db_session,
        asset_id=complete_asset.id,
        price=Decimal("25.00000000"),
    )

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    items_by_code = {item["asset_code"]: item for item in body["items"]}
    assert body["status"] == "INCOMPLETE"
    assert items_by_code["UPO"]["status"] == "COMPLETE"
    assert items_by_code["UPO"]["native_unrealized_pl"] == "50.0000000000000000"
    assert items_by_code["UPP"]["status"] == "UNAVAILABLE"
    assert items_by_code["UPP"]["unavailable_reason"] == "PRICE_UNAVAILABLE"


def test_decimal_response_fields_are_json_strings_never_floats(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-decimal-strings@example.com",
        username="unrealized-pl-decimal-strings",
    )
    asset = create_asset(db_session, asset_code="UPQ")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("1.23456789"),
        unit_price=Decimal("9.87654321"),
    )
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("11.11111111"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = only_item(response.json())
    decimal_fields = [
        item["quantity"],
        item["total_cost_basis"],
        item["average_cost_per_unit"],
        item["price"],
        item["native_market_value"],
        item["native_unrealized_pl"],
    ]
    assert all(isinstance(value, str) for value in decimal_fields)
    assert not any(isinstance(value, float) for value in decimal_fields)


def test_response_has_no_portfolio_level_pl_total_or_fx_base_currency_fields(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-no-total-fields@example.com",
        username="unrealized-pl-no-total-fields",
    )
    asset = create_asset(db_session, asset_code="UPR", currency="USD")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    forbidden_body_fields = {
        "base_currency",
        "total_unrealized_pl",
        "portfolio_unrealized_pl",
        "market_value",
        "fx_rate",
        "fx_date",
        "unrealized_pl_percent",
    }
    forbidden_item_fields = {
        "base_currency",
        "market_value",
        "portfolio_market_value",
        "portfolio_unrealized_pl",
        "fx_rate",
        "fx_date",
        "unrealized_pl_percent",
    }
    assert forbidden_body_fields.isdisjoint(body)
    assert forbidden_item_fields.isdisjoint(body["items"][0])


def test_unrealized_pl_api_serializes_price_freshness(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-freshness-api@example.com",
        username="unrealized-pl-freshness-api",
    )
    asset = create_asset(db_session, asset_code="UPF")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 24),
        price=Decimal("25.00000000"),
    )

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    assert only_item(response.json())["price_freshness"] == {
        "requested_date": "2026-08-25",
        "effective_date": "2026-08-24",
        "age_days": 1,
        "status": "STALE",
    }


def test_unrealized_pl_api_serializes_missing_price_freshness_as_unavailable(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="unrealized-pl-unavailable-freshness-api@example.com",
        username="unrealized-pl-unavailable-freshness-api",
    )
    asset = create_asset(db_session, asset_code="UPU")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)

    response = client.get(unrealized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    assert only_item(response.json())["price_freshness"] == {
        "requested_date": "2026-08-25",
        "effective_date": None,
        "age_days": None,
        "status": "UNAVAILABLE",
    }
