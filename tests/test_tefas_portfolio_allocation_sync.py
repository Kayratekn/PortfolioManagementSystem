from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_allocation_data import TefasFundAllocationData
from src.repositories.tefas_fund_allocation_data_repository import (
    TefasFundAllocationDataRepository,
    TefasFundAllocationRowCreate,
)
from src.services.tefas_service import (
    EXPECTED_ALLOCATION_FIELDS,
    TefasPortfolioAllocationItem,
    TefasPortfolioBreakdownSnapshot,
    TefasService,
)
from src.services.tefas_sync_service import TefasPortfolioAllocationSyncResult, TefasSyncService


class FakePortfolioBreakdownTefasService:
    def __init__(
        self,
        raw_rows: list[dict[str, Any]],
        normalized_snapshots: dict[int, TefasPortfolioBreakdownSnapshot],
    ) -> None:
        self.raw_rows = raw_rows
        self.normalized_snapshots = normalized_snapshots

    def fetch_portfolio_breakdown_raw(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self.raw_rows)

    def normalize_portfolio_breakdown_row(
        self,
        raw_row: dict[str, Any],
    ) -> TefasPortfolioBreakdownSnapshot:
        return self.normalized_snapshots[id(raw_row)]


class FakePortfolioBreakdownClient:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response

    def fetch_portfolio_breakdown(self, **kwargs: Any) -> dict[str, Any]:
        return self.response


class RaisingNormalizeTefasService:
    def __init__(self, raw_rows: list[dict[str, Any]], message: str) -> None:
        self.raw_rows = raw_rows
        self.message = message

    def fetch_portfolio_breakdown_raw(self, **kwargs: Any) -> list[dict[str, Any]]:
        return list(self.raw_rows)

    def normalize_portfolio_breakdown_row(
        self,
        raw_row: dict[str, Any],
    ) -> TefasPortfolioBreakdownSnapshot:
        raise ValueError(self.message)


class EmptyPortfolioBreakdownTefasService:
    def fetch_portfolio_breakdown_raw(self, **kwargs: Any) -> list[dict[str, Any]]:
        return []


def _create_asset(db_session: Session, *, asset_code: str = "AAL") -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency=None,
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _build_raw_row(tag: str) -> dict[str, Any]:
    return {"tag": tag}


def _build_real_portfolio_row(
    *,
    fund_code: str,
    fund_name: str,
    data_date: str = "2026-08-11",
    allocations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "fonKodu": fund_code,
        "fonUnvan": fund_name,
        "tarih": data_date,
        "bilFiyat": None,
    }
    row.update({field_name: None for field_name in EXPECTED_ALLOCATION_FIELDS})
    if allocations:
        row.update(allocations)
    return row


def _build_snapshot(
    *,
    fund_code: str = "AAL",
    fund_name: str = "Example Fund",
    data_date: date = date(2026, 8, 11),
    allocations: tuple[TefasPortfolioAllocationItem, ...] = (),
) -> TefasPortfolioBreakdownSnapshot:
    return TefasPortfolioBreakdownSnapshot(
        fund_code=fund_code,
        fund_name=fund_name,
        data_date=data_date,
        allocations=allocations,
    )


def _build_item(
    raw_field_name: str,
    value: str,
    *,
    label: str | None,
    mapping_status: str,
) -> TefasPortfolioAllocationItem:
    return TefasPortfolioAllocationItem(
        raw_field_name=raw_field_name,
        allocation_percentage=Decimal(value),
        label=label,
        mapping_status=mapping_status,
    )


def _replace_existing_snapshot(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date,
    rows: list[TefasFundAllocationRowCreate],
) -> None:
    repository = TefasFundAllocationDataRepository(db_session)
    repository.replace_for_asset_and_date(
        asset_id=asset_id,
        data_date=data_date,
        rows=rows,
    )
    db_session.commit()


def _load_allocations(db_session: Session) -> list[TefasFundAllocationData]:
    statement = select(TefasFundAllocationData).order_by(
        TefasFundAllocationData.asset_id,
        TefasFundAllocationData.data_date,
        TefasFundAllocationData.raw_field_name,
    )
    return list(db_session.scalars(statement))


