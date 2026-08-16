from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from src.services.tefas_fund_detail_snapshot_bulk_refresh_service import (
    TefasFundDetailSnapshotBulkRefreshFailure,
    TefasFundDetailSnapshotBulkRefreshResult,
    TefasFundDetailSnapshotBulkRefreshService,
)


class FakeAssetRepository:
    def __init__(self, asset_codes: list[str]) -> None:
        self.asset_codes = asset_codes
        self.calls: list[int] = []

    def list_active_tefas_assets(self, *, limit: int) -> list[SimpleNamespace]:
        self.calls.append(limit)
        return [SimpleNamespace(asset_code=asset_code) for asset_code in self.asset_codes[:limit]]


class FakeObservationService:
    def __init__(self, failures: dict[str, Exception] | None = None) -> None:
        self.failures = failures or {}
        self.calls: list[str] = []

    def observe_fund_detail_snapshot(self, *, fund_code: str) -> SimpleNamespace:
        self.calls.append(fund_code)
        failure = self.failures.get(fund_code)
        if failure is not None:
            raise failure
        return SimpleNamespace(fund_code=fund_code)


def _service(
    *,
    asset_codes: list[str],
    failures: dict[str, Exception] | None = None,
) -> tuple[
    TefasFundDetailSnapshotBulkRefreshService,
    FakeAssetRepository,
    FakeObservationService,
    list[float],
]:
    asset_repository = FakeAssetRepository(asset_codes)
    observation_service = FakeObservationService(failures)
    sleep_calls: list[float] = []
    service = TefasFundDetailSnapshotBulkRefreshService(
        asset_repository=asset_repository,
        observation_service=observation_service,
        sleep_func=sleep_calls.append,
    )
    return service, asset_repository, observation_service, sleep_calls


def _assert_count_invariants(result: TefasFundDetailSnapshotBulkRefreshResult) -> None:
    assert result.attempted_count == result.succeeded_count + result.failed_count
    assert result.succeeded_count == len(result.successful_fund_codes)
    assert result.failed_count == len(result.failures)


def test_successful_multi_fund_run_attempts_each_selected_fund_once() -> None:
    service, asset_repository, observation_service, sleep_calls = _service(
        asset_codes=["AAL", "AB1", "BLH"],
    )

    result = service.refresh_active_tefas_fund_detail_snapshots(
        limit=3,
        delay_seconds=0,
    )

    assert asset_repository.calls == [3]
    assert observation_service.calls == ["AAL", "AB1", "BLH"]
    assert sleep_calls == []
    assert result == TefasFundDetailSnapshotBulkRefreshResult(
        limit=3,
        attempted_count=3,
        succeeded_count=3,
        failed_count=0,
        successful_fund_codes=("AAL", "AB1", "BLH"),
        failures=(),
    )
    _assert_count_invariants(result)


def test_deterministic_repository_order_is_preserved() -> None:
    service, _, observation_service, _ = _service(
        asset_codes=["AAL", "AB1", "BLH"],
    )

    service.refresh_active_tefas_fund_detail_snapshots(limit=3, delay_seconds=0)

    assert observation_service.calls == ["AAL", "AB1", "BLH"]


def test_limit_is_forwarded_and_respected() -> None:
    service, asset_repository, observation_service, _ = _service(
        asset_codes=["AAL", "AB1", "BLH"],
    )

    result = service.refresh_active_tefas_fund_detail_snapshots(
        limit=2,
        delay_seconds=0,
    )

    assert asset_repository.calls == [2]
    assert observation_service.calls == ["AAL", "AB1"]
    assert result.attempted_count == 2
    assert result.successful_fund_codes == ("AAL", "AB1")
    _assert_count_invariants(result)


@pytest.mark.parametrize(
    ("limit", "delay_seconds", "message"),
    [
        (0, 0, "limit"),
        (-1, 0, "limit"),
        (True, 0, "limit"),
        (False, 0, "limit"),
        (1.0, 0, "limit"),
        (5.0, 0, "limit"),
        ("5", 0, "limit"),
        (None, 0, "limit"),
        (1, -0.1, "delay_seconds"),
    ],
)
def test_validates_inputs_before_listing_assets(
    limit: object,
    delay_seconds: float,
    message: str,
) -> None:
    service, asset_repository, observation_service, sleep_calls = _service(
        asset_codes=["AAL"],
    )

    with pytest.raises(ValueError, match=message):
        service.refresh_active_tefas_fund_detail_snapshots(
            limit=limit,
            delay_seconds=delay_seconds,
        )

    assert asset_repository.calls == []
    assert observation_service.calls == []
    assert sleep_calls == []


