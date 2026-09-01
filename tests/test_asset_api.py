from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.model.asset import Asset


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


def create_asset(
    db_session: Session,
    *,
    asset_code: str,
    asset_name: str,
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    isin: str | None = "TRTESTISIN01",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
    is_active: bool = True,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type=asset_type,
        fund_kind=fund_kind,
        isin=isin,
        currency=currency,
        data_source=data_source,
        is_active=is_active,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_authenticated_user_can_list_active_assets(client, db_session: Session) -> None:
    register_user(client, email="asset-api@example.com", username="asset-api")
    token = login_user(client, email="asset-api@example.com")
    second_same_code = create_asset(
        db_session,
        asset_code="AAA",
        asset_name="Second AAA Fund",
        data_source="MANUAL",
    )
    later_code = create_asset(db_session, asset_code="BBB", asset_name="BBB Fund")
    first_same_code = create_asset(db_session, asset_code="AAA", asset_name="First AAA Fund")
    create_asset(
        db_session,
        asset_code="AAB",
        asset_name="Inactive Fund",
        is_active=False,
    )

    response = client.get(
        "/api/v1/assets?skip=1&limit=2",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["skip"] == 1
    assert body["limit"] == 2
    assert [item["id"] for item in body["items"]] == [first_same_code.id, later_code.id]
    assert body["items"][0] == {
        "id": first_same_code.id,
        "asset_code": "AAA",
        "asset_name": "First AAA Fund",
        "asset_type": "FUND",
        "fund_kind": "YAT",
        "isin": "TRTESTISIN01",
        "currency": "TRY",
        "data_source": "TEFAS",
    }
    assert second_same_code.id < first_same_code.id


def test_asset_catalog_searches_code_and_name_case_insensitively(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="asset-search-api@example.com",
        username="asset-search-api",
    )
    token = login_user(client, email="asset-search-api@example.com")
    code_match = create_asset(db_session, asset_code="AAL", asset_name="Money Market")
    name_match = create_asset(db_session, asset_code="BLH", asset_name="Aal Balanced")
    create_asset(db_session, asset_code="CCC", asset_name="Equity Fund")
    create_asset(
        db_session,
        asset_code="AALX",
        asset_name="Inactive Match",
        is_active=False,
    )

    response = client.get(
        "/api/v1/assets?search=aal",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["id"] for item in body["items"]] == [code_match.id, name_match.id]


def test_asset_catalog_preserves_nullable_isin_and_currency(
    client,
    db_session: Session,
) -> None:
    register_user(
        client,
        email="asset-nullable-api@example.com",
        username="asset-nullable-api",
    )
    token = login_user(client, email="asset-nullable-api@example.com")
    create_asset(
        db_session,
        asset_code="NULL",
        asset_name="Nullable Fund",
        isin=None,
        currency=None,
    )

    response = client.get(
        "/api/v1/assets",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["isin"] is None
    assert item["currency"] is None


def test_asset_catalog_requires_authentication(client) -> None:
    response = client.get("/api/v1/assets")

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "Authentication credentials were not provided or are invalid."
    )


@pytest.mark.parametrize("query", ["skip=-1", "limit=0", "limit=101"])
def test_asset_catalog_validates_pagination_query(client, query: str) -> None:
    register_user(
        client,
        email=f"asset-pagination-{query.replace('=', '-')}@example.com",
        username=f"asset-pagination-{query.replace('=', '-')}",
    )
    token = login_user(
        client,
        email=f"asset-pagination-{query.replace('=', '-')}@example.com",
    )

    response = client.get(
        f"/api/v1/assets?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
