from __future__ import annotations

from sqlalchemy.orm import Session

from src.model.asset import Asset


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
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def create_portfolio(client, token: str, *, name: str):
    return client.post(
        "/api/v1/portfolios",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )


def create_tefas_asset(db_session: Session, *, asset_code: str = "AAL") -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def create_transaction(
    client,
    token: str,
    *,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str,
    quantity: str,
    unit_price: str = "20.00000000",
    transaction_currency: str = "TRY",
    transaction_date: str = "2026-08-25",
):
    return client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset_id,
            "transaction_type": transaction_type,
            "quantity": quantity,
            "unit_price": unit_price,
            "transaction_currency": transaction_currency,
            "transaction_date": transaction_date,
        },
        headers={"Authorization": f"Bearer {token}"},
    )


def test_authenticated_owner_can_list_holdings(client, db_session: Session) -> None:
    register_user(client, email="holding-api@example.com", username="holding-api")
    token = login_user(client, email="holding-api@example.com")
    portfolio_response = create_portfolio(client, token, name="Holding Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session, asset_code="HAA")
    buy_response = create_transaction(
        client,
        token,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity="10.00000000",
    )
    assert buy_response.status_code == 201
    sell_response = create_transaction(
        client,
        token,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity="4.00000000",
    )
    assert sell_response.status_code == 201

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["asset_id"] == asset.id
    assert item["asset_code"] == asset.asset_code
    assert item["asset_name"] == asset.asset_name
    assert item["asset_type"] == asset.asset_type
    assert item["fund_kind"] == asset.fund_kind
    assert item["currency"] == asset.currency
    assert item["data_source"] == asset.data_source
    assert item["quantity"] == "6.00000000"


def test_multiple_assets_are_returned_with_independent_quantities_in_asset_id_order(
    client,
    db_session: Session,
) -> None:
    register_user(client, email="holding-multi@example.com", username="holding-multi")
    token = login_user(client, email="holding-multi@example.com")
    portfolio_response = create_portfolio(client, token, name="Multi Holding Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    first_asset = create_tefas_asset(db_session, asset_code="HAB")
    second_asset = create_tefas_asset(db_session, asset_code="HAC")
    assert first_asset.id < second_asset.id
    assert create_transaction(
        client,
        token,
        portfolio_id=portfolio_id,
        asset_id=second_asset.id,
        transaction_type="BUY",
        quantity="8.00000000",
    ).status_code == 201
    assert create_transaction(
        client,
        token,
        portfolio_id=portfolio_id,
        asset_id=first_asset.id,
        transaction_type="BUY",
        quantity="5.00000000",
    ).status_code == 201
    assert create_transaction(
        client,
        token,
        portfolio_id=portfolio_id,
        asset_id=second_asset.id,
        transaction_type="SELL",
        quantity="3.00000000",
    ).status_code == 201

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["asset_id"] for item in body["items"]] == [
        first_asset.id,
        second_asset.id,
    ]
    assert [item["quantity"] for item in body["items"]] == [
        "5.00000000",
        "5.00000000",
    ]


def test_fully_sold_asset_is_omitted(client, db_session: Session) -> None:
    register_user(client, email="holding-sold@example.com", username="holding-sold")
    token = login_user(client, email="holding-sold@example.com")
    portfolio_response = create_portfolio(client, token, name="Sold Holding Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session, asset_code="HAD")
    assert create_transaction(
        client,
        token,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity="5.00000000",
    ).status_code == 201
    assert create_transaction(
        client,
        token,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity="5.00000000",
    ).status_code == 201

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_another_user_cannot_read_portfolio_holdings(client) -> None:
    register_user(client, email="holding-owner@example.com", username="holding-owner")
    owner_token = login_user(client, email="holding-owner@example.com")
    portfolio_response = create_portfolio(client, owner_token, name="Owner Holdings")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    register_user(client, email="holding-other@example.com", username="holding-other")
    other_token = login_user(client, email="holding-other@example.com")

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_list_holdings_requires_authentication(client) -> None:
    response = client.get("/api/v1/portfolios/999999/holdings")

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL