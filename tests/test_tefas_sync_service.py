from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.services.tefas_sync_service import TefasSyncService


class FakeTefasService:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def fetch_general_info(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self.rows)


def _build_normalized_row(**overrides: Any) -> dict[str, Any]:
    row = {
        "fund_code": "AAL",
        "fund_name": "Example Fund",
        "fund_kind": "YAT",
        "data_date": date(2026, 4, 24),
        "price": Decimal("12.34567890"),
        "shares_outstanding": Decimal("1000.0000"),
        "investor_count": 100,
        "portfolio_size": Decimal("12345.6700"),
        "exchange_bulletin_price": None,
    }
    row.update(overrides)
    return row


def test_first_synchronization_inserts_data(db_session: Session) -> None:
    service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([_build_normalized_row()]),
    )

    result = service.sync_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    asset = db_session.scalar(select(Asset))
    daily_data = db_session.scalar(select(TefasFundDailyData))

    assert asset is not None
    assert daily_data is not None
    assert asset.asset_code == "AAL"
    assert asset.asset_name == "Example Fund"
    assert asset.asset_type == "FUND"
    assert asset.fund_kind == "YAT"
    assert asset.currency is None
    assert asset.data_source == "TEFAS"
    assert asset.is_active is True
    assert daily_data.asset_id == asset.id
    assert daily_data.data_date == date(2026, 4, 24)
    assert daily_data.price == Decimal("12.34567890")
    assert daily_data.shares_outstanding == Decimal("1000.0000")
    assert daily_data.investor_count == 100
    assert daily_data.portfolio_size == Decimal("12345.6700")
    assert daily_data.exchange_bulletin_price is None
    assert result.fetched_rows == 1
    assert result.assets_created == 1
    assert result.assets_updated == 0
    assert result.daily_rows_created == 1
    assert result.daily_rows_updated == 0



def test_repeated_identical_synchronization_creates_no_duplicates(db_session: Session) -> None:
    row = _build_normalized_row()
    service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([row]),
    )

    service.sync_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )
    second_result = service.sync_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    asset_count = db_session.scalar(select(func.count()).select_from(Asset))
    daily_count = db_session.scalar(select(func.count()).select_from(TefasFundDailyData))

    assert asset_count == 1
    assert daily_count == 1
    assert second_result.fetched_rows == 1
    assert second_result.assets_created == 0
    assert second_result.assets_updated == 0
    assert second_result.daily_rows_created == 0
    assert second_result.daily_rows_updated == 0



def test_existing_asset_and_daily_row_are_updated(db_session: Session) -> None:
    initial_service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([_build_normalized_row()]),
    )
    initial_service.sync_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    updated_row = _build_normalized_row(
        fund_name="Updated Fund Name",
        price=Decimal("13.00000000"),
        investor_count=120,
        portfolio_size=Decimal("13000.0000"),
    )
    update_service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([updated_row]),
    )

    second_result = update_service.sync_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    asset_count = db_session.scalar(select(func.count()).select_from(Asset))
    daily_count = db_session.scalar(select(func.count()).select_from(TefasFundDailyData))
    asset = db_session.scalar(select(Asset))
    daily_data = db_session.scalar(select(TefasFundDailyData))

    assert asset_count == 1
    assert daily_count == 1
    assert asset is not None
    assert daily_data is not None
    assert asset.asset_name == "Updated Fund Name"
    assert daily_data.price == Decimal("13.00000000")
    assert daily_data.investor_count == 120
    assert daily_data.portfolio_size == Decimal("13000.0000")
    assert second_result.assets_created == 0
    assert second_result.assets_updated == 1
    assert second_result.daily_rows_created == 0
    assert second_result.daily_rows_updated == 1



def test_same_asset_on_different_date_creates_only_new_daily_row(db_session: Session) -> None:
    first_service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([_build_normalized_row(data_date=date(2026, 4, 24))]),
    )
    first_service.sync_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    second_service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([_build_normalized_row(data_date=date(2026, 4, 25))]),
    )
    second_result = second_service.sync_general_info(
        start_date=date(2026, 4, 25),
        end_date=date(2026, 4, 25),
    )

    asset_count = db_session.scalar(select(func.count()).select_from(Asset))
    daily_count = db_session.scalar(select(func.count()).select_from(TefasFundDailyData))

    assert asset_count == 1
    assert daily_count == 2
    assert second_result.assets_created == 0
    assert second_result.assets_updated == 0
    assert second_result.daily_rows_created == 1
    assert second_result.daily_rows_updated == 0



def test_empty_response_changes_nothing(db_session: Session) -> None:
    service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([]),
    )

    result = service.sync_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    asset_count = db_session.scalar(select(func.count()).select_from(Asset))
    daily_count = db_session.scalar(select(func.count()).select_from(TefasFundDailyData))

    assert result.fetched_rows == 0
    assert result.assets_created == 0
    assert result.assets_updated == 0
    assert result.daily_rows_created == 0
    assert result.daily_rows_updated == 0
    assert asset_count == 0
    assert daily_count == 0



def test_processing_failure_rolls_back_complete_transaction(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    def raising_add(self: TefasFundDailyDataRepository, daily_data: TefasFundDailyData) -> TefasFundDailyData:
        raise RuntimeError("daily data add failed")

    monkeypatch.setattr(TefasFundDailyDataRepository, "add", raising_add)

    service = TefasSyncService(
        db_session,
        tefas_service=FakeTefasService([_build_normalized_row()]),
    )

    with pytest.raises(RuntimeError, match="daily data add failed"):
        service.sync_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )

    db_session.expire_all()

    asset_count = db_session.scalar(select(func.count()).select_from(Asset))
    daily_count = db_session.scalar(select(func.count()).select_from(TefasFundDailyData))

    assert asset_count == 0
    assert daily_count == 0
