from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.exchange_rate import ExchangeRate
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.model.transaction import Transaction


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
VALUATION_DATE = "2026-08-26"


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


def create_portfolio(
    client,
    token: str,
    *,
    name: str = "Valuation Portfolio",
    base_currency: str | None = None,
):
    payload = {"name": name}
    if base_currency is not None:
        payload["base_currency"] = base_currency
    return client.post(
        "/api/v1/portfolios",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def valuation_url(portfolio_id: int, valuation_date: str = VALUATION_DATE) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/valuation?valuation_date={valuation_date}"


def create_tefas_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    fund_kind: str | None = "YAT",
    currency: str | None = "TRY",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Example Fund",
        asset_type="FUND",
        fund_kind=fund_kind,
        currency=currency,
        data_source="TEFAS",
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
    unit_price: Decimal = Decimal("1.00000000"),
    transaction_currency: str | None = None,
    transaction_date: date = date(2026, 8, 20),
) -> Transaction:
    transaction = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=unit_price,
        transaction_currency=transaction_currency,
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
    data_date: date = date(2026, 8, 26),
    price: Decimal = Decimal("12.34567890"),
    exchange_bulletin_price: Decimal | None = None,
) -> TefasFundDailyData:
    daily_data = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("12345.6700"),
        exchange_bulletin_price=exchange_bulletin_price,
    )
    db_session.add(daily_data)
    db_session.commit()
    db_session.refresh(daily_data)
    return daily_data


def add_exchange_rate(
    db_session: Session,
    *,
    base_currency: str = "USD",
    quote_currency: str = "TRY",
    rate_date: date = date(2026, 8, 25),
    forex_buying: Decimal = Decimal("40.00000000"),
    forex_selling: Decimal = Decimal("42.00000000"),
    source: str = "TCMB",
) -> ExchangeRate:
    exchange_rate = ExchangeRate(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate_date=rate_date,
        forex_buying=forex_buying,
        forex_selling=forex_selling,
        source=source,
    )
    db_session.add(exchange_rate)
    db_session.commit()
    db_session.refresh(exchange_rate)
    return exchange_rate


def create_owner_portfolio(client, *, email: str, username: str, base_currency: str = "TRY") -> tuple[str, int]:
    register_user(client, email=email, username=username)
    token = login_user(client, email=email)
    portfolio_response = create_portfolio(
        client,
        token,
        base_currency=base_currency,
    )
    assert portfolio_response.status_code == 201
    return token, portfolio_response.json()["id"]


def test_portfolio_valuation_requires_authentication(client) -> None:
    response = client.get(valuation_url(999999))

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_another_user_cannot_read_portfolio_valuation(client) -> None:
    owner_token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-owner@example.com",
        username="valuation-owner",
    )
    assert owner_token
    register_user(client, email="valuation-other@example.com", username="valuation-other")
    other_token = login_user(client, email="valuation-other@example.com")

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_missing_valuation_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-missing-date@example.com",
        username="valuation-missing-date",
    )

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/valuation",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_invalid_valuation_date_returns_422(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-invalid-date@example.com",
        username="valuation-invalid-date",
    )

    response = client.get(
        valuation_url(portfolio_id, valuation_date="not-a-date"),
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_empty_portfolio_returns_complete_zero_value(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-empty@example.com",
        username="valuation-empty",
    )

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["base_currency"] == "TRY"
    assert body["valuation_date"] == VALUATION_DATE
    assert body["status"] == "COMPLETE"
    assert body["total_market_value"] == "0"
    assert body["items"] == []


def test_complete_try_holding_exposes_nav_identity_fx_and_market_value(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-complete@example.com",
        username="valuation-complete",
    )
    asset = create_tefas_asset(db_session, asset_code="VAA")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
    )
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("3.25000000"))

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETE"
    assert body["total_market_value"] == "32.5000000000000000"
    item = body["items"][0]
    assert item["asset_id"] == asset.id
    assert item["asset_code"] == "VAA"
    assert item["quantity"] == "10.00000000"
    assert item["price"] == "3.25000000"
    assert item["price_date"] == VALUATION_DATE
    assert item["price_kind"] == "NAV"
    assert item["price_source"] == "TEFAS"
    assert item["fx_rate"] == "1"
    assert item["fx_rate_date"] is None
    assert item["fx_rate_kind"] == "IDENTITY"
    assert item["fx_source"] == "IDENTITY"
    assert item["native_market_value"] == "32.5000000000000000"
    assert item["market_value"] == "32.5000000000000000"
    assert item["weight"] == "1"


def test_decimal_values_serialize_as_strings_never_floats(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-decimal@example.com",
        username="valuation-decimal",
    )
    asset = create_tefas_asset(db_session, asset_code="VAB")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("1.23456789"),
    )
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("9.87654321"))

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    decimal_fields = [
        body["total_market_value"],
        item["quantity"],
        item["price"],
        item["fx_rate"],
        item["native_market_value"],
        item["market_value"],
        item["weight"],
    ]
    assert all(isinstance(value, str) for value in decimal_fields)
    assert not any(isinstance(value, float) for value in decimal_fields)


