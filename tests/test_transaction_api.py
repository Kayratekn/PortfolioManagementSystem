from __future__ import annotations

from decimal import Decimal

import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.transaction import Transaction


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


def create_tefas_asset(db_session: Session) -> Asset:
    asset = Asset(
        asset_code="AAL",
        asset_name="Example Fund",
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


def test_authenticated_user_can_create_buy_transaction(client, db_session: Session) -> None:
    register_user(
        client,
        email="transaction-api@example.com",
        username="transaction-api",
    )
    token = login_user(client, email="transaction-api@example.com")
    portfolio_response = create_portfolio(client, token, name="Transaction Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session)

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "BUY",
            "quantity": "10.50000000",
            "unit_price": "25.12345678",
            "transaction_date": "2026-08-25",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["asset_id"] == asset.id
    assert body["transaction_type"] == "BUY"
    assert body["quantity"] == "10.50000000"
    assert body["unit_price"] == "25.12345678"
    assert body["transaction_date"] == "2026-08-25"
    assert body["id"] is not None
    assert body["created_at"] is not None
    assert body["updated_at"] is not None

    db_session.expire_all()
    persisted_transaction = db_session.scalar(
        select(Transaction).where(Transaction.id == body["id"])
    )

    assert persisted_transaction is not None
    assert persisted_transaction.portfolio_id == portfolio_id
    assert persisted_transaction.asset_id == asset.id
    assert persisted_transaction.transaction_type == "BUY"
    assert persisted_transaction.quantity == Decimal("10.50000000")
    assert persisted_transaction.unit_price == Decimal("25.12345678")

def test_user_cannot_create_transaction_for_another_users_portfolio(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="transaction-owner@example.com",
        username="transaction-owner",
    )
    owner_token = login_user(client, email="transaction-owner@example.com")
    portfolio_response = create_portfolio(client, owner_token, name="Owner Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    register_user(
        client,
        email="transaction-other@example.com",
        username="transaction-other",
    )
    other_token = login_user(client, email="transaction-other@example.com")
    asset = create_tefas_asset(db_session)

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "BUY",
            "quantity": "10.50000000",
            "unit_price": "25.12345678",
            "transaction_date": "2026-08-25",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."

    persisted_transaction = db_session.scalar(
        select(Transaction).where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset.id,
        )
    )
    assert persisted_transaction is None

def test_transaction_with_missing_asset_returns_404(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="transaction-missing-asset@example.com",
        username="transaction-missing-asset",
    )
    token = login_user(client, email="transaction-missing-asset@example.com")
    portfolio_response = create_portfolio(client, token, name="Missing Asset Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": 999999,
            "transaction_type": "BUY",
            "quantity": "10.50000000",
            "unit_price": "25.12345678",
            "transaction_date": "2026-08-25",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Asset not found."

    persisted_transaction = db_session.scalar(
        select(Transaction).where(Transaction.portfolio_id == portfolio_id)
    )
    assert persisted_transaction is None


def test_authenticated_user_can_create_valid_sell_transaction(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="transaction-sell@example.com",
        username="transaction-sell",
    )
    token = login_user(client, email="transaction-sell@example.com")
    portfolio_response = create_portfolio(client, token, name="Sell Transaction Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session)

    buy_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "BUY",
            "quantity": "10.00000000",
            "unit_price": "20.00000000",
            "transaction_date": "2026-08-20",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert buy_response.status_code == 201

    sell_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "SELL",
            "quantity": "4.00000000",
            "unit_price": "25.00000000",
            "transaction_date": "2026-08-25",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert sell_response.status_code == 201
    body = sell_response.json()
    assert body["transaction_type"] == "SELL"
    assert body["portfolio_id"] == portfolio_id
    assert body["asset_id"] == asset.id
    assert body["quantity"] == "4.00000000"
    assert body["unit_price"] == "25.00000000"
    assert body["transaction_date"] == "2026-08-25"

    db_session.expire_all()
    persisted_transaction = db_session.scalar(
        select(Transaction).where(Transaction.id == body["id"])
    )
    assert persisted_transaction is not None
    assert persisted_transaction.transaction_type == "SELL"
    assert persisted_transaction.portfolio_id == portfolio_id
    assert persisted_transaction.asset_id == asset.id


def test_sell_greater_than_available_quantity_returns_422(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="transaction-insufficient@example.com",
        username="transaction-insufficient",
    )
    token = login_user(client, email="transaction-insufficient@example.com")
    portfolio_response = create_portfolio(
        client,
        token,
        name="Insufficient Quantity Portfolio",
    )
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session)

    buy_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "BUY",
            "quantity": "10.00000000",
            "unit_price": "20.00000000",
            "transaction_date": "2026-08-20",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert buy_response.status_code == 201
    buy_id = buy_response.json()["id"]

    sell_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "SELL",
            "quantity": "11.00000000",
            "unit_price": "25.00000000",
            "transaction_date": "2026-08-25",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert sell_response.status_code == 422
    assert sell_response.json()["detail"] == "Insufficient quantity for SELL."

    db_session.expire_all()
    sell_transaction = db_session.scalar(
        select(Transaction).where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset.id,
            Transaction.transaction_type == "SELL",
        )
    )
    assert sell_transaction is None

    buy_transaction = db_session.scalar(
        select(Transaction).where(Transaction.id == buy_id)
    )
    assert buy_transaction is not None
    assert buy_transaction.transaction_type == "BUY"


def test_backdated_sell_that_makes_later_balance_negative_returns_422(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="transaction-backdated@example.com",
        username="transaction-backdated",
    )
    token = login_user(client, email="transaction-backdated@example.com")
    portfolio_response = create_portfolio(client, token, name="Backdated Sell Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session)

    buy_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "BUY",
            "quantity": "10.00000000",
            "unit_price": "20.00000000",
            "transaction_date": "2026-08-20",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert buy_response.status_code == 201
    buy_id = buy_response.json()["id"]

    later_sell_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "SELL",
            "quantity": "10.00000000",
            "unit_price": "25.00000000",
            "transaction_date": "2026-08-30",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert later_sell_response.status_code == 201
    later_sell_id = later_sell_response.json()["id"]

    backdated_sell_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "SELL",
            "quantity": "5.00000000",
            "unit_price": "25.00000000",
            "transaction_date": "2026-08-25",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert backdated_sell_response.status_code == 422
    assert backdated_sell_response.json()["detail"] == "Insufficient quantity for SELL."

    db_session.expire_all()
    transactions = db_session.scalars(
        select(Transaction).where(
            Transaction.portfolio_id == portfolio_id,
            Transaction.asset_id == asset.id,
        )
    ).all()
    transaction_ids = {transaction.id for transaction in transactions}

    assert len(transactions) == 2
    assert buy_id in transaction_ids
    assert later_sell_id in transaction_ids
    assert all(
        transaction.quantity != Decimal("5.00000000")
        for transaction in transactions
    )


def test_create_transaction_requires_authentication(
    client,
    db_session: Session,
) -> None:
    asset = create_tefas_asset(db_session)

    response = client.post(
        "/api/v1/portfolios/999999/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "BUY",
            "quantity": "10.00000000",
            "unit_price": "20.00000000",
            "transaction_date": "2026-08-25",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Authentication credentials were not provided or are invalid."
    )

    persisted_transaction = db_session.scalar(select(Transaction))
    assert persisted_transaction is None


def test_invalid_transaction_type_returns_422(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="transaction-invalid-type@example.com",
        username="transaction-invalid-type",
    )
    token = login_user(client, email="transaction-invalid-type@example.com")
    portfolio_response = create_portfolio(client, token, name="Invalid Type Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session)

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json={
            "asset_id": asset.id,
            "transaction_type": "HOLD",
            "quantity": "10.00000000",
            "unit_price": "20.00000000",
            "transaction_date": "2026-08-25",
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

    persisted_transaction = db_session.scalar(
        select(Transaction).where(Transaction.portfolio_id == portfolio_id)
    )
    assert persisted_transaction is None


@pytest.mark.parametrize(
    ("field_name", "field_value"),
    [
        ("quantity", "0"),
        ("quantity", "-1"),
        ("unit_price", "0"),
        ("unit_price", "-1"),
    ],
)
def test_non_positive_transaction_amount_fields_return_422(
    client,
    db_session: Session,
    field_name: str,
    field_value: str,
) -> None:
    case_suffix = f"{field_name}-{field_value.replace('-', 'negative')}"
    register_user(
        client,
        email=f"transaction-{case_suffix}@example.com",
        username=f"transaction-{case_suffix}",
    )
    token = login_user(client, email=f"transaction-{case_suffix}@example.com")
    portfolio_response = create_portfolio(client, token, name="Invalid Amount Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    asset = create_tefas_asset(db_session)
    payload = {
        "asset_id": asset.id,
        "transaction_type": "BUY",
        "quantity": "10.00000000",
        "unit_price": "20.00000000",
        "transaction_date": "2026-08-25",
    }
    payload[field_name] = field_value

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/transactions",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422

    persisted_transaction = db_session.scalar(
        select(Transaction).where(Transaction.portfolio_id == portfolio_id)
    )
    assert persisted_transaction is None
