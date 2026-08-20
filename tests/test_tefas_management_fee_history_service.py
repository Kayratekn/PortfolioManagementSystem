from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import inspect
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_management_fee_history import TefasManagementFeeHistory
from src.repositories.tefas_management_fee_history_repository import (
    TefasManagementFeeHistoryRepository,
)
from src.services.tefas_management_fee_history_service import (
    TefasManagementFeeHistoryObservationResult,
    TefasManagementFeeHistoryService,
    TefasManagementFeeHistoryServiceError,
)
from src.services.tefas_service import TefasManagementFeeResult


FEE_A = Decimal("1")
FEE_B = Decimal("0.85")


class FailingAddHistoryRepository(TefasManagementFeeHistoryRepository):
    def add(
        self,
        history: TefasManagementFeeHistory,
    ) -> TefasManagementFeeHistory:
        raise RuntimeError("history add failed")


class NoCurrentFailingAddHistoryRepository(TefasManagementFeeHistoryRepository):
    def get_current_for_asset(self, *, asset_id: int) -> TefasManagementFeeHistory | None:
        return None

    def add(
        self,
        history: TefasManagementFeeHistory,
    ) -> TefasManagementFeeHistory:
        raise RuntimeError("history add failed")


def _observation(
    management_fee_percentage: Decimal = FEE_A,
    *,
    fund_code: str = "AAL",
    raw_field_name: str = "uygulananYu1Y",
    source_endpoint: str = "fonYonetimBazliBilgiGetir",
) -> TefasManagementFeeResult:
    return TefasManagementFeeResult(
        fund_code=fund_code,
        management_fee_percentage=management_fee_percentage,
        fund_kind="YAT",
        raw_field_name=raw_field_name,
        source_endpoint=source_endpoint,
    )


def _observed_at(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 8, day, hour, 0, tzinfo=timezone.utc)


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _history(
    *,
    asset_id: int,
    management_fee_percentage: Decimal = FEE_A,
    first_observed_at: datetime = _observed_at(1),
    last_observed_at: datetime = _observed_at(1),
    closed_at: datetime | None = None,
    source_endpoint: str = "fonYonetimBazliBilgiGetir",
    source_field_name: str = "uygulananYu1Y",
) -> TefasManagementFeeHistory:
    return TefasManagementFeeHistory(
        asset_id=asset_id,
        management_fee_percentage=management_fee_percentage,
        source_endpoint=source_endpoint,
        source_field_name=source_field_name,
        first_observed_at=first_observed_at,
        last_observed_at=last_observed_at,
        closed_at=closed_at,
    )


def _service(
    db_session: Session,
    *,
    history_repository: TefasManagementFeeHistoryRepository | None = None,
) -> TefasManagementFeeHistoryService:
    return TefasManagementFeeHistoryService(
        db_session,
        management_fee_history_repository=history_repository,
    )


def _history_rows(db_session: Session, asset_id: int) -> list[TefasManagementFeeHistory]:
    return list(
        db_session.scalars(
            select(TefasManagementFeeHistory)
            .where(TefasManagementFeeHistory.asset_id == asset_id)
            .order_by(
                TefasManagementFeeHistory.first_observed_at.asc(),
                TefasManagementFeeHistory.id.asc(),
            )
        )
    )


def _current_row(db_session: Session, asset_id: int) -> TefasManagementFeeHistory | None:
    return db_session.scalar(
        select(TefasManagementFeeHistory).where(
            TefasManagementFeeHistory.asset_id == asset_id,
            TefasManagementFeeHistory.closed_at.is_(None),
        )
    )


def _count_rows(db_session: Session) -> int:
    return len(list(db_session.scalars(select(TefasManagementFeeHistory))))


def test_first_observation_creates_one_open_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    observed_at = _observed_at(1)
    service = _service(db_session)

    result = service.observe_management_fee(
        observation=_observation(FEE_A),
        observed_at=observed_at,
    )

    rows = _history_rows(db_session, asset.id)
    assert isinstance(result, TefasManagementFeeHistoryObservationResult)
    assert result.action == TefasManagementFeeHistoryService.ACTION_CREATED
    assert len(rows) == 1
    assert rows[0].closed_at is None
    assert rows[0].management_fee_percentage == FEE_A


