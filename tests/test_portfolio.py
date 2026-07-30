from __future__ import annotations


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


def create_portfolio(client, token: str, *, name: str, base_currency: str | None = None):
    payload = {"name": name}
    if base_currency is not None:
        payload["base_currency"] = base_currency

    return client.post(
        "/api/v1/portfolios",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_authenticated_user_can_create_portfolio(client) -> None:
    user = register_user(
        client,
        email="portfolio-create@example.com",
        username="portfolio-create",
    )
    token = login_user(client, email="portfolio-create@example.com")

    response = create_portfolio(client, token, name="Retirement Fund", base_currency="USD")

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == user["id"]
    assert body["name"] == "Retirement Fund"
    assert body["base_currency"] == "USD"


def test_default_currency_comes_from_user_preferred_currency(client) -> None:
    register_user(
        client,
        email="default-currency@example.com",
        username="default-currency",
        preferred_currency="eur",
    )
    token = login_user(client, email="default-currency@example.com")

    response = create_portfolio(client, token, name="Euro Portfolio")

    assert response.status_code == 201
    assert response.json()["base_currency"] == "EUR"


def test_lowercase_currency_is_saved_as_uppercase(client) -> None:
    register_user(client, email="lowercase@example.com", username="lowercase")
    token = login_user(client, email="lowercase@example.com")

    response = create_portfolio(client, token, name="Currency Test", base_currency="gbp")

    assert response.status_code == 201
    assert response.json()["base_currency"] == "GBP"


def test_invalid_currency_returns_422(client) -> None:
    register_user(client, email="invalid-currency@example.com", username="invalid-currency")
    token = login_user(client, email="invalid-currency@example.com")

    response = create_portfolio(client, token, name="Invalid Currency", base_currency="JPY")

    assert response.status_code == 422


def test_name_is_trimmed(client) -> None:
    register_user(client, email="trim@example.com", username="trim")
    token = login_user(client, email="trim@example.com")

    response = create_portfolio(client, token, name="  Trimmed Name  ", base_currency="TRY")

    assert response.status_code == 201
    assert response.json()["name"] == "Trimmed Name"


def test_whitespace_only_name_is_rejected(client) -> None:
    register_user(client, email="whitespace@example.com", username="whitespace")
    token = login_user(client, email="whitespace@example.com")

    response = create_portfolio(client, token, name="   ")

    assert response.status_code == 422


def test_name_with_100_characters_is_accepted(client) -> None:
    register_user(client, email="max-length@example.com", username="max-length")
    token = login_user(client, email="max-length@example.com")

    response = create_portfolio(client, token, name="a" * 100)

    assert response.status_code == 201
    assert response.json()["name"] == "a" * 100


def test_name_with_101_characters_is_rejected(client) -> None:
    register_user(client, email="too-long@example.com", username="too-long")
    token = login_user(client, email="too-long@example.com")

    response = create_portfolio(client, token, name="a" * 101)

    assert response.status_code == 422


def test_same_name_portfolios_are_allowed(client) -> None:
    register_user(client, email="duplicate-name@example.com", username="duplicate-name")
    token = login_user(client, email="duplicate-name@example.com")

    first_response = create_portfolio(client, token, name="Same Name")
    second_response = create_portfolio(client, token, name="Same Name")

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] != second_response.json()["id"]


