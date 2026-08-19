from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot
from src.repositories.tefas_fund_detail_snapshot_repository import (
    TefasFundDetailSnapshotRepository,
)
from src.services.tefas_fund_detail_snapshot_observation_service import (
    TefasFundDetailSnapshotObservationService,
    TefasFundDetailSnapshotObservationServiceError,
)
from src.services.tefas_service import TefasFundDetailPageMetadataResult


OBSERVED_AT = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
LATER_OBSERVED_AT = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)


class FakeTefasService:
    def __init__(self, *results: TefasFundDetailPageMetadataResult | Exception) -> None:
        self.results = list(results)
        self.calls: list[str] = []

    def get_fund_detail_page_metadata(
        self,
        *,
        fund_code: str,
    ) -> TefasFundDetailPageMetadataResult:
        self.calls.append(fund_code)
        if not self.results:
            raise AssertionError("Unexpected TEFAS metadata fetch")

        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FailingDetailSnapshotRepository(TefasFundDetailSnapshotRepository):
    def add(self, snapshot: TefasFundDetailSnapshot) -> TefasFundDetailSnapshot:
        self.db.add(snapshot)
        raise RuntimeError("snapshot add failed")


def _build_asset(**overrides: object) -> Asset:
    values = {
        "asset_code": "AAL",
        "asset_name": "Example Fund",
        "asset_type": "FUND",
        "fund_kind": "YAT",
        "data_source": "TEFAS",
        "is_active": True,
    }
    values.update(overrides)
    return Asset(**values)


def _add_asset(db_session: Session, **overrides: object) -> Asset:
    asset = _build_asset(**overrides)
    db_session.add(asset)
    db_session.commit()
    return asset


def _metadata(**overrides: object) -> TefasFundDetailPageMetadataResult:
    values = {
        "fund_code": "AAL",
        "fund_category": "Serbest Fon",
        "category_rank": 1,
        "category_fund_count": 42,
        "market_share_raw": Decimal("1.2345678901"),
        "risk_value": 3,
        "source_page": "fon-detayli-analiz",
    }
    values.update(overrides)
    return TefasFundDetailPageMetadataResult(**values)


def _list_snapshots(db_session: Session) -> list[TefasFundDetailSnapshot]:
    return list(
        db_session.scalars(
            select(TefasFundDetailSnapshot).order_by(
                TefasFundDetailSnapshot.observed_at.asc(),
                TefasFundDetailSnapshot.id.asc(),
            )
        )
    )


def test_observe_fund_detail_snapshot_creates_snapshot_for_active_tefas_asset(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session)
    tefas_service = FakeTefasService(_metadata())
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=tefas_service,
    )

    snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    assert snapshot.id is not None
    assert snapshot.asset_id == asset.id
    assert snapshot.fund_category == "Serbest Fon"
    assert snapshot.category_rank == 1
    assert snapshot.category_fund_count == 42
    assert snapshot.market_share_raw == Decimal("1.2345678901")
    assert snapshot.risk_value == 3
    assert snapshot.source_page == "fon-detayli-analiz"
    assert snapshot.observed_at == OBSERVED_AT
    assert tefas_service.calls == ["AAL"]


def test_observe_fund_detail_snapshot_enriches_null_asset_isin_for_new_snapshot(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata(isin="TRMAALWWWWW5")),
    )

    snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    db_session.refresh(asset)
    assert snapshot.id is not None
    assert asset.isin == "TRMAALWWWWW5"


def test_observe_fund_detail_snapshot_leaves_asset_isin_unchanged_when_metadata_isin_missing(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session, isin="EXISTINGISIN")
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata(isin=None)),
    )

    service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    db_session.refresh(asset)
    assert asset.isin == "EXISTINGISIN"


def test_observe_fund_detail_snapshot_accepts_matching_existing_asset_isin(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session, isin="TRMAALWWWWW5")
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata(isin="TRMAALWWWWW5")),
    )

    snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    db_session.refresh(asset)
    assert snapshot.id is not None
    assert asset.isin == "TRMAALWWWWW5"


