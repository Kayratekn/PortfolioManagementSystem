from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from src.model.user import User
from src.repositories.user_repository import UserRepository
from src.request.user_request import UserUpdateRequest
from src.services.user_service import UserService


def register_and_login(client, *, email: str = "profile@example.com", username: str = "profile") -> str:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )
    assert register_response.status_code == 201
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_me_flow(client) -> None:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "kayra@example.com",
            "username": "kayra",
            "password": "StrongPass123",
            "full_name": "Kayra Tekin",
            "preferred_currency": "try",
            "risk_profile": "moderate",
        },
    )

    assert register_response.status_code == 201
    register_body = register_response.json()
    assert register_body["email"] == "kayra@example.com"
    assert register_body["preferred_currency"] == "TRY"
    assert "password" not in register_body

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "kayra@example.com",
            "password": "StrongPass123",
        },
    )

    assert login_response.status_code == 200
    login_body = login_response.json()
    assert login_body["token_type"] == "bearer"
    assert login_body["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {login_body['access_token']}"},
    )

    assert me_response.status_code == 200
    me_body = me_response.json()
    assert me_body["email"] == "kayra@example.com"
    assert me_body["username"] == "kayra"


def test_register_rejects_duplicate_email(client) -> None:
    payload = {
        "email": "duplicate@example.com",
        "username": "duplicate-user",
        "password": "StrongPass123",
        "preferred_currency": "TRY",
    }

    first_response = client.post("/api/v1/auth/register", json=payload)
    second_response = client.post(
        "/api/v1/auth/register",
        json={**payload, "username": "another-user"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["detail"] == "A user with this email already exists."


def test_login_rejects_invalid_password(client) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "invalid-login@example.com",
            "username": "invalid-login",
            "password": "StrongPass123",
            "preferred_currency": "TRY",
        },
    )

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "invalid-login@example.com",
            "password": "WrongPass123",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


def test_me_rejects_invalid_token(client) -> None:
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer this-is-not-a-valid-token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_me_requires_bearer_token(client) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_profile_update_normalizes_fields_and_me_reflects_persisted_values(client) -> None:
    token = register_and_login(client)

    currency_response = client.patch(
        "/api/v1/auth/me",
        json={"preferred_currency": "usd"},
        headers=auth_headers(token),
    )
    alias_response = client.patch(
        "/api/v1/auth/me",
        json={"risk_profile": " LOW "},
        headers=auth_headers(token),
    )
    canonical_response = client.patch(
        "/api/v1/auth/me",
        json={"risk_profile": "dengeli"},
        headers=auth_headers(token),
    )
    clear_response = client.patch(
        "/api/v1/auth/me",
        json={"risk_profile": None},
        headers=auth_headers(token),
    )
    both_response = client.patch(
        "/api/v1/auth/me",
        json={"preferred_currency": "gbp", "risk_profile": "yüksek"},
        headers=auth_headers(token),
    )
    me_response = client.get("/api/v1/auth/me", headers=auth_headers(token))

    assert currency_response.status_code == 200
    assert currency_response.json()["preferred_currency"] == "USD"
    assert alias_response.status_code == 200
    assert alias_response.json()["risk_profile"] == "muhafazakar"
    assert canonical_response.status_code == 200
    assert canonical_response.json()["risk_profile"] == "dengeli"
    assert clear_response.status_code == 200
    assert clear_response.json()["risk_profile"] is None
    assert both_response.status_code == 200
    assert both_response.json()["preferred_currency"] == "GBP"
    assert both_response.json()["risk_profile"] == "agresif"
    assert me_response.status_code == 200
    assert me_response.json()["preferred_currency"] == "GBP"
    assert me_response.json()["risk_profile"] == "agresif"