def test_valuation_date_is_returned_unchanged(client) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-date-return@example.com",
        username="valuation-date-return",
    )

    response = client.get(
        valuation_url(portfolio_id, valuation_date="2026-08-24"),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["valuation_date"] == "2026-08-24"


def test_latest_tefas_price_on_or_before_valuation_date_is_exposed(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-latest-price@example.com",
        username="valuation-latest-price",
    )
    asset = create_tefas_asset(db_session, asset_code="VAC")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 20),
        price=Decimal("9.00000000"),
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 25),
        price=Decimal("10.00000000"),
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 27),
        price=Decimal("100.00000000"),
    )

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["price"] == "10.00000000"
    assert item["price_date"] == "2026-08-25"


def test_future_buy_after_valuation_date_is_excluded(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-future-buy@example.com",
        username="valuation-future-buy",
    )
    asset = create_tefas_asset(db_session, asset_code="VAD")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        transaction_date=date(2026, 8, 27),
    )
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total_market_value"] == "0"


def test_future_sell_after_valuation_date_does_not_reduce_historical_quantity(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-future-sell@example.com",
        username="valuation-future-sell",
    )
    asset = create_tefas_asset(db_session, asset_code="VAE")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        transaction_date=date(2026, 8, 20),
    )
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        transaction_date=date(2026, 8, 27),
    )
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["quantity"] == "10.00000000"
    assert item["market_value"] == "20.0000000000000000"


def test_byf_uses_exchange_bulletin_price_and_exchange_market_kind(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-byf@example.com",
        username="valuation-byf",
    )
    asset = create_tefas_asset(db_session, asset_code="VAF", fund_kind="BYF")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=Decimal("11.25000000"),
    )

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["price"] == "11.25000000"
    assert item["price_kind"] == "EXCHANGE_MARKET"
    assert item["market_value"] == "112.5000000000000000"


def test_missing_byf_exchange_bulletin_price_is_incomplete(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-byf-missing@example.com",
        username="valuation-byf-missing",
    )
    asset = create_tefas_asset(db_session, asset_code="VAG", fund_kind="BYF")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=None,
    )

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["status"] == "INCOMPLETE"
    assert body["total_market_value"] is None
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "PRICE_UNAVAILABLE"
    assert item["price"] is None


def test_missing_asset_currency_is_incomplete_and_preserves_price_provenance(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-missing-currency@example.com",
        username="valuation-missing-currency",
    )
    asset = create_tefas_asset(db_session, asset_code="VAH", currency=None)
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_currency="TRY",
    )
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("5.00000000"))

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["status"] == "INCOMPLETE"
    assert body["total_market_value"] is None
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "ASSET_CURRENCY_UNAVAILABLE"
    assert item["price"] == "5.00000000"
    assert item["price_date"] == VALUATION_DATE
    assert item["price_kind"] == "NAV"
    assert item["price_source"] == "TEFAS"
    assert item["native_market_value"] is None
    assert item["market_value"] is None
    assert item["weight"] is None


def test_missing_fx_is_incomplete_and_preserves_native_value_and_price_provenance(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-missing-fx@example.com",
        username="valuation-missing-fx",
    )
    asset = create_tefas_asset(db_session, asset_code="VAI", currency="USD")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    item = body["items"][0]
    assert body["status"] == "INCOMPLETE"
    assert body["total_market_value"] is None
    assert item["status"] == "UNAVAILABLE"
    assert item["unavailable_reason"] == "FX_UNAVAILABLE"
    assert item["price"] == "2.00000000"
    assert item["price_kind"] == "NAV"
    assert item["price_source"] == "TEFAS"
    assert item["native_market_value"] == "20.0000000000000000"
    assert item["fx_rate"] is None
    assert item["market_value"] is None
    assert item["weight"] is None


def test_complete_item_retains_market_value_when_portfolio_is_incomplete(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-partial-items@example.com",
        username="valuation-partial-items",
    )
    complete_asset = create_tefas_asset(db_session, asset_code="VAJ")
    missing_price_asset = create_tefas_asset(db_session, asset_code="VAK")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=complete_asset.id,
        quantity=Decimal("2.00000000"),
    )
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=missing_price_asset.id,
        quantity=Decimal("3.00000000"),
    )
    add_daily_data(db_session, asset_id=complete_asset.id, price=Decimal("7.00000000"))

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INCOMPLETE"
    assert body["total_market_value"] is None
    assert len(body["items"]) == 2
    complete_item = body["items"][0]
    unavailable_item = body["items"][1]
    assert complete_item["status"] == "COMPLETE"
    assert complete_item["market_value"] == "14.0000000000000000"
    assert complete_item["weight"] is None
    assert unavailable_item["status"] == "UNAVAILABLE"
    assert unavailable_item["unavailable_reason"] == "PRICE_UNAVAILABLE"
    assert unavailable_item["weight"] is None


