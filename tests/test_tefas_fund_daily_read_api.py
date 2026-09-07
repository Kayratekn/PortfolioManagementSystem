from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session, Session as SQLAlchemySession

from src.integrations.tefas_client import CustomTefasClient
from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.services.tefas_sync_service import TefasSyncService


def register_user(
    client,
    *,
    email: str = "daily-reader@example.com",
    username: str = "daily-reader",
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


def login_user(client, *, email: str = "daily-reader@example.com") -> str:
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
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind=fund_kind,
        currency=currency,
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date,
    price: Decimal,
    exchange_bulletin_price: Decimal | None = None,
    shares_outstanding: Decimal | None = Decimal("1000.0000"),
    investor_count: int | None = 100,
    portfolio_size: Decimal | None = Decimal("10000.0000"),
) -> TefasFundDailyData:
    row = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        exchange_bulletin_price=exchange_bulletin_price,
        shares_outstanding=shares_outstanding,
        investor_count=investor_count,
        portfolio_size=portfolio_size,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    return row


def test_latest_requires_authentication(client, db_session: Session) -> None:
    create_tefas_asset(db_session)

    response = client.get("/api/v1/tefas/funds/AAL/latest")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_latest_returns_canonical_fund_and_latest_observation(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("100"))
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("101.12345678"),
        exchange_bulletin_price=Decimal("102.12345678"),
        shares_outstanding=Decimal("1234.5678"),
        investor_count=321,
        portfolio_size=Decimal("98765.4321"),
    )

    response = client.get(
        "/api/v1/tefas/funds/aal/latest",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset.id
    assert body["fund_code"] == "AAL"
    assert body["fund_name"] == "AAL TEST FUND"
    assert body["fund_kind"] == "YAT"
    assert body["currency"] == "TRY"
    assert body["observation"] == {
        "data_date": "2026-08-11",
        "price": "101.12345678",
        "exchange_bulletin_price": "102.12345678",
        "shares_outstanding": "1234.5678",
        "investor_count": 321,
        "portfolio_size": "98765.4321",
    }


def test_latest_preserves_nullable_values(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session, fund_kind=None, currency=None)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("101.12345678"),
        exchange_bulletin_price=None,
        shares_outstanding=None,
        investor_count=None,
        portfolio_size=None,
    )

    response = client.get("/api/v1/tefas/funds/AAL/latest", headers=auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["fund_kind"] is None
    assert body["currency"] is None
    assert body["observation"]["exchange_bulletin_price"] is None
    assert body["observation"]["shares_outstanding"] is None
    assert body["observation"]["investor_count"] is None
    assert body["observation"]["portfolio_size"] is None


def test_latest_missing_tefas_asset_returns_404(client) -> None:
    token = create_authenticated_user(client)

    response = client.get("/api/v1/tefas/funds/AAL/latest", headers=auth_headers(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund not found."


def test_latest_existing_fund_without_daily_row_returns_404(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get("/api/v1/tefas/funds/AAL/latest", headers=auth_headers(token))

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund daily data not found."


def test_history_requires_authentication(client, db_session: Session) -> None:
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AAL/history?start_date=2026-08-10&end_date=2026-08-11"
    )

    assert response.status_code == 401


def test_history_returns_inclusive_ordered_stored_observations(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    other_asset = create_tefas_asset(db_session, asset_code="BLH")
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 9), price=Decimal("99"))
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("100"))
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("101"))
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 12), price=Decimal("102"))
    add_daily_data(db_session, asset_id=other_asset.id, data_date=date(2026, 8, 10), price=Decimal("200"))

    response = client.get(
        "/api/v1/tefas/funds/AAL/history?start_date=2026-08-10&end_date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["asset_id"] == asset.id
    assert body["fund_code"] == "AAL"
    assert body["total"] == 2
    assert [item["data_date"] for item in body["items"]] == ["2026-08-10", "2026-08-11"]
    assert [item["price"] for item in body["items"]] == ["100.00000000", "101.00000000"]


def test_history_valid_empty_range_returns_empty_list(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 9), price=Decimal("99"))

    response = client.get(
        "/api/v1/tefas/funds/AAL/history?start_date=2026-08-10&end_date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


def test_history_start_after_end_returns_422(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AAL/history?start_date=2026-08-12&end_date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_history_missing_tefas_asset_returns_404(client) -> None:
    token = create_authenticated_user(client)

    response = client.get(
        "/api/v1/tefas/funds/AAL/history?start_date=2026-08-10&end_date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund not found."


def test_daily_read_endpoints_do_not_trigger_tefas_network_or_sync(
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
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("101"))

    latest_response = client.get("/api/v1/tefas/funds/AAL/latest", headers=auth_headers(token))
    history_response = client.get(
        "/api/v1/tefas/funds/AAL/history?start_date=2026-08-10&end_date=2026-08-11",
        headers=auth_headers(token),
    )

    assert latest_response.status_code == 200
    assert history_response.status_code == 200


def test_daily_read_endpoints_do_not_commit_during_read(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("101"))

    def fail_on_commit(self):
        raise AssertionError("daily read endpoint should not commit")

    monkeypatch.setattr(SQLAlchemySession, "commit", fail_on_commit)

    response = client.get("/api/v1/tefas/funds/AAL/latest", headers=auth_headers(token))

    assert response.status_code == 200