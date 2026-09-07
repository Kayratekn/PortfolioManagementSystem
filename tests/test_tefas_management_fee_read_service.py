from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_management_fee_history import TefasManagementFeeHistory
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_management_fee_history_repository import TefasManagementFeeHistoryRepository
from src.services.tefas_management_fee_read_service import TefasManagementFeeReadService


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_name: str = "AAL Fund",
    data_source: str = "TEFAS",
    fund_kind: str | None = "YAT",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind=fund_kind,
        data_source=data_source,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_management_fee(
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
    db_session.flush()
    return history


def _service(db_session: Session) -> TefasManagementFeeReadService:
    return TefasManagementFeeReadService(
        asset_repository=AssetRepository(db_session),
        management_fee_history_repository=TefasManagementFeeHistoryRepository(db_session),
    )


def test_current_management_fee_normalizes_fund_code_and_returns_current_row(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session, asset_code="AAL", asset_name="AAL TEST FUND")
    closed = _add_management_fee(
        db_session,
        asset_id=asset.id,
        management_fee_percentage=Decimal("2.000000"),
        closed_at=datetime(2026, 8, 10, 10, 0, tzinfo=timezone.utc),
    )
    current = _add_management_fee(
        db_session,
        asset_id=asset.id,
        management_fee_percentage=Decimal("1.750000"),
        source_endpoint="fonYonetimBazliBilgiGetir",
        source_field_name="uygulananYu1Y",
    )

    result = _service(db_session).get_current_management_fee(fund_code="  aal  ")

    assert result.asset_id == asset.id
    assert result.fund_code == "AAL"
    assert result.fund_name == "AAL TEST FUND"
    assert result.fund_kind == "YAT"
    assert result.management_fee_percentage == Decimal("1.750000")
    assert result.management_fee_percentage != Decimal("0.017500")
    assert result.first_observed_at == current.first_observed_at
    assert result.last_observed_at == current.last_observed_at
    assert result.source_endpoint == "fonYonetimBazliBilgiGetir"
    assert result.source_field_name == "uygulananYu1Y"
    assert result.management_fee_percentage != closed.management_fee_percentage


def test_current_management_fee_accepts_emk(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="EMK1", fund_kind="EMK")
    _add_management_fee(db_session, asset_id=asset.id)

    result = _service(db_session).get_current_management_fee(fund_code="EMK1")

    assert result.fund_kind == "EMK"
    assert result.management_fee_percentage == Decimal("1.750000")


def test_missing_tefas_asset_raises_404(db_session: Session) -> None:
    _create_asset(db_session, asset_code="AAL", data_source="MANUAL")

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_current_management_fee(fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS fund not found."


@pytest.mark.parametrize("fund_kind", ["BYF", "GYF", "GSYF", None])
def test_unsupported_fund_kind_raises_not_found_even_with_fee_row(
    db_session: Session,
    fund_kind: str | None,
) -> None:
    asset = _create_asset(db_session, fund_kind=fund_kind)
    _add_management_fee(db_session, asset_id=asset.id)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_current_management_fee(fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS management fee not found."


def test_supported_asset_without_current_fee_raises_not_found(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_management_fee(
        db_session,
        asset_id=asset.id,
        closed_at=datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_current_management_fee(fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS management fee not found."


def test_service_does_not_write_or_commit(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    asset = _create_asset(db_session)
    _add_management_fee(db_session, asset_id=asset.id)
    commit_calls = 0
    flush_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    def counting_flush(*args: object, **kwargs: object) -> None:
        nonlocal flush_calls
        flush_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    monkeypatch.setattr(db_session, "flush", counting_flush)

    _service(db_session).get_current_management_fee(fund_code="AAL")

    assert commit_calls == 0
    assert flush_calls == 0