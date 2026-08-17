from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, Session as SQLAlchemySession

from src.integrations.tefas_client import CustomTefasClient
from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.tefas_fund_allocation_data_repository import (
    TefasFundAllocationDataRepository,
    TefasFundAllocationRowCreate,
)
from src.services.tefas_sync_service import TefasSyncService


def register_user(
    client,
    *,
    email: str = "metrics-reader@example.com",
    username: str = "metrics-reader",
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


def login_user(client, *, email: str = "metrics-reader@example.com") -> str:
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
    fund_kind: str = "GYF",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind=fund_kind,
        currency=None,
        data_source="TEFAS",
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
    shares_outstanding: Decimal | None = Decimal("1000"),
    investor_count: int | None = 100,
    portfolio_size: Decimal | None = Decimal("10000"),
    exchange_bulletin_price: Decimal | None = None,
) -> TefasFundDailyData:
    row = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=shares_outstanding,
        investor_count=investor_count,
        portfolio_size=portfolio_size,
        exchange_bulletin_price=exchange_bulletin_price,
    )
    db_session.add(row)
    return row


def create_metrics_history(db_session: Session, *, asset_id: int) -> None:
    add_daily_data(
        db_session,
        asset_id=asset_id,
        data_date=date(2026, 7, 10),
        price=Decimal("100"),
        shares_outstanding=Decimal("900"),
        investor_count=90,
        portfolio_size=Decimal("9000"),
    )
    add_daily_data(
        db_session,
        asset_id=asset_id,
        data_date=date(2026, 8, 4),
        price=Decimal("80"),
        shares_outstanding=Decimal("800"),
        investor_count=80,
        portfolio_size=Decimal("8000"),
    )
    for item_date, price in [
        (date(2026, 8, 5), Decimal("90")),
        (date(2026, 8, 6), Decimal("95")),
        (date(2026, 8, 7), Decimal("98")),
    ]:
        add_daily_data(db_session, asset_id=asset_id, data_date=item_date, price=price)
    add_daily_data(
        db_session,
        asset_id=asset_id,
        data_date=date(2026, 8, 10),
        price=Decimal("100"),
        shares_outstanding=Decimal("1000"),
        investor_count=100,
        portfolio_size=Decimal("10000"),
    )
    add_daily_data(
        db_session,
        asset_id=asset_id,
        data_date=date(2026, 8, 11),
        price=Decimal("101"),
        shares_outstanding=Decimal("1000"),
        investor_count=100,
        portfolio_size=Decimal("10100"),
    )
    db_session.commit()


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


