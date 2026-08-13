from __future__ import annotations

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest

from src.services.tefas_fund_type_history_service import TefasFundTypeHistoryService
from src.services.tefas_fund_type_refresh_service import (
    TefasFundTypeRefreshFailure,
    TefasFundTypeRefreshResult,
    TefasFundTypeRefreshService,
)


class FakeAssetRepository:
    def __init__(self, asset_codes: list[str], error: Exception | None = None) -> None:
        self.asset_codes = asset_codes
        self.error = error
        self.calls: list[str] = []

    def list_active_by_data_source(self, data_source: str) -> list[SimpleNamespace]:
        self.calls.append(data_source)
        if self.error is not None:
            raise self.error
        return [SimpleNamespace(asset_code=asset_code) for asset_code in self.asset_codes]


class FakeFundTypeHistoryService:
    def __init__(self, outcomes: dict[str, str | Exception]) -> None:
        self.outcomes = outcomes
        self.calls: list[str] = []

    def observe_fund_type(self, *, fund_code: str) -> SimpleNamespace:
        self.calls.append(fund_code)
        outcome = self.outcomes[fund_code]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(action=outcome)


def _service(
    *,
    asset_codes: list[str],
    outcomes: dict[str, str | Exception] | None = None,
    listing_error: Exception | None = None,
) -> tuple[TefasFundTypeRefreshService, FakeAssetRepository, FakeFundTypeHistoryService]:
    asset_repository = FakeAssetRepository(asset_codes, error=listing_error)
    fund_type_history_service = FakeFundTypeHistoryService(outcomes or {})
    service = TefasFundTypeRefreshService(
        asset_repository=asset_repository,
        fund_type_history_service=fund_type_history_service,
    )
    return service, asset_repository, fund_type_history_service


def _assert_count_invariants(result: TefasFundTypeRefreshResult) -> None:
    assert result.attempted_count == result.succeeded_count + result.failed_count
    assert result.succeeded_count == (
        result.created_count + result.unchanged_count + result.changed_count
    )


def test_zero_active_assets_returns_zero_result() -> None:
    service, asset_repository, history_service = _service(asset_codes=[])

    result = service.refresh_active_tefas_funds()

    assert result == TefasFundTypeRefreshResult(
        attempted_count=0,
        succeeded_count=0,
        failed_count=0,
        created_count=0,
        unchanged_count=0,
        changed_count=0,
        failures=(),
    )
    assert asset_repository.calls == ["TEFAS"]
    assert history_service.calls == []
    _assert_count_invariants(result)


def test_multiple_successful_assets_are_attempted_once_in_repository_order() -> None:
    service, _, history_service = _service(
        asset_codes=["AAL", "AB1", "BLH"],
        outcomes={
            "AAL": TefasFundTypeHistoryService.ACTION_CREATED,
            "AB1": TefasFundTypeHistoryService.ACTION_UNCHANGED,
            "BLH": TefasFundTypeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.refresh_active_tefas_funds()

    assert history_service.calls == ["AAL", "AB1", "BLH"]
    assert result.attempted_count == 3
    assert result.succeeded_count == 3
    assert result.failed_count == 0
    assert result.created_count == 1
    assert result.unchanged_count == 1
    assert result.changed_count == 1
    assert result.failures == ()
    _assert_count_invariants(result)


def test_one_per_fund_failure_does_not_stop_later_assets() -> None:
    service, _, history_service = _service(
        asset_codes=["AAL", "BLH", "AB1"],
        outcomes={
            "AAL": TefasFundTypeHistoryService.ACTION_CREATED,
            "BLH": RuntimeError("source failed"),
            "AB1": TefasFundTypeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.refresh_active_tefas_funds()

    assert history_service.calls == ["AAL", "BLH", "AB1"]
    assert result.attempted_count == 3
    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.created_count == 1
    assert result.unchanged_count == 0
    assert result.changed_count == 1
    assert result.failures == (
        TefasFundTypeRefreshFailure(
            fund_code="BLH",
            error_type="RuntimeError",
            message="source failed",
        ),
    )
    _assert_count_invariants(result)


def test_failure_records_exact_fund_code_error_type_and_message() -> None:
    service, _, _ = _service(
        asset_codes=["AAL"],
        outcomes={"AAL": ValueError("bad profile response")},
    )

    result = service.refresh_active_tefas_funds()

    assert result.failures[0].fund_code == "AAL"
    assert result.failures[0].error_type == "ValueError"
    assert result.failures[0].message == "bad profile response"
    _assert_count_invariants(result)


def test_listing_failure_propagates_without_normal_result() -> None:
    service, _, history_service = _service(
        asset_codes=[],
        listing_error=RuntimeError("listing failed"),
    )

    with pytest.raises(RuntimeError, match="listing failed"):
        service.refresh_active_tefas_funds()

    assert history_service.calls == []


def test_unexpected_action_fails_clearly() -> None:
    service, _, _ = _service(
        asset_codes=["AAL"],
        outcomes={"AAL": "RENAMED"},
    )

    with pytest.raises(ValueError, match="Unexpected TEFAS fund-type refresh action: RENAMED"):
        service.refresh_active_tefas_funds()


def test_result_and_failure_structures_are_immutable() -> None:
    failure = TefasFundTypeRefreshFailure(
        fund_code="AAL",
        error_type="RuntimeError",
        message="source failed",
    )
    result = TefasFundTypeRefreshResult(
        attempted_count=1,
        succeeded_count=0,
        failed_count=1,
        created_count=0,
        unchanged_count=0,
        changed_count=0,
        failures=(failure,),
    )

    with pytest.raises(FrozenInstanceError):
        failure.message = "changed"
    with pytest.raises(FrozenInstanceError):
        result.failed_count = 0


def test_service_does_not_import_scheduler_or_tefas_client() -> None:
    import src.services.tefas_fund_type_refresh_service as refresh_module

    imported_names = set(refresh_module.__dict__)

    assert "sync_tefas_daily" not in imported_names
    assert "sync_tefas_scheduled" not in imported_names
    assert "TefasService" not in imported_names