def test_continue_on_error_records_failure_and_attempts_later_funds() -> None:
    service, _, observation_service, _ = _service(
        asset_codes=["AAL", "BLH", "AB1"],
        failures={"BLH": RuntimeError("detail page failed")},
    )

    result = service.refresh_active_tefas_fund_detail_snapshots(
        limit=3,
        delay_seconds=0,
    )

    assert observation_service.calls == ["AAL", "BLH", "AB1"]
    assert result.attempted_count == 3
    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.successful_fund_codes == ("AAL", "AB1")
    assert result.failures == (
        TefasFundDetailSnapshotBulkRefreshFailure(
            fund_code="BLH",
            error_type="RuntimeError",
            message="detail page failed",
        ),
    )
    _assert_count_invariants(result)


def test_failure_summary_contains_failed_fund_code() -> None:
    service, _, _, _ = _service(
        asset_codes=["AAL"],
        failures={"AAL": ValueError("bad metadata")},
    )

    result = service.refresh_active_tefas_fund_detail_snapshots(
        limit=1,
        delay_seconds=0,
    )

    assert result.failures[0].fund_code == "AAL"
    assert result.failures[0].error_type == "ValueError"
    assert result.failures[0].message == "bad metadata"
    _assert_count_invariants(result)


def test_sleep_occurs_only_between_attempted_funds() -> None:
    service, _, observation_service, sleep_calls = _service(
        asset_codes=["AAL", "AB1", "BLH"],
    )

    service.refresh_active_tefas_fund_detail_snapshots(
        limit=3,
        delay_seconds=1.25,
    )

    assert observation_service.calls == ["AAL", "AB1", "BLH"]
    assert sleep_calls == [1.25, 1.25]


def test_no_sleep_after_final_fund_or_when_delay_is_zero() -> None:
    service, _, _, sleep_calls = _service(asset_codes=["AAL"])

    service.refresh_active_tefas_fund_detail_snapshots(
        limit=1,
        delay_seconds=1.25,
    )

    assert sleep_calls == []

    service, _, _, sleep_calls = _service(asset_codes=["AAL", "AB1"])
    service.refresh_active_tefas_fund_detail_snapshots(
        limit=2,
        delay_seconds=0,
    )

    assert sleep_calls == []


def test_limit_larger_than_available_assets_uses_available_assets() -> None:
    service, asset_repository, observation_service, sleep_calls = _service(
        asset_codes=["AAL", "AB1"],
    )

    result = service.refresh_active_tefas_fund_detail_snapshots(
        limit=10,
        delay_seconds=0.5,
    )

    assert asset_repository.calls == [10]
    assert observation_service.calls == ["AAL", "AB1"]
    assert sleep_calls == [0.5]
    assert result.attempted_count == 2
    assert result.succeeded_count == 2
    assert result.failed_count == 0
    _assert_count_invariants(result)


def test_zero_eligible_assets_returns_valid_zero_count_result() -> None:
    service, asset_repository, observation_service, sleep_calls = _service(asset_codes=[])

    result = service.refresh_active_tefas_fund_detail_snapshots(limit=10)

    assert asset_repository.calls == [10]
    assert observation_service.calls == []
    assert sleep_calls == []
    assert result == TefasFundDetailSnapshotBulkRefreshResult(
        limit=10,
        attempted_count=0,
        succeeded_count=0,
        failed_count=0,
        successful_fund_codes=(),
        failures=(),
    )
    _assert_count_invariants(result)


def test_result_and_failure_structures_are_immutable() -> None:
    failure = TefasFundDetailSnapshotBulkRefreshFailure(
        fund_code="AAL",
        error_type="RuntimeError",
        message="detail page failed",
    )
    result = TefasFundDetailSnapshotBulkRefreshResult(
        limit=1,
        attempted_count=1,
        succeeded_count=0,
        failed_count=1,
        successful_fund_codes=(),
        failures=(failure,),
    )

    with pytest.raises(FrozenInstanceError):
        failure.message = "changed"
    with pytest.raises(FrozenInstanceError):
        result.failed_count = 0