def test_unavailable_positive_holding_is_not_hidden_from_items(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-unavailable-visible@example.com",
        username="valuation-unavailable-visible",
    )
    asset = create_tefas_asset(db_session, asset_code="VAL")
    add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        quantity=Decimal("4.00000000"),
    )

    response = client.get(
        valuation_url(portfolio_id),
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INCOMPLETE"
    assert len(body["items"]) == 1
    assert body["items"][0]["asset_id"] == asset.id
    assert body["items"][0]["unavailable_reason"] == "PRICE_UNAVAILABLE"
    assert body["items"][0]["weight"] is None

def test_complete_multi_holding_portfolio_exposes_weight_ratios(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="valuation-api-weights@example.com", username="valuation-api-weights")
    first_asset = create_tefas_asset(db_session, asset_code="WBA")
    second_asset = create_tefas_asset(db_session, asset_code="WBB")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=first_asset.id, quantity=Decimal("5.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=second_asset.id, quantity=Decimal("15.00000000"))
    add_daily_data(db_session, asset_id=first_asset.id, price=Decimal("5.00000000"))
    add_daily_data(db_session, asset_id=second_asset.id, price=Decimal("5.00000000"))

    response = client.get(valuation_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["market_value"] == "25.0000000000000000"
    assert items[1]["market_value"] == "75.0000000000000000"
    assert items[0]["weight"] == "0.25"
    assert items[1]["weight"] == "0.75"


def test_fx_converted_holding_weight_uses_converted_market_value(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="valuation-api-fx-weight@example.com", username="valuation-api-fx-weight")
    try_asset = create_tefas_asset(db_session, asset_code="WBC", currency="TRY")
    usd_asset = create_tefas_asset(db_session, asset_code="WBD", currency="USD")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=try_asset.id, quantity=Decimal("50.00000000"))
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=usd_asset.id, quantity=Decimal("1.00000000"))
    add_daily_data(db_session, asset_id=try_asset.id, price=Decimal("1.00000000"))
    add_daily_data(db_session, asset_id=usd_asset.id, price=Decimal("5.00000000"))
    add_exchange_rate(db_session, base_currency="USD", forex_buying=Decimal("9.00000000"), forex_selling=Decimal("11.00000000"))

    response = client.get(valuation_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[1]["native_market_value"] == "5.0000000000000000"
    assert items[1]["market_value"] == "50.000000000000000000000000"
    assert items[1]["weight"] == "0.5"


def test_incomplete_portfolio_exposes_null_weight_for_all_items(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="valuation-api-incomplete-weights@example.com", username="valuation-api-incomplete-weights")
    complete_asset = create_tefas_asset(db_session, asset_code="WBE")
    unavailable_asset = create_tefas_asset(db_session, asset_code="WBF")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=complete_asset.id)
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=unavailable_asset.id)
    add_daily_data(db_session, asset_id=complete_asset.id, price=Decimal("2.00000000"))

    response = client.get(valuation_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "INCOMPLETE"
    assert body["total_market_value"] is None
    assert body["items"][0]["status"] == "COMPLETE"
    assert body["items"][0]["market_value"] == "20.0000000000000000"
    assert all(item["weight"] is None for item in body["items"])


def test_weight_is_serialized_as_string_never_float(client, db_session: Session) -> None:
    token, portfolio_id = create_owner_portfolio(client, email="valuation-api-weight-string@example.com", username="valuation-api-weight-string")
    asset = create_tefas_asset(db_session, asset_code="WBG")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))

    response = client.get(valuation_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    weight = response.json()["items"][0]["weight"]
    assert weight == "1"
    assert isinstance(weight, str)
    assert not isinstance(weight, float)


def test_portfolio_valuation_api_serializes_market_data_freshness(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-freshness-api@example.com",
        username="valuation-freshness-api",
        base_currency="TRY",
    )
    asset = create_tefas_asset(db_session, asset_code="VFH", currency="USD")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 25),
        price=Decimal("2.00000000"),
    )
    add_exchange_rate(
        db_session,
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 24),
    )

    response = client.get(valuation_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["price_freshness"] == {
        "requested_date": "2026-08-26",
        "effective_date": "2026-08-25",
        "age_days": 1,
        "status": "STALE",
    }
    assert item["fx_freshness"] == {
        "requested_date": "2026-08-26",
        "effective_date": "2026-08-24",
        "age_days": 2,
        "status": "STALE",
    }


def test_portfolio_valuation_api_serializes_identity_fx_freshness_as_not_applicable(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = create_owner_portfolio(
        client,
        email="valuation-identity-freshness-api@example.com",
        username="valuation-identity-freshness-api",
    )
    asset = create_tefas_asset(db_session, asset_code="VFI")
    add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    add_daily_data(db_session, asset_id=asset.id)

    response = client.get(valuation_url(portfolio_id), headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["items"][0]["fx_freshness"] == {
        "requested_date": "2026-08-26",
        "effective_date": None,
        "age_days": None,
        "status": "NOT_APPLICABLE",
    }