def test_user_only_lists_own_active_portfolios(client) -> None:
    register_user(client, email="owner@example.com", username="owner")
    owner_token = login_user(client, email="owner@example.com")
    register_user(client, email="other@example.com", username="other")
    other_token = login_user(client, email="other@example.com")

    own_visible = create_portfolio(client, owner_token, name="Own Visible")
    own_deleted = create_portfolio(client, owner_token, name="Own Deleted")
    create_portfolio(client, other_token, name="Other User")

    delete_response = client.delete(
        f"/api/v1/portfolios/{own_deleted.json()['id']}",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert own_visible.status_code == 201
    assert own_deleted.status_code == 201
    assert delete_response.status_code == 204

    response = client.get(
        "/api/v1/portfolios",
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["name"] for item in body["items"]] == ["Own Visible"]


def test_pagination_and_total_are_correct(client) -> None:
    register_user(client, email="pagination@example.com", username="pagination")
    token = login_user(client, email="pagination@example.com")

    for index in range(3):
        response = create_portfolio(client, token, name=f"Portfolio {index + 1}")
        assert response.status_code == 201

    response = client.get(
        "/api/v1/portfolios?skip=1&limit=1",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert body["skip"] == 1
    assert body["limit"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == "Portfolio 2"


def test_portfolio_detail_can_be_retrieved(client) -> None:
    register_user(client, email="detail@example.com", username="detail")
    token = login_user(client, email="detail@example.com")
    create_response = create_portfolio(client, token, name="Detail Portfolio")

    response = client.get(
        f"/api/v1/portfolios/{create_response.json()['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Detail Portfolio"


def test_other_users_portfolio_detail_returns_404(client) -> None:
    register_user(client, email="detail-owner@example.com", username="detail-owner")
    owner_token = login_user(client, email="detail-owner@example.com")
    register_user(client, email="detail-other@example.com", username="detail-other")
    other_token = login_user(client, email="detail-other@example.com")
    create_response = create_portfolio(client, owner_token, name="Hidden Portfolio")

    response = client.get(
        f"/api/v1/portfolios/{create_response.json()['id']}",
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."


def test_name_and_currency_can_be_updated(client) -> None:
    register_user(client, email="update@example.com", username="update")
    token = login_user(client, email="update@example.com")
    create_response = create_portfolio(client, token, name="Before Update", base_currency="TRY")

    response = client.patch(
        f"/api/v1/portfolios/{create_response.json()['id']}",
        json={"name": "  After Update  ", "base_currency": "usd"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "After Update"
    assert body["base_currency"] == "USD"


def test_empty_patch_returns_422(client) -> None:
    register_user(client, email="empty-patch@example.com", username="empty-patch")
    token = login_user(client, email="empty-patch@example.com")
    create_response = create_portfolio(client, token, name="Patch Target")

    response = client.patch(
        f"/api/v1/portfolios/{create_response.json()['id']}",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422


def test_other_user_cannot_update_portfolio(client) -> None:
    register_user(client, email="update-owner@example.com", username="update-owner")
    owner_token = login_user(client, email="update-owner@example.com")
    register_user(client, email="update-other@example.com", username="update-other")
    other_token = login_user(client, email="update-other@example.com")
    create_response = create_portfolio(client, owner_token, name="Owner Portfolio")

    response = client.patch(
        f"/api/v1/portfolios/{create_response.json()['id']}",
        json={"name": "Hijacked"},
        headers={"Authorization": f"Bearer {other_token}"},
    )

    assert response.status_code == 404


def test_delete_returns_204_and_soft_deletes_portfolio(client) -> None:
    register_user(client, email="delete@example.com", username="delete")
    token = login_user(client, email="delete@example.com")
    create_response = create_portfolio(client, token, name="Delete Me")

    response = client.delete(
        f"/api/v1/portfolios/{create_response.json()['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204
    assert response.content == b""


def test_deleted_portfolio_is_hidden_from_list(client) -> None:
    register_user(client, email="hidden-list@example.com", username="hidden-list")
    token = login_user(client, email="hidden-list@example.com")
    visible_response = create_portfolio(client, token, name="Visible")
    deleted_response = create_portfolio(client, token, name="Deleted")

    delete_result = client.delete(
        f"/api/v1/portfolios/{deleted_response.json()['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )

    response = client.get(
        "/api/v1/portfolios",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert visible_response.status_code == 201
    assert delete_result.status_code == 204
    assert response.status_code == 200
    assert [item["name"] for item in response.json()["items"]] == ["Visible"]


def test_deleted_portfolio_returns_404_for_detail_update_and_delete(client) -> None:
    register_user(client, email="deleted-ops@example.com", username="deleted-ops")
    token = login_user(client, email="deleted-ops@example.com")
    create_response = create_portfolio(client, token, name="Deleted Ops")
    portfolio_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/api/v1/portfolios/{portfolio_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    detail_response = client.get(
        f"/api/v1/portfolios/{portfolio_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    update_response = client.patch(
        f"/api/v1/portfolios/{portfolio_id}",
        json={"name": "Should Fail"},
        headers={"Authorization": f"Bearer {token}"},
    )
    second_delete_response = client.delete(
        f"/api/v1/portfolios/{portfolio_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert delete_response.status_code == 204
    assert detail_response.status_code == 404
    assert update_response.status_code == 404
    assert second_delete_response.status_code == 404


def test_portfolio_endpoints_require_token(client) -> None:
    create_response = client.post("/api/v1/portfolios", json={"name": "No Token"})
    list_response = client.get("/api/v1/portfolios")
    detail_response = client.get("/api/v1/portfolios/1")
    update_response = client.patch("/api/v1/portfolios/1", json={"name": "No Token"})
    delete_response = client.delete("/api/v1/portfolios/1")

    assert create_response.status_code == 401
    assert list_response.status_code == 401
    assert detail_response.status_code == 401
    assert update_response.status_code == 401
    assert delete_response.status_code == 401
