from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.model.note import Note
from src.model.portfolio import Portfolio


def register_user(client, *, email: str, username: str) -> dict:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )
    assert response.status_code == 201
    return response.json()


def login_user(client, *, email: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "StrongPass123"})
    assert response.status_code == 200
    return response.json()["access_token"]


def create_portfolio(client, token: str, *, name: str = "Portfolio") -> dict:
    response = client.post(
        "/api/v1/portfolios",
        json={"name": name},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 201
    return response.json()


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_api_post_201_exact_public_fields_and_trimmed_text(client) -> None:
    register_user(client, email="notes@example.com", username="notes")
    token = login_user(client, email="notes@example.com")
    portfolio = create_portfolio(client, token)

    response = client.post(
        "/api/v1/notes",
        json={"portfolio_id": portfolio["id"], "note_text": "  hello  "},
        headers=headers(token),
    )

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "portfolio_id", "note_text", "created_at"}
    assert body["portfolio_id"] == portfolio["id"]
    assert body["note_text"] == "hello"
    assert "user_id" not in body
    assert "updated_at" not in body


def test_api_get_pagination_order_total_and_user_isolation(client, db_session: Session) -> None:
    register_user(client, email="notes-owner@example.com", username="notes-owner")
    owner_token = login_user(client, email="notes-owner@example.com")
    register_user(client, email="notes-other@example.com", username="notes-other")
    other_token = login_user(client, email="notes-other@example.com")
    portfolio = create_portfolio(client, owner_token)
    other_portfolio = create_portfolio(client, other_token)

    old = client.post("/api/v1/notes", json={"portfolio_id": portfolio["id"], "note_text": "old"}, headers=headers(owner_token)).json()
    first = client.post("/api/v1/notes", json={"portfolio_id": portfolio["id"], "note_text": "first"}, headers=headers(owner_token)).json()
    second = client.post("/api/v1/notes", json={"portfolio_id": portfolio["id"], "note_text": "second"}, headers=headers(owner_token)).json()
    assert client.post("/api/v1/notes", json={"portfolio_id": other_portfolio["id"], "note_text": "other"}, headers=headers(other_token)).status_code == 201

    for item_id, created_at in [
        (old["id"], datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc)),
        (first["id"], datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)),
        (second["id"], datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc)),
    ]:
        note = db_session.get(Note, item_id)
        note.created_at = created_at
    db_session.commit()

    response = client.get("/api/v1/notes?skip=1&limit=2", headers=headers(owner_token))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["skip"] == 1
    assert body["limit"] == 2
    assert [item["id"] for item in body["items"]] == [first["id"], old["id"]]
    assert all(set(item) == {"id", "portfolio_id", "note_text", "created_at"} for item in body["items"])


def test_api_unauthenticated_post_and_get_return_401(client) -> None:
    post_response = client.post("/api/v1/notes", json={"portfolio_id": 1, "note_text": "hello"})
    get_response = client.get("/api/v1/notes")

    expected = "Authentication credentials were not provided or are invalid."
    assert post_response.status_code == 401
    assert post_response.json()["detail"] == expected
    assert get_response.status_code == 401
    assert get_response.json()["detail"] == expected


def test_api_cross_user_portfolio_create_returns_404(client) -> None:
    register_user(client, email="note-owner@example.com", username="note-owner")
    owner_token = login_user(client, email="note-owner@example.com")
    register_user(client, email="note-other@example.com", username="note-other")
    other_token = login_user(client, email="note-other@example.com")
    portfolio = create_portfolio(client, owner_token)

    response = client.post(
        "/api/v1/notes",
        json={"portfolio_id": portfolio["id"], "note_text": "nope"},
        headers=headers(other_token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_api_deleted_portfolio_create_404_but_existing_note_remains_listable(client, db_session: Session) -> None:
    register_user(client, email="note-deleted@example.com", username="note-deleted")
    token = login_user(client, email="note-deleted@example.com")
    portfolio = create_portfolio(client, token)
    created = client.post(
        "/api/v1/notes",
        json={"portfolio_id": portfolio["id"], "note_text": "before delete"},
        headers=headers(token),
    ).json()

    persisted_portfolio = db_session.get(Portfolio, portfolio["id"])
    persisted_portfolio.deleted_at = datetime(2026, 9, 7, tzinfo=timezone.utc)
    db_session.commit()

    create_response = client.post(
        "/api/v1/notes",
        json={"portfolio_id": portfolio["id"], "note_text": "after delete"},
        headers=headers(token),
    )
    list_response = client.get("/api/v1/notes", headers=headers(token))

    assert create_response.status_code == 404
    assert create_response.json()["detail"] == "Portfolio not found."
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1
    assert list_response.json()["items"][0]["id"] == created["id"]


def test_api_validation_422(client) -> None:
    register_user(client, email="note-validation@example.com", username="note-validation")
    token = login_user(client, email="note-validation@example.com")

    invalid_payloads = [
        {"portfolio_id": 0, "note_text": "hello"},
        {"portfolio_id": 1, "note_text": "   "},
        {"portfolio_id": 1, "note_text": "a" * 2001},
        {"portfolio_id": 1, "note_text": "hello", "title": "no"},
    ]
    for payload in invalid_payloads:
        response = client.post("/api/v1/notes", json=payload, headers=headers(token))
        assert response.status_code == 422

    for query in ["skip=-1", "limit=0", "limit=101"]:
        response = client.get(f"/api/v1/notes?{query}", headers=headers(token))
        assert response.status_code == 422


def test_api_does_not_expose_patch_delete_search_routes(client) -> None:
    register_user(client, email="note-routes@example.com", username="note-routes")
    token = login_user(client, email="note-routes@example.com")

    assert client.patch("/api/v1/notes/1", json={"note_text": "x"}, headers=headers(token)).status_code == 404
    assert client.delete("/api/v1/notes/1", headers=headers(token)).status_code == 404
