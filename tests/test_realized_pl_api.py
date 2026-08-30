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


def create_portfolio(client, token: str, name: str = "Realized P/L Portfolio"):
    return client.post(
        "/api/v1/portfolios",
        json={"name": name},
        headers=auth_headers(token),
    )


def create_owner_portfolio(client, *, email: str, username: str) -> tuple[str, int]:
    register_user(client, email=email, username=username)
    token = login_user(client, email=email)
    portfolio_response = create_portfolio(client, token)
    assert portfolio_response.status_code == 201
    return token, portfolio_response.json()["id"]


def realized_pl_url(portfolio_id: int, as_of_date: str = AS_OF_DATE) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/realized-pl?as_of_date={as_of_date}"


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


def test_realized_pl_requires_authentication(client) -> None:
    response = client.get(realized_pl_url(999999))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_another_user_cannot_read_realized_pl(client) -> None:
    owner_token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-api-owner@example.com",
        username="realized-api-owner",
    )
    assert owner_token
    register_user(
        client,
        email="realized-api-other@example.com",
        username="realized-api-other",
    )
    other_token = login_user(client, email="realized-api-other@example.com")

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(other_token))

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_missing_as_of_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-missing-date@example.com",
        username="realized-missing-date",
    )

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/realized-pl",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_invalid_as_of_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-invalid-date@example.com",
        username="realized-invalid-date",
    )

    response = client.get(
        realized_pl_url(portfolio_id, as_of_date="not-a-date"),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_no_sells_returns_complete_empty_items(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-empty@example.com",
        username="realized-empty",
    )
    asset = create_asset(db_session, asset_code="RPE")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["as_of_date"] == AS_OF_DATE
    assert body["status"] == "COMPLETE"
    assert body["items"] == []


def test_profitable_realized_pl_exposed(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-profit@example.com",
        username="realized-profit",
    )
    asset = create_asset(db_session, asset_code="RPP")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        unit_price=Decimal("30.00000000"),
    )

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["status"] == "COMPLETE"
    assert item["asset_id"] == asset.id
    assert item["asset_code"] == "RPP"
    assert item["asset_currency"] == "TRY"
    assert item["status"] == "COMPLETE"
    assert item["unavailable_reason"] is None
    assert item["sold_quantity"] == "4.00000000"
    assert item["realized_proceeds"] == "120.0000000000000000"
    assert item["realized_cost_basis"] == "80.0000000000000000"
    assert item["native_realized_pl"] == "40.0000000000000000"