def test_observe_fund_detail_snapshot_rejects_conflicting_asset_isin_and_preserves_old_value(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session, isin="OLDISIN")
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata(isin="TRMAALWWWWW5")),
    )

    with pytest.raises(
        TefasFundDetailSnapshotObservationServiceError,
        match="Conflicting TEFAS asset ISIN metadata",
    ):
        service.observe_fund_detail_snapshot(
            fund_code="AAL",
            observed_at=OBSERVED_AT,
        )

    db_session.refresh(asset)
    assert asset.isin == "OLDISIN"
    assert _list_snapshots(db_session) == []


def test_observe_fund_detail_snapshot_normalizes_fund_code(
    db_session: Session,
) -> None:
    _add_asset(db_session, asset_code="AAL")
    tefas_service = FakeTefasService(_metadata())
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=tefas_service,
    )

    snapshot = service.observe_fund_detail_snapshot(
        fund_code=" aal ",
        observed_at=OBSERVED_AT,
    )

    assert snapshot.id is not None
    assert tefas_service.calls == ["AAL"]


def test_observe_fund_detail_snapshot_preserves_rank_zero(
    db_session: Session,
) -> None:
    _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata(category_rank=0)),
    )

    snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    assert snapshot.category_rank == 0


def test_observe_fund_detail_snapshot_preserves_nullable_source_fields(
    db_session: Session,
) -> None:
    _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(
            _metadata(
                category_rank=None,
                category_fund_count=None,
                market_share_raw=None,
                risk_value=None,
            )
        ),
    )

    snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    assert snapshot.category_rank is None
    assert snapshot.category_fund_count is None
    assert snapshot.market_share_raw is None
    assert snapshot.risk_value is None


def test_observe_fund_detail_snapshot_preserves_decimal_exactly(
    db_session: Session,
) -> None:
    _add_asset(db_session)
    market_share_raw = Decimal("0.1234567891")
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata(market_share_raw=market_share_raw)),
    )

    snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    assert snapshot.market_share_raw == market_share_raw


def test_observe_fund_detail_snapshot_is_idempotent_for_identical_same_timestamp_metadata(
    db_session: Session,
) -> None:
    _add_asset(db_session)
    tefas_service = FakeTefasService(_metadata(), _metadata())
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=tefas_service,
    )

    first_snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )
    second_snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    snapshots = _list_snapshots(db_session)
    assert second_snapshot.id == first_snapshot.id
    assert [snapshot.id for snapshot in snapshots] == [first_snapshot.id]
    assert tefas_service.calls == ["AAL", "AAL"]


def test_observe_fund_detail_snapshot_enriches_isin_for_existing_identical_snapshot_without_duplicate(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(
            _metadata(isin=None),
            _metadata(isin="TRMAALWWWWW5"),
        ),
    )
    first_snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    second_snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    db_session.refresh(asset)
    snapshots = _list_snapshots(db_session)
    assert second_snapshot.id == first_snapshot.id
    assert [snapshot.id for snapshot in snapshots] == [first_snapshot.id]
    assert asset.isin == "TRMAALWWWWW5"


def test_observe_fund_detail_snapshot_rejects_conflicting_same_timestamp_metadata(
    db_session: Session,
) -> None:
    _add_asset(db_session)
    tefas_service = FakeTefasService(
        _metadata(),
        _metadata(risk_value=4),
    )
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=tefas_service,
    )
    first_snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    with pytest.raises(
        TefasFundDetailSnapshotObservationServiceError,
        match="Conflicting TEFAS fund detail snapshot observation",
    ):
        service.observe_fund_detail_snapshot(
            fund_code="AAL",
            observed_at=OBSERVED_AT,
        )

    snapshots = _list_snapshots(db_session)
    assert [snapshot.id for snapshot in snapshots] == [first_snapshot.id]


