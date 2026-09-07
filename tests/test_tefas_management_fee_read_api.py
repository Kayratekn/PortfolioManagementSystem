from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, Session as SQLAlchemySession

from src.integrations.tefas_client import CustomTefasClient
from src.model.asset import Asset
from src.model.tefas_management_fee_history import TefasManagementFeeHistory
from src.services.tefas_management_fee_refresh_service import TefasManagementFeeRefreshService
from src.services.tefas_sync_service import TefasSyncService


def register_user(
    client,
    *,
    email: str = "management-fee-reader@example.com",
    username: str = "management-fee-reader",
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


def login_user(client, *, email: str = "management-fee-reader@example.com") -> str:
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
    asset_code: str = "AAL",
    asset_name: str = "AAL TEST FUND",
    fund_kind: str | None = "YAT",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind=fund_kind,
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def add_management_fee(
    db_session: Session,
    *,
    asset_id: int,
    management_fee_percentage: Decimal = Decimal("1.750000"),
    first_observed_at: datetime = datetime(2026, 8, 10, 9, 0, tzinfo=timezone.utc),
    last_observed_at: datetime = datetime(2026, 8, 11, 9, 0, tzinfo=timezone.utc),
    closed_at: datetime | None = None,
    source_endpoint: str = "fonYonetimBazliBilgiGetir",
    source_field_name: str = "uygulananYu1Y",
) -> TefasManagementFeeHistory:
    history = TefasManagementFeeHistory(
        asset_id=asset_id,
        management_fee_percentage=management_fee_percentage,
        first_observed_at=first_observed_at,
        last_observed_at=last_observed_at,
        closed_at=closed_at,
        source_endpoint=source_endpoint,
        source_field_name=source_field_name,
    )
    db_session.add(history)
    db_session.commit()
    db_session.refresh(history)
    return history


def test_current_management_fee_requires_authentication(client, db_session: Session) -> None:
    create_tefas_asset(db_session)

    response = client.get("/api/v1/tefas/funds/AAL/management-fee/current")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_current_management_fee_returns_canonical_response_and_decimal_string(
    client,
    db_session: Session,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_management_fee(
        db_session,
        asset_id=asset.id,
        management_fee_percentage=Decimal("1.750000"),
        source_endpoint="fonYonetimBazliBilgiGetir",
        source_field_name="uygulananYu1Y",
    )

    response = client.get(
        "/api/v1/tefas/funds/ aal /management-fee/current",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json() == {
        "asset_id": asset.id,
        "fund_code": "AAL",
        "fund_name": "AAL TEST FUND",
        "fund_kind": "YAT",
        "management_fee_percentage": "1.750000",
        "first_observed_at": "2026-08-10T09:00:00",
        "last_observed_at": "2026-08-11T09:00:00",
        "source_endpoint": "fonYonetimBazliBilgiGetir",
        "source_field_name": "uygulananYu1Y",
    }


def test_current_management_fee_missing_tefas_asset_returns_404(client) -> None:
    token = create_authenticated_user(client)

    response = client.get(
        "/api/v1/tefas/funds/AAL/management-fee/current",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund not found."


def test_current_management_fee_supported_asset_without_current_row_returns_404(
    client,
    db_session: Session,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_management_fee(
        db_session,
        asset_id=asset.id,
        closed_at=datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc),
    )

    response = client.get(
        "/api/v1/tefas/funds/AAL/management-fee/current",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS management fee not found."


@pytest.mark.parametrize("fund_kind", ["BYF", "GYF", "GSYF"])
def test_current_management_fee_unsupported_fund_kind_returns_404(
    client,
    db_session: Session,
    fund_kind: str,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session, fund_kind=fund_kind)
    add_management_fee(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AAL/management-fee/current",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS management fee not found."


def test_current_management_fee_does_not_trigger_network_refresh_or_sync(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_network_fetch(*args, **kwargs):
        raise AssertionError("TEFAS network fetch should not run")

    def fail_on_sync(*args, **kwargs):
        raise AssertionError("TEFAS sync should not run")

    def fail_on_refresh(*args, **kwargs):
        raise AssertionError("TEFAS management-fee refresh should not run")

    monkeypatch.setattr(CustomTefasClient, "_post_json", fail_on_network_fetch)
    monkeypatch.setattr(TefasSyncService, "sync_general_info", fail_on_sync)
    monkeypatch.setattr(TefasManagementFeeRefreshService, "refresh_fund_kind", fail_on_refresh)
    monkeypatch.setattr(TefasManagementFeeRefreshService, "refresh_fund_kinds", fail_on_refresh)
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_management_fee(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AAL/management-fee/current",
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_current_management_fee_does_not_commit_during_read(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_management_fee(db_session, asset_id=asset.id)

    def fail_on_commit(self):
        raise AssertionError("management-fee read endpoint should not commit")

    monkeypatch.setattr(SQLAlchemySession, "commit", fail_on_commit)

    response = client.get(
        "/api/v1/tefas/funds/AAL/management-fee/current",
        headers=auth_headers(token),
    )

    assert response.status_code == 200