def test_zero_realized_pl(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-zero@example.com",
        username="realized-zero",
    )
    asset = create_asset(db_session, asset_code="RPZ")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("4.00000000"), unit_price=Decimal("20.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    assert Decimal(response.json()["items"][0]["native_realized_pl"]) == Decimal("0")


def test_negative_realized_pl(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-loss@example.com",
        username="realized-loss",
    )
    asset = create_asset(db_session, asset_code="RPL")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("4.00000000"), unit_price=Decimal("15.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["items"][0]["native_realized_pl"] == "-20.0000000000000000"


def test_multiple_buys_to_sell_exposes_mwac_realized_values(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-mwac@example.com",
        username="realized-mwac",
    )
    asset = create_asset(db_session, asset_code="RPM")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, unit_price=Decimal("20.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, unit_price=Decimal("30.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("4.00000000"), unit_price=Decimal("40.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["realized_proceeds"] == "160.0000000000000000"
    assert item["realized_cost_basis"] == "100.0000000000000000"
    assert item["native_realized_pl"] == "60.0000000000000000"


def test_multiple_sells_accumulate_values(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-multiple-sells@example.com",
        username="realized-multiple-sells",
    )
    asset = create_asset(db_session, asset_code="RMS")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("2.00000000"), unit_price=Decimal("30.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("3.00000000"), unit_price=Decimal("10.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sold_quantity"] == "5.00000000"
    assert item["realized_proceeds"] == "90.0000000000000000"
    assert item["realized_cost_basis"] == "100.0000000000000000"
    assert item["native_realized_pl"] == "-10.0000000000000000"


def test_fully_sold_asset_remains_present(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-full-sell@example.com",
        username="realized-full-sell",
    )
    asset = create_asset(db_session, asset_code="RFS")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL")

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["asset_id"] == asset.id
    assert body["items"][0]["sold_quantity"] == "10.00000000"


def test_full_exit_reentry_later_sell_exposes_cumulative_values(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-reentry@example.com",
        username="realized-reentry",
    )
    asset = create_asset(db_session, asset_code="RRE")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, unit_price=Decimal("20.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", unit_price=Decimal("25.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, quantity=Decimal("5.00000000"), unit_price=Decimal("30.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("2.00000000"), unit_price=Decimal("40.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sold_quantity"] == "12.00000000"
    assert item["realized_proceeds"] == "330.0000000000000000"
    assert item["realized_cost_basis"] == "260.0000000000000000"
    assert item["native_realized_pl"] == "70.0000000000000000"


def test_future_buy_and_future_sell_excluded_exact_as_of_included(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-historical@example.com",
        username="realized-historical",
    )
    asset = create_asset(db_session, asset_code="RHI")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_date=date(2026, 8, 24))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("2.00000000"), unit_price=Decimal("30.00000000"), transaction_date=date(2026, 8, 25))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, quantity=Decimal("100.00000000"), unit_price=Decimal("1.00000000"), transaction_date=date(2026, 8, 26))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("3.00000000"), unit_price=Decimal("40.00000000"), transaction_date=date(2026, 8, 26))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sold_quantity"] == "2.00000000"
    assert item["realized_proceeds"] == "60.0000000000000000"
    assert item["realized_cost_basis"] == "40.0000000000000000"


def test_multiple_assets_remain_separate_and_buy_only_omitted(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-multiple-assets@example.com",
        username="realized-multiple-assets",
    )
    first_asset = create_asset(db_session, asset_code="RAA")
    second_asset = create_asset(db_session, asset_code="RAB", currency="USD")
    buy_only_asset = create_asset(db_session, asset_code="RAC")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=first_asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=first_asset.id, transaction_type="SELL", quantity=Decimal("5.00000000"), unit_price=Decimal("30.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=second_asset.id, quantity=Decimal("3.00000000"), unit_price=Decimal("7.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=second_asset.id, transaction_type="SELL", quantity=Decimal("1.00000000"), unit_price=Decimal("10.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=buy_only_asset.id)

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert [item["asset_id"] for item in body["items"]] == [first_asset.id, second_asset.id]
    assert body["items"][0]["native_realized_pl"] == "50.0000000000000000"
    assert body["items"][1]["asset_currency"] == "USD"
    assert body["items"][1]["native_realized_pl"] == "3.0000000000000000"


def test_missing_currency_returns_incomplete_unavailable_item(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-missing-currency@example.com",
        username="realized-missing-currency",
    )
    asset = create_asset(db_session, asset_code="RNC", currency=None)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("4.00000000"), unit_price=Decimal("30.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["status"] == "INCOMPLETE"
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "ASSET_CURRENCY_UNAVAILABLE"
    assert item["sold_quantity"] == "4.00000000"
    assert item["realized_proceeds"] is None
    assert item["realized_cost_basis"] is None
    assert item["native_realized_pl"] is None


def test_complete_item_remains_complete_when_another_item_is_unavailable(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-mixed@example.com",
        username="realized-mixed",
    )
    complete_asset = create_asset(db_session, asset_code="RCO")
    unavailable_asset = create_asset(db_session, asset_code="RUN", currency=None)
    for asset in (complete_asset, unavailable_asset):
        add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
        add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("5.00000000"), unit_price=Decimal("30.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    complete_item, unavailable_item = body["items"]
    assert body["status"] == "INCOMPLETE"
    assert complete_item["status"] == "COMPLETE"
    assert complete_item["native_realized_pl"] == "50.0000000000000000"
    assert unavailable_item["status"] == "UNAVAILABLE"


def test_manual_non_tefas_asset_with_known_currency_works(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-manual@example.com",
        username="realized-manual",
    )
    asset = create_asset(db_session, asset_code="MSFT", asset_name="Microsoft", asset_type="STOCK", fund_kind=None, currency="USD", data_source="MANUAL")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, quantity=Decimal("2.00000000"), unit_price=Decimal("100.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("1.00000000"), unit_price=Decimal("125.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["asset_code"] == "MSFT"
    assert item["asset_currency"] == "USD"
    assert item["native_realized_pl"] == "25.0000000000000000"


def test_decimal_financial_response_values_are_json_strings_never_floats(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-decimal-strings@example.com",
        username="realized-decimal-strings",
    )
    asset = create_asset(db_session, asset_code="RDS")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, quantity=Decimal("1.00000000"), unit_price=Decimal("1.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, quantity=Decimal("2.00000000"), unit_price=Decimal("2.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("1.00000000"), unit_price=Decimal("3.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    decimal_fields = [
        item["sold_quantity"],
        item["realized_proceeds"],
        item["realized_cost_basis"],
        item["native_realized_pl"],
    ]
    assert all(isinstance(value, str) for value in decimal_fields)
    assert not any(isinstance(value, float) for value in decimal_fields)
    assert item["realized_cost_basis"] == "1.666666666666666666666666667"


def test_response_has_no_portfolio_total_or_fx_base_currency_fields(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="realized-no-totals@example.com",
        username="realized-no-totals",
    )
    asset = create_asset(db_session, asset_code="RNT")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("5.00000000"), unit_price=Decimal("30.00000000"))

    response = client.get(realized_pl_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    forbidden_fields = {
        "total_realized_pl",
        "portfolio_realized_pl",
        "base_currency",
        "fx_rate",
        "fx_date",
        "market_value",
        "realized_pl_percent",
    }
    assert not forbidden_fields.intersection(body)
    assert not forbidden_fields.intersection(body["items"][0])
