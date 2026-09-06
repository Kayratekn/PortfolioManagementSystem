from __future__ import annotations

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.watchlist_item import WatchlistItem


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
    asset_code: str = "AAL",
    asset_name: str = "Example Fund",
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


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_watchlist_create_list_delete_contracts(client, db_session: Session) -> None:
    register_user(client, email="watchlist-api@example.com", username="watchlist-api")
    token = login_user(client, email="watchlist-api@example.com")
    asset = create_asset(db_session)

    create_response = client.post(
        "/api/v1/watchlist",
        json={"asset_id": asset.id},
        headers=auth_headers(token),
    )

    assert create_response.status_code == 201
    body = create_response.json()
    assert set(body) == {
        "id",
        "asset_id",
        "asset_code",
        "asset_name",
        "asset_type",
        "fund_kind",
        "isin",
        "currency",
        "data_source",
        "created_at",
    }
    assert body["asset_id"] == asset.id
    assert body["asset_code"] == "AAL"
    assert "user_id" not in body
    assert "updated_at" not in body

    list_response = client.get("/api/v1/watchlist", headers=auth_headers(token))
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["skip"] == 0
    assert list_response.json()["limit"] == 50
    assert list_response.json()["items"] == [body]

    delete_response = client.delete(f"/api/v1/watchlist/{body['id']}", headers=auth_headers(token))
    assert delete_response.status_code == 204
    assert delete_response.content == b""
    assert db_session.get(WatchlistItem, body["id"]) is None


def test_watchlist_list_pagination_order_and_user_isolation(client, db_session: Session) -> None:
    register_user(client, email="wl-owner@example.com", username="wl-owner")
    owner_token = login_user(client, email="wl-owner@example.com")
    register_user(client, email="wl-other@example.com", username="wl-other")
    other_token = login_user(client, email="wl-other@example.com")
    asset_b = create_asset(db_session, asset_code="BBB", asset_name="BBB Fund")
    asset_a2 = create_asset(db_session, asset_code="AAA", asset_name="Second AAA", data_source="MANUAL")
    asset_a1 = create_asset(db_session, asset_code="AAA", asset_name="First AAA")
    asset_other = create_asset(db_session, asset_code="AAC", asset_name="Other")

    for asset in [asset_b, asset_a2, asset_a1]:
        assert client.post(
            "/api/v1/watchlist",
            json={"asset_id": asset.id},
            headers=auth_headers(owner_token),
        ).status_code == 201
    assert client.post(
        "/api/v1/watchlist",
        json={"asset_id": asset_other.id},
        headers=auth_headers(other_token),
    ).status_code == 201

    response = client.get("/api/v1/watchlist?skip=1&limit=2", headers=auth_headers(owner_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["skip"] == 1
    assert body["limit"] == 2
    assert [(item["asset_code"], item["asset_name"]) for item in body["items"]] == [
        ("AAA", "First AAA"),
        ("BBB", "BBB Fund"),
    ]


def test_watchlist_create_missing_or_inactive_asset_returns_404(client, db_session: Session) -> None:
    register_user(client, email="wl-missing@example.com", username="wl-missing")
    token = login_user(client, email="wl-missing@example.com")
    inactive = create_asset(db_session, is_active=False)

    missing_response = client.post(
        "/api/v1/watchlist",
        json={"asset_id": 999999},
        headers=auth_headers(token),
    )
    inactive_response = client.post(
        "/api/v1/watchlist",
        json={"asset_id": inactive.id},
        headers=auth_headers(token),
    )

    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Asset not found."
    assert inactive_response.status_code == 404
    assert inactive_response.json()["detail"] == "Asset not found."


def test_watchlist_duplicate_returns_409_and_same_asset_allowed_for_different_users(
    client,
    db_session: Session,
) -> None:
    register_user(client, email="wl-first@example.com", username="wl-first")
    first_token = login_user(client, email="wl-first@example.com")
    register_user(client, email="wl-second@example.com", username="wl-second")
    second_token = login_user(client, email="wl-second@example.com")
    asset = create_asset(db_session)

    assert client.post(
        "/api/v1/watchlist",
        json={"asset_id": asset.id},
        headers=auth_headers(first_token),
    ).status_code == 201
    duplicate_response = client.post(
        "/api/v1/watchlist",
        json={"asset_id": asset.id},
        headers=auth_headers(first_token),
    )
    second_user_response = client.post(
        "/api/v1/watchlist",
        json={"asset_id": asset.id},
        headers=auth_headers(second_token),
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json()["detail"] == "Asset is already in watchlist."
    assert second_user_response.status_code == 201


def test_watchlist_delete_missing_or_other_user_item_returns_404(client, db_session: Session) -> None:
    register_user(client, email="wl-owner-delete@example.com", username="wl-owner-delete")
    owner_token = login_user(client, email="wl-owner-delete@example.com")
    register_user(client, email="wl-other-delete@example.com", username="wl-other-delete")
    other_token = login_user(client, email="wl-other-delete@example.com")
    asset = create_asset(db_session)
    created = client.post(
        "/api/v1/watchlist",
        json={"asset_id": asset.id},
        headers=auth_headers(owner_token),
    ).json()

    other_response = client.delete(
        f"/api/v1/watchlist/{created['id']}",
        headers=auth_headers(other_token),
    )
    missing_response = client.delete("/api/v1/watchlist/999999", headers=auth_headers(owner_token))

    assert other_response.status_code == 404
    assert other_response.json()["detail"] == "Watchlist item not found."
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Watchlist item not found."
    assert db_session.get(WatchlistItem, created["id"]) is not None


def test_watchlist_endpoints_require_authentication(client, db_session: Session) -> None:
    asset = create_asset(db_session)

    post_response = client.post("/api/v1/watchlist", json={"asset_id": asset.id})
    list_response = client.get("/api/v1/watchlist")
    delete_response = client.delete("/api/v1/watchlist/1")

    expected = "Authentication credentials were not provided or are invalid."
    assert post_response.status_code == 401
    assert post_response.json()["detail"] == expected
    assert list_response.status_code == 401
    assert list_response.json()["detail"] == expected
    assert delete_response.status_code == 401
    assert delete_response.json()["detail"] == expected


def test_watchlist_validates_payload_and_pagination(client) -> None:
    register_user(client, email="wl-validation@example.com", username="wl-validation")
    token = login_user(client, email="wl-validation@example.com")

    assert client.post(
        "/api/v1/watchlist",
        json={"asset_id": 1, "extra": "not allowed"},
        headers=auth_headers(token),
    ).status_code == 422
    assert client.post(
        "/api/v1/watchlist",
        json={"asset_id": 0},
        headers=auth_headers(token),
    ).status_code == 422
    for query in ["skip=-1", "limit=0", "limit=101"]:
        assert client.get(
            f"/api/v1/watchlist?{query}",
            headers=auth_headers(token),
        ).status_code == 422
