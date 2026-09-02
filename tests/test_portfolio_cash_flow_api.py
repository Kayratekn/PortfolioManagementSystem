from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.portfolio_cash_flow import PortfolioCashFlow


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


def _valid_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "flow_type": "DEPOSIT",
        "amount": "123.45678901",
        "currency": "TRY",
        "flow_date": "2026-09-02",
    }
    payload.update(overrides)
    return payload


def test_authenticated_user_can_create_deposit_cash_flow(
    client,
    db_session: Session,
) -> None:
    register_user(client, email="cash-flow-api@example.com", username="cash-flow-api")
    token = login_user(client, email="cash-flow-api@example.com")
    portfolio_response = create_portfolio(client, token, name="Cash Flow Portfolio")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/cash-flows",
        json=_valid_payload(flow_type=" deposit ", currency=" usd "),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["portfolio_id"] == portfolio_id
    assert body["flow_type"] == "DEPOSIT"
    assert body["amount"] == "123.45678901"
    assert body["currency"] == "USD"
    assert body["flow_date"] == "2026-09-02"
    assert body["id"] is not None
    assert body["created_at"] is not None
    assert body["updated_at"] is not None

    db_session.expire_all()
    persisted_cash_flow = db_session.scalar(
        select(PortfolioCashFlow).where(PortfolioCashFlow.id == body["id"])
    )
    assert persisted_cash_flow is not None
    assert persisted_cash_flow.amount == Decimal("123.45678901")
    assert persisted_cash_flow.currency == "USD"


def test_authenticated_user_can_create_withdrawal_cash_flow(client) -> None:
    register_user(
        client,
        email="cash-flow-withdrawal-api@example.com",
        username="cash-flow-withdrawal-api",
    )
    token = login_user(client, email="cash-flow-withdrawal-api@example.com")
    portfolio_response = create_portfolio(client, token, name="Withdrawal Cash Flow")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/cash-flows",
        json=_valid_payload(flow_type="WITHDRAWAL"),
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    assert response.json()["flow_type"] == "WITHDRAWAL"


def test_create_cash_flow_requires_authentication(client, db_session: Session) -> None:
    response = client.post(
        "/api/v1/portfolios/999999/cash-flows",
        json=_valid_payload(),
    )

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Authentication credentials were not provided or are invalid."
    )
    assert db_session.scalar(select(PortfolioCashFlow)) is None


def test_user_cannot_create_cash_flow_for_another_users_portfolio(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="cash-flow-owner-api@example.com",
        username="cash-flow-owner-api",
    )
    owner_token = login_user(client, email="cash-flow-owner-api@example.com")
    portfolio_response = create_portfolio(client, owner_token, name="Owner Cash Flow")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    register_user(
        client,
        email="cash-flow-other-api@example.com",
        username="cash-flow-other-api",
    )
    other_token = login_user(client, email="cash-flow-other-api@example.com")

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/cash-flows",
        json=_valid_payload(),
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."
    assert db_session.scalar(select(PortfolioCashFlow)) is None


@pytest.mark.parametrize(
    "payload",
    [
        _valid_payload(flow_type="BUY"),
        _valid_payload(currency="JPY"),
        _valid_payload(amount="0"),
        _valid_payload(amount="-1"),
    ],
)
def test_invalid_cash_flow_payload_returns_422(client, payload: dict[str, str]) -> None:
    register_user(
        client,
        email=f"cash-flow-invalid-{payload['flow_type']}-{payload['currency']}-{payload['amount']}@example.com",
        username=f"cash-flow-invalid-{payload['flow_type']}-{payload['currency']}-{payload['amount']}",
    )
    token = login_user(
        client,
        email=f"cash-flow-invalid-{payload['flow_type']}-{payload['currency']}-{payload['amount']}@example.com",
    )
    portfolio_response = create_portfolio(client, token, name="Invalid Cash Flow")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/cash-flows",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_authenticated_user_can_list_cash_flows_with_pagination_and_order(client) -> None:
    register_user(
        client,
        email="cash-flow-list-api@example.com",
        username="cash-flow-list-api",
    )
    token = login_user(client, email="cash-flow-list-api@example.com")
    portfolio_response = create_portfolio(client, token, name="List Cash Flows")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]
    created_ids: list[int] = []
    for flow_date in ["2026-09-03", "2026-09-02", "2026-09-02"]:
        response = client.post(
            f"/api/v1/portfolios/{portfolio_id}/cash-flows",
            json=_valid_payload(flow_date=flow_date),
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        created_ids.append(response.json()["id"])

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/cash-flows?skip=1&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["skip"] == 1
    assert body["limit"] == 2
    assert [item["id"] for item in body["items"]] == [created_ids[2], created_ids[0]]
    assert body["items"][0]["amount"] == "123.45678901"


def test_list_cash_flows_requires_authentication(client) -> None:
    response = client.get("/api/v1/portfolios/999999/cash-flows")

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Authentication credentials were not provided or are invalid."
    )


def test_user_cannot_list_cash_flows_for_another_users_portfolio(client) -> None:
    register_user(
        client,
        email="cash-flow-list-owner-api@example.com",
        username="cash-flow-list-owner-api",
    )
    owner_token = login_user(client, email="cash-flow-list-owner-api@example.com")
    portfolio_response = create_portfolio(client, owner_token, name="Owner List")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    register_user(
        client,
        email="cash-flow-list-other-api@example.com",
        username="cash-flow-list-other-api",
    )
    other_token = login_user(client, email="cash-flow-list-other-api@example.com")

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/cash-flows",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_list_cash_flows_empty_history_returns_empty_items(client) -> None:
    register_user(
        client,
        email="cash-flow-empty-api@example.com",
        username="cash-flow-empty-api",
    )
    token = login_user(client, email="cash-flow-empty-api@example.com")
    portfolio_response = create_portfolio(client, token, name="Empty Cash Flows")
    assert portfolio_response.status_code == 201
    portfolio_id = portfolio_response.json()["id"]

    response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/cash-flows",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "skip": 0, "limit": 50}


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=101"])
def test_list_cash_flows_validates_pagination_query(client, query: str) -> None:
    register_user(
        client,
        email=f"cash-flow-list-{query.replace('=', '-')}@example.com",
        username=f"cash-flow-list-{query.replace('=', '-')}",
    )
    token = login_user(
        client,
        email=f"cash-flow-list-{query.replace('=', '-')}@example.com",
    )

    response = client.get(
        f"/api/v1/portfolios/999999/cash-flows?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
