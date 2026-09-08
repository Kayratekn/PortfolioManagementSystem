from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from scripts.backfill_tefas_asset_currency import build_parser
from src.model.asset import Asset
from src.repositories.asset_repository import AssetRepository
from src.services.tefas_asset_currency_backfill_service import (
    TefasAssetCurrencyBackfillService,
    TefasAssetCurrencyConflictError,
)


def _add_asset(
    db_session: Session,
    *,
    asset_code: str,
    data_source: str = "TEFAS",
    currency: str | None = None,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Asset",
        asset_type="FUND",
        fund_kind="YAT",
        currency=currency,
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _service(db_session: Session) -> TefasAssetCurrencyBackfillService:
    return TefasAssetCurrencyBackfillService(
        db=db_session,
        asset_repository=AssetRepository(db_session),
    )


def test_backfill_script_defaults_to_dry_run() -> None:
    assert build_parser().parse_args([]).apply is False


def test_backfill_dry_run_reports_scope_without_mutation(db_session: Session) -> None:
    tefas_null = _add_asset(db_session, asset_code="TEFASNULL")
    _add_asset(db_session, asset_code="TEFASTRY", currency="TRY")
    manual_null = _add_asset(
        db_session,
        asset_code="MANUALNULL",
        data_source="MANUAL",
    )
    db_session.commit()

    result = _service(db_session).inspect()

    db_session.refresh(tefas_null)
    db_session.refresh(manual_null)
    assert result.null_currency_count == 1
    assert result.try_currency_count == 1
    assert result.non_try_currency_conflict_count == 0
    assert result.applied is False
    assert result.affected_count == 0
    assert tefas_null.currency is None
    assert manual_null.currency is None


def test_backfill_apply_changes_only_tefas_null_currency_and_is_idempotent(
    db_session: Session,
) -> None:
    tefas_null = _add_asset(db_session, asset_code="TEFASNULL")
    tefas_try = _add_asset(db_session, asset_code="TEFASTRY", currency="TRY")
    manual_null = _add_asset(
        db_session,
        asset_code="MANUALNULL",
        data_source="MANUAL",
    )
    db_session.commit()

    first = _service(db_session).apply()
    second = _service(db_session).apply()

    db_session.expire_all()
    rows = {asset.asset_code: asset for asset in db_session.scalars(select(Asset))}
    assert first.applied is True
    assert first.affected_count == 1
    assert second.applied is True
    assert second.affected_count == 0
    assert rows[tefas_null.asset_code].currency == "TRY"
    assert rows[tefas_try.asset_code].currency == "TRY"
    assert rows[manual_null.asset_code].currency is None


def test_backfill_conflict_aborts_without_mutation(db_session: Session) -> None:
    tefas_null = _add_asset(db_session, asset_code="TEFASNULL")
    conflicting = _add_asset(db_session, asset_code="TEFASUSD", currency="USD")
    db_session.commit()

    with pytest.raises(TefasAssetCurrencyConflictError):
        _service(db_session).apply()

    db_session.refresh(tefas_null)
    db_session.refresh(conflicting)
    assert tefas_null.currency is None
    assert conflicting.currency == "USD"