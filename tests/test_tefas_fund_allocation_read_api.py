from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.integrations.tefas_client import CustomTefasClient
from src.model.asset import Asset
from src.repositories.tefas_fund_allocation_data_repository import (
    TefasFundAllocationDataRepository,
    TefasFundAllocationRowCreate,
)


def register_user(
    client,
    *,
    email: str = "tefas-reader@example.com",
    username: str = "tefas-reader",
) -> dict:
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


def login_user(client, *, email: str = "tefas-reader@example.com") -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_authenticated_user(client) -> str:
    register_user(client)
    return login_user(client)


def create_tefas_asset(
    db_session: Session,
    *,
    asset_code: str = "AB1",
    asset_name: str = "AB1 GAYRIMENKUL YATIRIM FONU",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind="GYF",
        currency=None,
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def replace_allocations(
    db_session: Session,
    *,
    asset_id: int,
    rows: list[tuple[str, Decimal]],
    data_date: date = date(2026, 8, 11),
) -> None:
    repository = TefasFundAllocationDataRepository(db_session)
    repository.replace_for_asset_and_date(
        asset_id=asset_id,
        data_date=data_date,
        rows=[
            TefasFundAllocationRowCreate(
                asset_id=asset_id,
                data_date=data_date,
                raw_field_name=raw_field_name,
                allocation_percentage=allocation_percentage,
            )
            for raw_field_name, allocation_percentage in rows
        ],
    )
    db_session.commit()


def test_authenticated_request_returns_verified_allocation(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fund_code"] == "AB1"
    assert body["fund_name"] == "AB1 GAYRIMENKUL YATIRIM FONU"
    assert body["data_date"] == "2026-08-11"
    assert body["allocations"] == [
        {
            "label": "Gayrimenkul Yatırımları",
            "raw_field_name": None,
            "percentage": "100.000000",
            "mapping_status": "VERIFIED",
        }
    ]


def test_unresolved_allocation_preserves_raw_field_name(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("bb", Decimal("5.500000"))],
    )

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["allocations"] == [
        {
            "label": None,
            "raw_field_name": "bb",
            "percentage": "5.500000",
            "mapping_status": "UNRESOLVED",
        }
    ]


def test_path_fund_code_is_normalized(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )

    response = client.get(
        "/api/v1/tefas/funds/ab1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["fund_code"] == "AB1"


def test_missing_fund_returns_404(client) -> None:
    token = create_authenticated_user(client)

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund not found."


def test_existing_asset_with_no_rows_returns_empty_allocations(
    client,
    db_session: Session,
) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["allocations"] == []


def test_missing_date_query_returns_422(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_invalid_date_query_returns_422(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=not-a-date",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_unauthenticated_request_returns_401(client, db_session: Session) -> None:
    create_tefas_asset(db_session)

    response = client.get("/api/v1/tefas/funds/AB1/allocations?date=2026-08-11")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_authenticated_user_does_not_need_portfolio_ownership(
    client,
    db_session: Session,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["fund_code"] == "AB1"


def test_endpoint_does_not_trigger_tefas_network_fetch(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_network_fetch(*args, **kwargs):
        raise AssertionError("TEFAS network fetch should not run")

    monkeypatch.setattr(CustomTefasClient, "_post_json", fail_on_network_fetch)
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_exact_route_path_works_without_duplicate_api_prefix(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )

    exact_response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )
    duplicated_prefix_response = client.get(
        "/api/v1/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert exact_response.status_code == 200
    assert duplicated_prefix_response.status_code == 404


def test_verified_allocation_json_does_not_expose_raw_abbreviation(
    client,
    db_session: Session,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )

    response = client.get(
        "/api/v1/tefas/funds/AB1/allocations?date=2026-08-11",
        headers=auth_headers(token),
    )

    allocation = response.json()["allocations"][0]
    assert allocation["raw_field_name"] is None
    assert "gyy" not in allocation.values()