def test_first_observation_sets_first_and_last_to_observed_at(db_session: Session) -> None:
    asset = _create_asset(db_session)
    observed_at = _observed_at(1)
    service = _service(db_session)

    service.observe_management_fee(
        observation=_observation(FEE_A),
        observed_at=observed_at,
    )

    row = _history_rows(db_session, asset.id)[0]
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == observed_at
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == observed_at


def test_first_observation_preserves_source_metadata(db_session: Session) -> None:
    asset = _create_asset(db_session)
    service = _service(db_session)

    service.observe_management_fee(
        observation=_observation(
            FEE_A,
            source_endpoint="fonYonetimBazliBilgiGetir",
            raw_field_name="uygulananYu1Y",
        ),
        observed_at=_observed_at(1),
    )

    row = _history_rows(db_session, asset.id)[0]
    assert row.source_endpoint == "fonYonetimBazliBilgiGetir"
    assert row.source_field_name == "uygulananYu1Y"


def test_unchanged_observation_does_not_create_second_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(
        _history(
            asset_id=asset.id,
            management_fee_percentage=Decimal("1.000000"),
            first_observed_at=_observed_at(1),
            last_observed_at=_observed_at(1),
        )
    )
    db_session.commit()
    service = _service(db_session)

    result = service.observe_management_fee(
        observation=_observation(Decimal("1")),
        observed_at=_observed_at(8),
    )

    rows = _history_rows(db_session, asset.id)
    assert result.action == TefasManagementFeeHistoryService.ACTION_UNCHANGED
    assert len(rows) == 1


def test_unchanged_observation_updates_last_observed_at_only(db_session: Session) -> None:
    asset = _create_asset(db_session)
    first_seen = _observed_at(1)
    last_seen = _observed_at(1)
    db_session.add(
        _history(
            asset_id=asset.id,
            first_observed_at=first_seen,
            last_observed_at=last_seen,
        )
    )
    db_session.commit()
    service = _service(db_session)

    service.observe_management_fee(
        observation=_observation(FEE_A),
        observed_at=_observed_at(8),
    )

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == first_seen
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == _observed_at(8)
    assert row.closed_at is None