def test_authenticated_request_returns_metrics_response(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["fund_code"] == "AB1"
    assert body["fund_name"] == "AB1 GAYRIMENKUL YATIRIM FONU"
    assert body["data_date"] == "2026-08-11"


def test_metrics_response_contains_expected_baseline_dates(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    body = response.json()
    assert body["previous_observation_date"] == "2026-08-10"
    assert body["daily_return_baseline_date"] == "2026-08-10"
    assert body["five_observation_baseline_date"] == "2026-08-04"
    assert body["one_month_baseline_date"] == "2026-07-10"


def test_decimal_ratios_serialize_as_json_strings(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    body = response.json()
    assert body["daily_return_ratio"] == "0.01"
    assert body["five_observation_return_ratio"] == "0.2625"
    assert body["one_month_return_ratio"] == "0.01"


def test_metrics_response_exposes_short_term_evolution_metrics(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["five_observation_aum_change"] == "2100.0000"
    assert body["five_observation_aum_growth_ratio"] == "0.2625"
    assert body["five_observation_investor_count_change"] == 20
    assert body["five_observation_investor_count_growth_ratio"] == "0.25"
    assert body["one_month_aum_change"] == "1100.0000"
    assert body["one_month_aum_growth_ratio"] == "0.122222222222222222222222222"
    assert body["one_month_investor_count_change"] == 10
    assert body["one_month_investor_count_growth_ratio"] == "0.111111111111111111111111111"

def test_zero_changes_and_zero_growth_are_preserved(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    body = response.json()
    assert body["investor_count_change"] == 0
    assert body["investor_count_growth_ratio"] == "0"
    assert body["shares_outstanding_change"] == "0.0000"


def test_unavailable_metric_serializes_as_null(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("101"),
    )
    db_session.commit()

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["daily_return_ratio"] is None
    assert body["five_observation_return_ratio"] is None
    assert body["one_month_return_ratio"] is None



def test_authenticated_byf_metrics_response_exposes_byf_fields(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(
        db_session,
        asset_code="BLH",
        asset_name="BLH BYF",
        fund_kind="BYF",
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 10),
        price=Decimal("100"),
        exchange_bulletin_price=Decimal("100"),
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("100"),
        exchange_bulletin_price=Decimal("102"),
    )
    db_session.commit()

    response = client.get(
        "/api/v1/tefas/funds/BLH/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["byf_exchange_bulletin_daily_return_ratio"] == "0.02"
    assert body["byf_exchange_bulletin_daily_return_baseline_date"] == "2026-08-10"
    assert body["byf_exchange_bulletin_price_to_price_ratio"] == "0.02"


def test_byf_null_values_serialize_as_null(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(
        db_session,
        asset_code="BLH",
        asset_name="BLH BYF",
        fund_kind="BYF",
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 10),
        price=Decimal("100"),
        exchange_bulletin_price=Decimal("100"),
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("100"),
        exchange_bulletin_price=None,
    )
    db_session.commit()

    response = client.get(
        "/api/v1/tefas/funds/BLH/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["byf_exchange_bulletin_daily_return_ratio"] is None
    assert body["byf_exchange_bulletin_daily_return_baseline_date"] == "2026-08-10"
    assert body["byf_exchange_bulletin_price_to_price_ratio"] is None


def test_non_byf_response_contains_byf_fields_as_null(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 10),
        price=Decimal("100"),
        exchange_bulletin_price=Decimal("100"),
    )
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("101"),
        exchange_bulletin_price=Decimal("102"),
    )
    db_session.commit()

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["daily_return_ratio"] == "0.01"
    assert body["byf_exchange_bulletin_daily_return_ratio"] is None
    assert body["byf_exchange_bulletin_daily_return_baseline_date"] is None
    assert body["byf_exchange_bulletin_price_to_price_ratio"] is None
def test_lowercase_path_resolves_canonical_fund_code(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/ab1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["fund_code"] == "AB1"


def test_missing_fund_returns_404(client) -> None:
    token = create_authenticated_user(client)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund not found."


def test_existing_fund_without_exact_current_daily_row_returns_404(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 10),
        price=Decimal("100"),
    )
    db_session.commit()

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "TEFAS fund daily data not found."


def test_missing_date_query_returns_422(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_invalid_date_query_returns_422(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    create_tefas_asset(db_session)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=not-a-date",
        headers=auth_headers(token),
    )

    assert response.status_code == 422


def test_unauthenticated_request_returns_401(client, db_session: Session) -> None:
    create_tefas_asset(db_session)

    response = client.get("/api/v1/tefas/funds/AB1/metrics?date=2026-08-11")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication credentials were not provided or are invalid."


def test_authenticated_user_does_not_need_portfolio_ownership(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
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
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_endpoint_does_not_invoke_sync_or_backfill(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_on_sync(*args, **kwargs):
        raise AssertionError("TEFAS sync should not run")

    monkeypatch.setattr(TefasSyncService, "sync_general_info", fail_on_sync)
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_endpoint_does_not_commit_during_read(
    client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    def fail_on_commit(self):
        raise AssertionError("metrics endpoint should not commit")

    monkeypatch.setattr(SQLAlchemySession, "commit", fail_on_commit)

    response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert response.status_code == 200


def test_existing_allocation_route_remains_working(client, db_session: Session) -> None:
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
    allocation = response.json()["allocations"][0]
    assert allocation["label"] is not None
    assert allocation["raw_field_name"] is None
    assert allocation["percentage"] == "100.000000"
    assert allocation["mapping_status"] == "VERIFIED"

def test_exact_route_path_works_without_duplicate_api_prefix(client, db_session: Session) -> None:
    token = create_authenticated_user(client)
    asset = create_tefas_asset(db_session)
    create_metrics_history(db_session, asset_id=asset.id)

    exact_response = client.get(
        "/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )
    duplicated_prefix_response = client.get(
        "/api/v1/api/v1/tefas/funds/AB1/metrics?date=2026-08-11",
        headers=auth_headers(token),
    )

    assert exact_response.status_code == 200
    assert duplicated_prefix_response.status_code == 404


def test_controller_contains_no_metric_calculation_logic() -> None:
    controller_source = Path("src/controller/tefas_fund_controller.py").read_text()

    assert "_return_ratio" not in controller_source
    assert "Decimal(" not in controller_source
    assert "portfolio_size" not in controller_source
    assert "investor_count" not in controller_source
