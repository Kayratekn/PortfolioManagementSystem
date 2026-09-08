from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, Session as SQLAlchemySession

from src.integrations.tefas_client import CustomTefasClient
from src.model.asset import Asset
from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot
from src.services.tefas_sync_service import TefasSyncService


def register_user(
    client,
    *,
    email: str = "metadata-reader@example.com",
    username: str = "metadata-reader",
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


def login_user(client, *, email: str = "metadata-reader@example.com") -> str:
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
    isin: str | None = "TRMAALWWWWW5",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind=fund_kind,
        isin=isin,
        currency=currency,
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def add_detail_snapshot(
    db_session: Session,
    *,
    asset_id: int,
    observed_at: datetime = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
    fund_category: str = "Para Piyasasi",
    category_rank: int | None = 1,
    category_fund_count: int | None = 10,
    market_share_raw: Decimal | None = Decimal("1.2345678901"),
    risk_value: int | None = 3,
    tefas_status: str | None = "TEFAS/BEFAS",
    transaction_start_time: str | None = "09:00",
    transaction_end_time: str | None = "17:00",
    entry_commission_raw: Decimal | None = Decimal("3.0000000000"),
    exit_commission_raw: Decimal | None = Decimal("0.5000000000"),
    interest_content: str | None = "Faiz icerir",
    fund_sale_valor: int | None = 0,
    fund_redemption_valor: int | None = 3,
    source_page: str = "fon-detayli-analiz",
) -> TefasFundDetailSnapshot:
    snapshot = TefasFundDetailSnapshot(
        asset_id=asset_id,
        observed_at=observed_at,
        source_page=source_page,
        fund_category=fund_category,
        category_rank=category_rank,
        category_fund_count=category_fund_count,
        market_share_raw=market_share_raw,
        risk_value=risk_value,
        tefas_status=tefas_status,
        transaction_start_time=transaction_start_time,
        transaction_end_time=transaction_end_time,
        entry_commission_raw=entry_commission_raw,
        exit_commission_raw=exit_commission_raw,
        interest_content=interest_content,
        fund_sale_valor=fund_sale_valor,
        fund_redemption_valor=fund_redemption_valor,
    )
    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)
    return snapshot


def test_latest_metadata_requires_authentication(client, db_session: Session) -> None:
    create_tefas_asset(db_session)

    response = client.get("/api/v1/tefas/funds/AAL/metadata/latest")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_latest_metadata_returns_canonical_response_and_decimal_strings(
    client,
    db_session: Session,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_detail_snapshot(
        db_session,
        asset_id=asset.id,
        observed_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
        market_share_raw=Decimal("0.1000000000"),
    )
    add_detail_snapshot(
        db_session,
        asset_id=asset.id,
        observed_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        market_share_raw=Decimal("1.2345678901"),
        entry_commission_raw=Decimal("3.0000000000"),
        exit_commission_raw=Decimal("0.5000000000"),
    )

    response = client.get(
        "/api/v1/tefas/funds/ aal /metadata/latest",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body == {
        "asset_id": asset.id,
        "fund_code": "AAL",
        "fund_name": "AAL TEST FUND",
        "fund_kind": "YAT",
        "isin": "TRMAALWWWWW5",
        "currency": "TRY",
        "observed_at": "2026-08-11T12:00:00",
        "source_page": "fon-detayli-analiz",
        "fund_category": "Para Piyasasi",
        "category_rank": 1,
        "category_fund_count": 10,
        "market_share_raw": "1.2345678901",
        "risk_value": 3,
        "tefas_status": "TEFAS/BEFAS",
        "transaction_start_time": "09:00",
        "transaction_end_time": "17:00",
        "entry_commission_raw": "3.0000000000",
        "exit_commission_raw": "0.5000000000",
        "interest_content": "Faiz icerir",
        "fund_sale_valor": 0,
        "fund_redemption_valor": 3,
    }


def test_latest_metadata_preserves_nullable_fields(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session, fund_kind=None, isin=None, currency="TRY")
    add_detail_snapshot(
        db_session,
        asset_id=asset.id,
        category_rank=None,
        category_fund_count=None,
        market_share_raw=None,
        risk_value=None,
        tefas_status=None,
        transaction_start_time=None,
        transaction_end_time=None,
        entry_commission_raw=None,
        exit_commission_raw=None,
        interest_content=None,
        fund_sale_valor=None,
        fund_redemption_valor=None,
    )

    response = client.get(
        "/api/v1/tefas/funds/AAL/metadata/latest",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fund_kind"] is None
    assert body["isin"] is None
    assert body["currency"] == "TRY"
    assert body["category_rank"] is None
    assert body["category_fund_count"] is None
    assert body["market_share_raw"] is None
    assert body["risk_value"] is None
    assert body["tefas_status"] is None
    assert body["transaction_start_time"] is None
    assert body["transaction_end_time"] is None
    assert body["entry_commission_raw"] is None
    assert body["exit_commission_raw"] is None
    assert body["interest_content"] is None
    assert body["fund_sale_valor"] is None
    assert body["fund_redemption_valor"] is None


def test_latest_metadata_missing_tefas_asset_returns_404(client) -> None:
    token = create_authenticated_user(client)

    response = client.get(
        "/api/v1/tefas/funds/AAL/metadata/latest",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund not found."


def test_latest_metadata_existing_asset_without_snapshot_returns_404(
    client,
    db_session: Session,
) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AAL/metadata/latest",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund detail metadata not found."


def test_latest_metadata_does_not_trigger_tefas_network_or_sync(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_network_fetch(*args, **kwargs):
        raise AssertionError("TEFAS network fetch should not run")

    def fail_on_sync(*args, **kwargs):
        raise AssertionError("TEFAS sync should not run")

    monkeypatch.setattr(CustomTefasClient, "_post_json", fail_on_network_fetch)
    monkeypatch.setattr(TefasSyncService, "sync_general_info", fail_on_sync)
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_detail_snapshot(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AAL/metadata/latest",
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_latest_metadata_does_not_commit_during_read(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_detail_snapshot(db_session, asset_id=asset.id)

    def fail_on_commit(self):
        raise AssertionError("metadata read endpoint should not commit")

    monkeypatch.setattr(SQLAlchemySession, "commit", fail_on_commit)

    response = client.get(
        "/api/v1/tefas/funds/AAL/metadata/latest",
        headers=auth_headers(token),
    )

    assert response.status_code == 200