def test_sync_portfolio_breakdown_persists_allocations_and_commits(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = _create_asset(db_session)
    raw_row = _build_raw_row("first")
    snapshot = _build_snapshot(
        allocations=(
            _build_item("bb", "5.50", label=None, mapping_status="UNRESOLVED"),
            _build_item("hs", "80.25", label="Hisse Senedi", mapping_status="VERIFIED"),
            _build_item("r", "-1.25", label="Repo", mapping_status="VERIFIED"),
            _build_item("vmtl", "0", label="Mevduat (TL)", mapping_status="VERIFIED"),
        )
    )
    service = TefasSyncService(
        db_session,
        tefas_service=FakePortfolioBreakdownTefasService(
            [raw_row],
            {id(raw_row): snapshot},
        ),
    )

    commit_calls = 0
    original_commit = db_session.commit

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        original_commit()

    monkeypatch.setattr(db_session, "commit", counting_commit)

    result = service.sync_portfolio_breakdown(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
    )

    rows = _load_allocations(db_session)

    assert commit_calls == 1
    assert isinstance(result, TefasPortfolioAllocationSyncResult)
    assert result.fetched_fund_count == 1
    assert result.synced_fund_count == 1
    assert result.persisted_allocation_count == 4
    assert [(row.raw_field_name, row.allocation_percentage) for row in rows] == [
        ("bb", Decimal("5.500000")),
        ("hs", Decimal("80.250000")),
        ("r", Decimal("-1.250000")),
        ("vmtl", Decimal("0.000000")),
    ]
    assert all(row.asset_id == asset.id for row in rows)
    assert all(row.data_date == date(2026, 8, 11) for row in rows)
    assert not any(hasattr(row, "label") for row in rows)
    assert not any(hasattr(row, "mapping_status") for row in rows)


def test_sync_portfolio_breakdown_filters_requested_fund_code_before_sync_processing(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session, asset_code="AB1")
    tefas_service = TefasService(
        client=FakePortfolioBreakdownClient(
            {
                "errorCode": None,
                "errorMessage": None,
                "resultList": [
                    _build_real_portfolio_row(
                        fund_code="AB1",
                        fund_name="Fund AB1",
                        allocations={"gyy": 100},
                    ),
                    _build_real_portfolio_row(
                        fund_code="AB2",
                        fund_name="Fund AB2",
                        allocations={"gyy": 100},
                    ),
                ],
            }
        )
    )  # type: ignore[arg-type]
    service = TefasSyncService(db_session, tefas_service=tefas_service)

    result = service.sync_portfolio_breakdown(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    rows = _load_allocations(db_session)

    assert asset.id is not None
    assert result == TefasPortfolioAllocationSyncResult(
        fetched_fund_count=1,
        synced_fund_count=1,
        persisted_allocation_count=1,
    )
    assert [(row.asset_id, row.raw_field_name, row.allocation_percentage) for row in rows] == [
        (asset.id, "gyy", Decimal("100.000000")),
    ]


def test_resync_replaces_snapshot_and_removes_stale_fields(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_existing_snapshot(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        rows=[
            TefasFundAllocationRowCreate(
                asset_id=asset.id,
                data_date=date(2026, 8, 11),
                raw_field_name="hs",
                allocation_percentage=Decimal("80"),
            ),
            TefasFundAllocationRowCreate(
                asset_id=asset.id,
                data_date=date(2026, 8, 11),
                raw_field_name="vmtl",
                allocation_percentage=Decimal("20"),
            ),
        ],
    )

    raw_row = _build_raw_row("updated")
    snapshot = _build_snapshot(
        allocations=(
            _build_item("hs", "100", label="Hisse Senedi", mapping_status="VERIFIED"),
        )
    )
    service = TefasSyncService(
        db_session,
        tefas_service=FakePortfolioBreakdownTefasService([raw_row], {id(raw_row): snapshot}),
    )

    result = service.sync_portfolio_breakdown(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
    )

    rows = _load_allocations(db_session)

    assert result.fetched_fund_count == 1
    assert result.synced_fund_count == 1
    assert result.persisted_allocation_count == 1
    assert [(row.raw_field_name, row.allocation_percentage) for row in rows] == [
        ("hs", Decimal("100.000000")),
    ]


def test_all_null_snapshot_removes_stale_rows(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_existing_snapshot(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        rows=[
            TefasFundAllocationRowCreate(
                asset_id=asset.id,
                data_date=date(2026, 8, 11),
                raw_field_name="hs",
                allocation_percentage=Decimal("80"),
            ),
        ],
    )

    raw_row = _build_raw_row("all-null")
    snapshot = _build_snapshot(allocations=())
    service = TefasSyncService(
        db_session,
        tefas_service=FakePortfolioBreakdownTefasService([raw_row], {id(raw_row): snapshot}),
    )

    result = service.sync_portfolio_breakdown(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
    )

    assert result.fetched_fund_count == 1
    assert result.synced_fund_count == 1
    assert result.persisted_allocation_count == 0
    assert _load_allocations(db_session) == []


def test_missing_asset_raises_and_rolls_back(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_row = _build_raw_row("missing-asset")
    snapshot = _build_snapshot(
        fund_code="ZZZ",
        allocations=(
            _build_item("hs", "10", label="Hisse Senedi", mapping_status="VERIFIED"),
        ),
    )
    service = TefasSyncService(
        db_session,
        tefas_service=FakePortfolioBreakdownTefasService([raw_row], {id(raw_row): snapshot}),
    )

    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(ValueError, match="Missing TEFAS asset"):
        service.sync_portfolio_breakdown(
            start_date=date(2026, 8, 11),
            end_date=date(2026, 8, 11),
        )

    assert rollback_calls == 1
    assert db_session.scalar(select(func.count()).select_from(TefasFundAllocationData)) == 0


def test_normalization_failure_rolls_back_without_changing_existing_rows(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset = _create_asset(db_session)
    _replace_existing_snapshot(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        rows=[
            TefasFundAllocationRowCreate(
                asset_id=asset.id,
                data_date=date(2026, 8, 11),
                raw_field_name="hs",
                allocation_percentage=Decimal("80"),
            ),
        ],
    )
    raw_row = _build_raw_row("bad-row")
    service = TefasSyncService(
        db_session,
        tefas_service=RaisingNormalizeTefasService([raw_row], "schema drift"),
    )

    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(ValueError, match="schema drift"):
        service.sync_portfolio_breakdown(
            start_date=date(2026, 8, 11),
            end_date=date(2026, 8, 11),
        )

    rows = _load_allocations(db_session)

    assert rollback_calls == 1
    assert [(row.raw_field_name, row.allocation_percentage) for row in rows] == [
        ("hs", Decimal("80.000000")),
    ]


def test_repository_failure_rolls_back_partial_replacement(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_existing_snapshot(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        rows=[
            TefasFundAllocationRowCreate(
                asset_id=asset.id,
                data_date=date(2026, 8, 11),
                raw_field_name="hs",
                allocation_percentage=Decimal("80"),
            ),
        ],
    )

    raw_row = _build_raw_row("replace-fails")
    snapshot = _build_snapshot(
        allocations=(
            _build_item("hs", "100", label="Hisse Senedi", mapping_status="VERIFIED"),
        )
    )
    service = TefasSyncService(
        db_session,
        tefas_service=FakePortfolioBreakdownTefasService([raw_row], {id(raw_row): snapshot}),
    )

    original_replace = TefasFundAllocationDataRepository.replace_for_asset_and_date

    def delete_then_fail(
        self: TefasFundAllocationDataRepository,
        *,
        asset_id: int,
        data_date: date,
        rows: list[TefasFundAllocationRowCreate],
    ) -> list[TefasFundAllocationData]:
        self.delete_by_asset_and_date(asset_id=asset_id, data_date=data_date)
        raise RuntimeError("allocation replace failed")

    TefasFundAllocationDataRepository.replace_for_asset_and_date = delete_then_fail
    try:
        with pytest.raises(RuntimeError, match="allocation replace failed"):
            service.sync_portfolio_breakdown(
                start_date=date(2026, 8, 11),
                end_date=date(2026, 8, 11),
            )
    finally:
        TefasFundAllocationDataRepository.replace_for_asset_and_date = original_replace

    rows = _load_allocations(db_session)

    assert [(row.raw_field_name, row.allocation_percentage) for row in rows] == [
        ("hs", Decimal("80.000000")),
    ]


def test_duplicate_same_fund_and_date_raises_and_rolls_back(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_existing_snapshot(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        rows=[
            TefasFundAllocationRowCreate(
                asset_id=asset.id,
                data_date=date(2026, 8, 11),
                raw_field_name="hs",
                allocation_percentage=Decimal("80"),
            ),
        ],
    )

    raw_row_1 = _build_raw_row("duplicate-1")
    raw_row_2 = _build_raw_row("duplicate-2")
    snapshot_1 = _build_snapshot(
        allocations=(
            _build_item("hs", "100", label="Hisse Senedi", mapping_status="VERIFIED"),
        )
    )
    snapshot_2 = _build_snapshot(
        allocations=(
            _build_item("vmtl", "0", label="Mevduat (TL)", mapping_status="VERIFIED"),
        )
    )
    service = TefasSyncService(
        db_session,
        tefas_service=FakePortfolioBreakdownTefasService(
            [raw_row_1, raw_row_2],
            {
                id(raw_row_1): snapshot_1,
                id(raw_row_2): snapshot_2,
            },
        ),
    )

    with pytest.raises(ValueError, match="Duplicate TEFAS portfolio breakdown snapshot"):
        service.sync_portfolio_breakdown(
            start_date=date(2026, 8, 11),
            end_date=date(2026, 8, 11),
        )

    rows = _load_allocations(db_session)

    assert [(row.raw_field_name, row.allocation_percentage) for row in rows] == [
        ("hs", Decimal("80.000000")),
    ]


def test_no_data_result_creates_no_rows_and_does_not_commit(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TefasSyncService(
        db_session,
        tefas_service=EmptyPortfolioBreakdownTefasService(),
    )

    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    result = service.sync_portfolio_breakdown(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
    )

    assert result == TefasPortfolioAllocationSyncResult(
        fetched_fund_count=0,
        synced_fund_count=0,
        persisted_allocation_count=0,
    )
    assert commit_calls == 0
    assert db_session.scalar(select(func.count()).select_from(TefasFundAllocationData)) == 0
