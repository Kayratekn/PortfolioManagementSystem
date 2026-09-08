from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_detail_snapshot_repository import TefasFundDetailSnapshotRepository
from src.services.tefas_fund_metadata_read_service import TefasFundMetadataReadService


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_name: str = "AAL Fund",
    data_source: str = "TEFAS",
    fund_kind: str | None = "YAT",
    isin: str | None = "TRMAALWWWWW5",
    currency: str | None = "TRY",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind=fund_kind,
        isin=isin,
        currency=currency,
        data_source=data_source,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_snapshot(
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
    db_session.flush()
    return snapshot


def _service(db_session: Session) -> TefasFundMetadataReadService:
    return TefasFundMetadataReadService(
        asset_repository=AssetRepository(db_session),
        detail_snapshot_repository=TefasFundDetailSnapshotRepository(db_session),
    )


def test_latest_metadata_normalizes_fund_code_and_returns_latest_snapshot(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session, asset_code="AAL", asset_name="AAL TEST FUND")
    _add_snapshot(
        db_session,
        asset_id=asset.id,
        observed_at=datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc),
        market_share_raw=Decimal("0.1000000000"),
    )
    latest = _add_snapshot(
        db_session,
        asset_id=asset.id,
        observed_at=datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc),
        market_share_raw=Decimal("1.2345678901"),
        entry_commission_raw=Decimal("3.0000000000"),
        exit_commission_raw=Decimal("0.5000000000"),
    )

    result = _service(db_session).get_latest_metadata(fund_code="  aal  ")

    assert result.asset_id == asset.id
    assert result.fund_code == "AAL"
    assert result.fund_name == "AAL TEST FUND"
    assert result.fund_kind == "YAT"
    assert result.isin == "TRMAALWWWWW5"
    assert result.currency == "TRY"
    assert result.observed_at == latest.observed_at
    assert result.source_page == "fon-detayli-analiz"
    assert result.fund_category == "Para Piyasasi"
    assert result.category_rank == 1
    assert result.category_fund_count == 10
    assert result.market_share_raw == Decimal("1.2345678901")
    assert result.risk_value == 3
    assert result.tefas_status == "TEFAS/BEFAS"
    assert result.transaction_start_time == "09:00"
    assert result.transaction_end_time == "17:00"
    assert result.entry_commission_raw == Decimal("3.0000000000")
    assert result.exit_commission_raw == Decimal("0.5000000000")
    assert result.interest_content == "Faiz icerir"
    assert result.fund_sale_valor == 0
    assert result.fund_redemption_valor == 3


def test_latest_metadata_preserves_nullable_fields(db_session: Session) -> None:
    asset = _create_asset(db_session, fund_kind=None, isin=None, currency="TRY")
    _add_snapshot(
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

    result = _service(db_session).get_latest_metadata(fund_code="AAL")

    assert result.fund_kind is None
    assert result.isin is None
    assert result.currency == "TRY"
    assert result.category_rank is None
    assert result.category_fund_count is None
    assert result.market_share_raw is None
    assert result.risk_value is None
    assert result.tefas_status is None
    assert result.transaction_start_time is None
    assert result.transaction_end_time is None
    assert result.entry_commission_raw is None
    assert result.exit_commission_raw is None
    assert result.interest_content is None
    assert result.fund_sale_valor is None
    assert result.fund_redemption_valor is None


def test_missing_tefas_asset_raises_404(db_session: Session) -> None:
    _create_asset(db_session, asset_code="AAL", data_source="MANUAL")

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_latest_metadata(fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS fund not found."


def test_existing_tefas_asset_without_detail_snapshot_raises_404(db_session: Session) -> None:
    _create_asset(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_latest_metadata(fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS fund detail metadata not found."


def test_service_does_not_write_or_commit(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    asset = _create_asset(db_session)
    _add_snapshot(db_session, asset_id=asset.id)
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

    _service(db_session).get_latest_metadata(fund_code="AAL")

    assert commit_calls == 0
    assert flush_calls == 0