def test_observe_fund_detail_snapshot_creates_separate_rows_for_different_timestamps(
    db_session: Session,
) -> None:
    _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata(), _metadata()),
    )

    first_snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )
    second_snapshot = service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=LATER_OBSERVED_AT,
    )

    assert second_snapshot.id != first_snapshot.id
    assert len(_list_snapshots(db_session)) == 2


@pytest.mark.parametrize(
    "asset_overrides",
    [
        {"asset_code": "AAL", "data_source": "MANUAL", "is_active": True},
        {"asset_code": "AAL", "data_source": "TEFAS", "is_active": False},
    ],
)
def test_observe_fund_detail_snapshot_rejects_missing_or_ineligible_tefas_asset(
    db_session: Session,
    asset_overrides: dict[str, object],
) -> None:
    _add_asset(db_session, **asset_overrides)
    tefas_service = FakeTefasService(_metadata())
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=tefas_service,
    )

    with pytest.raises(
        TefasFundDetailSnapshotObservationServiceError,
        match="Active TEFAS asset not found",
    ):
        service.observe_fund_detail_snapshot(
            fund_code="AAL",
            observed_at=OBSERVED_AT,
        )

    assert tefas_service.calls == []
    assert _list_snapshots(db_session) == []


def test_observe_fund_detail_snapshot_rejects_timezone_naive_observed_at(
    db_session: Session,
) -> None:
    _add_asset(db_session)
    tefas_service = FakeTefasService(_metadata())
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=tefas_service,
    )

    with pytest.raises(
        TefasFundDetailSnapshotObservationServiceError,
        match="observed_at must be timezone-aware",
    ):
        service.observe_fund_detail_snapshot(
            fund_code="AAL",
            observed_at=datetime(2026, 8, 14, 9, 0),
        )

    assert tefas_service.calls == []


def test_observe_fund_detail_snapshot_rolls_back_when_tefas_metadata_fetch_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(RuntimeError("metadata fetch failed")),
    )
    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(RuntimeError, match="metadata fetch failed"):
        service.observe_fund_detail_snapshot(
            fund_code="AAL",
            observed_at=OBSERVED_AT,
        )

    assert rollback_calls == 1
    assert _list_snapshots(db_session) == []


def test_observe_fund_detail_snapshot_rolls_back_when_repository_add_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        detail_snapshot_repository=FailingDetailSnapshotRepository(db_session),
        tefas_service=FakeTefasService(_metadata()),
    )
    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(RuntimeError, match="snapshot add failed"):
        service.observe_fund_detail_snapshot(
            fund_code="AAL",
            observed_at=OBSERVED_AT,
        )

    assert rollback_calls == 1
    assert _list_snapshots(db_session) == []


def test_observe_fund_detail_snapshot_rolls_back_asset_isin_when_repository_add_fails(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        detail_snapshot_repository=FailingDetailSnapshotRepository(db_session),
        tefas_service=FakeTefasService(_metadata(isin="TRMAALWWWWW5")),
    )

    with pytest.raises(RuntimeError, match="snapshot add failed"):
        service.observe_fund_detail_snapshot(
            fund_code="AAL",
            observed_at=OBSERVED_AT,
        )

    db_session.expire_all()
    persisted_asset = db_session.get(Asset, asset.id)
    assert persisted_asset is not None
    assert persisted_asset.isin is None
    assert _list_snapshots(db_session) == []


def test_observe_fund_detail_snapshot_commits_new_observation(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _add_asset(db_session)
    service = TefasFundDetailSnapshotObservationService(
        db_session,
        tefas_service=FakeTefasService(_metadata()),
    )
    commit_calls = 0
    original_commit = db_session.commit

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        original_commit()

    monkeypatch.setattr(db_session, "commit", counting_commit)

    service.observe_fund_detail_snapshot(
        fund_code="AAL",
        observed_at=OBSERVED_AT,
    )

    assert commit_calls == 1