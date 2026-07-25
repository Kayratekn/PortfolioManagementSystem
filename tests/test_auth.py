from __future__ import annotations


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


def test_me_requires_bearer_token(client) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."