def test_changed_observation_closes_old_row_and_creates_new_open_row(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(
        _history(
            asset_id=asset.id,
            management_fee_percentage=FEE_A,
            first_observed_at=_observed_at(1),
            last_observed_at=_observed_at(8),
        )
    )
    db_session.commit()
    service = _service(db_session)

    result = service.observe_management_fee(
        observation=_observation(FEE_B),
        observed_at=_observed_at(15),
    )

    rows = _history_rows(db_session, asset.id)
    assert result.action == TefasManagementFeeHistoryService.ACTION_CHANGED
    assert len(rows) == 2
    assert rows[0].management_fee_percentage == FEE_A
    assert rows[0].closed_at is not None
    assert rows[0].closed_at.replace(tzinfo=timezone.utc) == _observed_at(15)
    assert rows[0].last_observed_at.replace(tzinfo=timezone.utc) == _observed_at(8)
    assert rows[1].management_fee_percentage == FEE_B
    assert rows[1].first_observed_at.replace(tzinfo=timezone.utc) == _observed_at(15)
    assert rows[1].last_observed_at.replace(tzinfo=timezone.utc) == _observed_at(15)
    assert rows[1].closed_at is None


def test_changed_observation_uses_new_source_fields(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(_history(asset_id=asset.id, last_observed_at=_observed_at(8)))
    db_session.commit()
    service = _service(db_session)

    service.observe_management_fee(
        observation=_observation(
            FEE_B,
            source_endpoint="fonYonetimBazliBilgiGetirV2",
            raw_field_name="uygulananYu1YV2",
        ),
        observed_at=_observed_at(15),
    )

    new_row = _history_rows(db_session, asset.id)[1]
    assert new_row.source_endpoint == "fonYonetimBazliBilgiGetirV2"
    assert new_row.source_field_name == "uygulananYu1YV2"


def test_a_to_b_to_a_creates_three_periods_without_reopening_old_a(db_session: Session) -> None:
    asset = _create_asset(db_session)
    service = _service(db_session)

    service.observe_management_fee(observation=_observation(FEE_A), observed_at=_observed_at(1))
    service.observe_management_fee(observation=_observation(FEE_B), observed_at=_observed_at(8))
    service.observe_management_fee(observation=_observation(FEE_A), observed_at=_observed_at(15))

    rows = _history_rows(db_session, asset.id)
    assert [row.management_fee_percentage for row in rows] == [FEE_A, FEE_B, FEE_A]
    assert rows[0].closed_at is not None
    assert rows[1].closed_at is not None
    assert rows[2].closed_at is None
    assert rows[0].id != rows[2].id


def test_asset_missing_does_not_write_history(db_session: Session, monkeypatch) -> None:
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    service = _service(db_session)

    with pytest.raises(TefasManagementFeeHistoryServiceError):
        service.observe_management_fee(
            observation=_observation(FEE_A),
            observed_at=_observed_at(1),
        )

    assert _count_rows(db_session) == 0
    assert commit_calls == 0


def test_changed_transition_flushes_closed_row_before_adding_new_open_row(
    db_session: Session,
    monkeypatch,
) -> None:
    asset = _create_asset(db_session)
    current = _history(asset_id=asset.id, last_observed_at=_observed_at(8))
    db_session.add(current)
    db_session.commit()
    original_flush = db_session.flush
    flush_closed_values: list[datetime | None] = []

    def tracking_flush(*args: Any, **kwargs: Any) -> None:
        flush_closed_values.append(current.closed_at)
        original_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", tracking_flush)
    service = _service(db_session)

    service.observe_management_fee(
        observation=_observation(FEE_B),
        observed_at=_observed_at(15),
    )

    assert flush_closed_values[0] is not None
    assert flush_closed_values[0].replace(tzinfo=timezone.utc) == _observed_at(15)
    assert len(flush_closed_values) >= 2


def test_changed_transition_add_failure_rolls_back(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    current = _history(asset_id=asset.id, last_observed_at=_observed_at(8))
    db_session.add(current)
    db_session.commit()
    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)
    service = _service(
        db_session,
        history_repository=FailingAddHistoryRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="history add failed"):
        service.observe_management_fee(
            observation=_observation(FEE_B),
            observed_at=_observed_at(15),
        )

    assert rollback_calls == 1


def test_changed_transition_rollback_leaves_previous_current_state_intact(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session)
    current = _history(asset_id=asset.id, last_observed_at=_observed_at(8))
    db_session.add(current)
    db_session.commit()
    service = _service(
        db_session,
        history_repository=FailingAddHistoryRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="history add failed"):
        service.observe_management_fee(
            observation=_observation(FEE_B),
            observed_at=_observed_at(15),
        )

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.id == current.id
    assert row.management_fee_percentage == FEE_A
    assert row.closed_at is None
    assert len(_history_rows(db_session, asset.id)) == 1


def test_first_observation_db_failure_rolls_back(db_session: Session, monkeypatch) -> None:
    _create_asset(db_session)
    db_session.commit()
    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)
    service = _service(
        db_session,
        history_repository=NoCurrentFailingAddHistoryRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="history add failed"):
        service.observe_management_fee(
            observation=_observation(FEE_A),
            observed_at=_observed_at(1),
        )

    assert rollback_calls == 1
    assert _count_rows(db_session) == 0


def test_unchanged_update_db_failure_rolls_back(db_session: Session, monkeypatch) -> None:
    asset = _create_asset(db_session)
    first_seen = _observed_at(1)
    last_seen = _observed_at(8)
    current = _history(
        asset_id=asset.id,
        first_observed_at=first_seen,
        last_observed_at=last_seen,
    )
    db_session.add(current)
    db_session.commit()
    rollback_calls = 0
    original_rollback = db_session.rollback

    def failing_flush(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("flush failed")

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "flush", failing_flush)
    monkeypatch.setattr(db_session, "rollback", counting_rollback)
    service = _service(db_session)

    with pytest.raises(RuntimeError, match="flush failed"):
        service.observe_management_fee(
            observation=_observation(FEE_A),
            observed_at=_observed_at(15),
        )

    assert rollback_calls == 1
    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == last_seen


def test_successful_operation_commits_once_at_service_boundary(
    db_session: Session,
    monkeypatch,
) -> None:
    _create_asset(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    service = _service(db_session)

    service.observe_management_fee(
        observation=_observation(FEE_A),
        observed_at=_observed_at(1),
    )

    assert commit_calls == 1


def test_repository_still_does_not_commit() -> None:
    source = inspect.getsource(TefasManagementFeeHistoryRepository)

    assert ".commit(" not in source


def test_default_observation_timestamp_is_timezone_aware(db_session: Session) -> None:
    _create_asset(db_session)
    service = _service(db_session)

    result = service.observe_management_fee(observation=_observation(FEE_A))

    assert result.observed_at.tzinfo is not None
    assert result.observed_at.utcoffset() is not None
    assert result.observed_at.tzinfo == timezone.utc


def test_non_utc_observed_at_is_normalized_to_utc(db_session: Session) -> None:
    asset = _create_asset(db_session)
    service = _service(db_session)
    observed_at = datetime(2026, 8, 1, 12, 0, tzinfo=timezone(timedelta(hours=3)))

    result = service.observe_management_fee(
        observation=_observation(FEE_A),
        observed_at=observed_at,
    )

    row = _history_rows(db_session, asset.id)[0]
    assert result.observed_at == _observed_at(1)
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == _observed_at(1)


def test_naive_observed_at_is_rejected_without_mutation(db_session: Session) -> None:
    _create_asset(db_session)
    service = _service(db_session)

    with pytest.raises(TefasManagementFeeHistoryServiceError, match="timezone-aware"):
        service.observe_management_fee(
            observation=_observation(FEE_A),
            observed_at=datetime(2026, 8, 1, 9, 0),
        )

    assert _count_rows(db_session) == 0


def test_out_of_order_before_last_observed_at_is_rejected_without_mutation(
    db_session: Session,
    monkeypatch,
) -> None:
    asset = _create_asset(db_session)
    first_seen = _observed_at(10)
    last_seen = _observed_at(12)
    current = _history(
        asset_id=asset.id,
        first_observed_at=first_seen,
        last_observed_at=last_seen,
    )
    db_session.add(current)
    db_session.commit()
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    service = _service(db_session)

    with pytest.raises(TefasManagementFeeHistoryServiceError, match="observed_at cannot"):
        service.observe_management_fee(
            observation=_observation(FEE_B),
            observed_at=_observed_at(11),
        )

    row = _current_row(db_session, asset.id)
    assert row is not None
    assert row.management_fee_percentage == FEE_A
    assert row.first_observed_at.replace(tzinfo=timezone.utc) == first_seen
    assert row.last_observed_at.replace(tzinfo=timezone.utc) == last_seen
    assert row.closed_at is None
    assert commit_calls == 0


def test_out_of_order_before_first_observed_at_is_rejected_without_mutation(
    db_session: Session,
) -> None:
    asset = _create_asset(db_session)
    db_session.add(
        _history(
            asset_id=asset.id,
            first_observed_at=_observed_at(10),
            last_observed_at=_observed_at(10),
        )
    )
    db_session.commit()
    service = _service(db_session)

    with pytest.raises(TefasManagementFeeHistoryServiceError, match="observed_at cannot"):
        service.observe_management_fee(
            observation=_observation(FEE_A),
            observed_at=_observed_at(9),
        )

    assert len(_history_rows(db_session, asset.id)) == 1


def test_fund_code_is_normalized_for_asset_lookup_and_result(db_session: Session) -> None:
    _create_asset(db_session, asset_code="AAL")
    service = _service(db_session)

    result = service.observe_management_fee(
        observation=_observation(FEE_A, fund_code=" aal "),
        observed_at=_observed_at(1),
    )

    assert result.fund_code == "AAL"


def test_service_does_not_call_tefas_fetch_management_fees() -> None:
    source = inspect.getsource(TefasManagementFeeHistoryService)

    assert "fetch_management_fees" not in source
    assert "TefasService(" not in source


@pytest.mark.parametrize(
    ("source_endpoint", "raw_field_name", "expected_message"),
    [
        ("", "uygulananYu1Y", "source_endpoint"),
        ("fonYonetimBazliBilgiGetir", "", "source_field_name"),
    ],
)
def test_invalid_source_metadata_is_rejected_without_mutation(
    db_session: Session,
    source_endpoint: str,
    raw_field_name: str,
    expected_message: str,
) -> None:
    _create_asset(db_session)
    service = _service(db_session)

    with pytest.raises(TefasManagementFeeHistoryServiceError, match=expected_message):
        service.observe_management_fee(
            observation=_observation(
                FEE_A,
                source_endpoint=source_endpoint,
                raw_field_name=raw_field_name,
            ),
            observed_at=_observed_at(1),
        )

    assert _count_rows(db_session) == 0