def test_profile_update_requires_authentication(client) -> None:
    response = client.patch("/api/v1/auth/me", json={"preferred_currency": "USD"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


@pytest.mark.parametrize(
    "payload",
    [
        {"preferred_currency": "JPY"},
        {"preferred_currency": None},
        {"risk_profile": "speculative"},
        {"risk_profile": "   "},
        {},
    ],
)
def test_profile_update_rejects_invalid_payloads(client, payload: dict[str, object]) -> None:
    token = register_and_login(client)

    response = client.patch("/api/v1/auth/me", json=payload, headers=auth_headers(token))

    assert response.status_code == 422


@pytest.mark.parametrize(
    "field_name",
    ["email", "username", "password", "full_name", "is_active", "role", "is_admin", "permissions"],
)
def test_profile_update_forbids_non_profile_fields(client, field_name: str) -> None:
    token = register_and_login(client)

    response = client.patch(
        "/api/v1/auth/me",
        json={field_name: "not-allowed"},
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_profile_update_commit_failure_rolls_back_and_preserves_persisted_state(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = User(
        email="rollback@example.com",
        username="rollback",
        hashed_password="hashed",
        preferred_currency="TRY",
        risk_profile="dengeli",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    original_rollback = db_session.rollback
    rollback_calls = 0

    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    def tracking_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", tracking_rollback)

    with pytest.raises(RuntimeError, match="commit failed"):
        UserService(UserRepository(db_session)).update_profile(
            payload=UserUpdateRequest(preferred_currency="USD", risk_profile="aggressive"),
            current_user=user,
        )

    assert rollback_calls == 1
    db_session.expire_all()
    reloaded = db_session.get(User, user.id)
    assert reloaded is not None
    assert reloaded.preferred_currency == "TRY"
    assert reloaded.risk_profile == "dengeli"
    assert user.preferred_currency == "TRY"
    assert user.risk_profile == "dengeli"


def test_profile_update_two_user_isolation(client) -> None:
    user_a_token = register_and_login(client, email="profile-a@example.com", username="profile-a")
    user_b_token = register_and_login(client, email="profile-b@example.com", username="profile-b")
    user_b_before = client.get("/api/v1/auth/me", headers=auth_headers(user_b_token)).json()

    response = client.patch(
        "/api/v1/auth/me",
        json={"preferred_currency": "EUR", "risk_profile": "aggressive"},
        headers=auth_headers(user_a_token),
    )

    user_b_after = client.get("/api/v1/auth/me", headers=auth_headers(user_b_token)).json()
    assert response.status_code == 200
    assert user_b_after == user_b_before


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "attacker@example.com"},
        {"username": "attacker"},
        {"password": "AnotherStrongPass123"},
        {"full_name": "Attacker"},
        {"is_active": True},
        {"role": "admin"},
        {"permissions": ["admin"]},
    ],
)
def test_profile_update_rejects_type_valid_forbidden_fields(client, payload: dict[str, object]) -> None:
    token = register_and_login(client)

    response = client.patch("/api/v1/auth/me", json=payload, headers=auth_headers(token))

    assert response.status_code == 422


def test_profile_update_preserves_omitted_fields(client) -> None:
    token = register_and_login(client)
    initial = client.patch(
        "/api/v1/auth/me",
        json={"preferred_currency": "USD", "risk_profile": "moderate"},
        headers=auth_headers(token),
    )
    currency_only = client.patch(
        "/api/v1/auth/me",
        json={"preferred_currency": "EUR"},
        headers=auth_headers(token),
    )
    risk_only = client.patch(
        "/api/v1/auth/me",
        json={"risk_profile": "aggressive"},
        headers=auth_headers(token),
    )

    assert initial.status_code == 200
    assert currency_only.status_code == 200
    assert currency_only.json()["preferred_currency"] == "EUR"
    assert currency_only.json()["risk_profile"] == "dengeli"
    assert risk_only.status_code == 200
    assert risk_only.json()["preferred_currency"] == "EUR"
    assert risk_only.json()["risk_profile"] == "agresif"


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("conservative", "muhafazakar"),
        ("LOW", "muhafazakar"),
        ("dusuk", "muhafazakar"),
        ("düşük", "muhafazakar"),
        ("DÜŞÜK", "muhafazakar"),
        ("defansif", "muhafazakar"),
        ("muhafazakar", "muhafazakar"),
        ("moderate", "dengeli"),
        ("balanced", "dengeli"),
        ("medium", "dengeli"),
        ("orta", "dengeli"),
        ("dengeli", "dengeli"),
        ("aggressive", "agresif"),
        ("high", "agresif"),
        ("yuksek", "agresif"),
        ("YÜKSEK", "agresif"),
        ("dinamik", "agresif"),
        ("agresif", "agresif"),
    ],
)
def test_profile_update_risk_aliases_canonicalize(client, alias: str, canonical: str) -> None:
    token = register_and_login(client)

    response = client.patch(
        "/api/v1/auth/me",
        json={"risk_profile": alias},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["risk_profile"] == canonical
