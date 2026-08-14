from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.services.tefas_fund_type_backfill_service import (
    TefasFundTypeBackfillFailure,
    TefasFundTypeBackfillResult,
    TefasFundTypeBackfillService,
)
from src.services.tefas_fund_type_history_service import TefasFundTypeHistoryService


class FakeAssetRepository:
    def __init__(self, asset_codes: list[str]) -> None:
        self.asset_codes = asset_codes
        self.calls: list[dict[str, object]] = []

    def list_active_tefas_without_current_fund_type(
        self,
        *,
        fund_kind: str,
        limit: int,
    ) -> list[SimpleNamespace]:
        self.calls.append({"fund_kind": fund_kind, "limit": limit})
        return [SimpleNamespace(asset_code=asset_code) for asset_code in self.asset_codes[:limit]]


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
) -> tuple[
    TefasFundTypeBackfillService,
    FakeAssetRepository,
    FakeFundTypeHistoryService,
    list[float],
]:
    asset_repository = FakeAssetRepository(asset_codes)
    history_service = FakeFundTypeHistoryService(outcomes or {})
    sleep_calls: list[float] = []
    service = TefasFundTypeBackfillService(
        asset_repository=asset_repository,
        fund_type_history_service=history_service,
        sleep_func=sleep_calls.append,
    )
    return service, asset_repository, history_service, sleep_calls


def test_backfill_queries_missing_active_tefas_assets_by_kind_and_limit() -> None:
    service, asset_repository, history_service, sleep_calls = _service(
        asset_codes=["AAL", "AB1"],
        outcomes={
            "AAL": TefasFundTypeHistoryService.ACTION_CREATED,
            "AB1": TefasFundTypeHistoryService.ACTION_CREATED,
        },
    )

    result = service.backfill_missing_active_tefas_funds(
        fund_kind=" yat ",
        limit=2,
        delay_seconds=0,
    )

    assert asset_repository.calls == [{"fund_kind": "YAT", "limit": 2}]
    assert history_service.calls == ["AAL", "AB1"]
    assert sleep_calls == []
    assert result == TefasFundTypeBackfillResult(
        fund_kind="YAT",
        limit=2,
        attempted_count=2,
        succeeded_count=2,
        failed_count=0,
        created_count=2,
        unchanged_count=0,
        changed_count=0,
        failures=(),
    )


def test_backfill_continues_after_individual_failure_and_reports_counts() -> None:
    service, _, history_service, _ = _service(
        asset_codes=["AAL", "BLH", "AB1"],
        outcomes={
            "AAL": TefasFundTypeHistoryService.ACTION_CREATED,
            "BLH": RuntimeError("profile failed"),
            "AB1": TefasFundTypeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.backfill_missing_active_tefas_funds(
        fund_kind="YAT",
        limit=3,
        delay_seconds=0,
    )

    assert history_service.calls == ["AAL", "BLH", "AB1"]
    assert result.attempted_count == 3
    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.created_count == 1
    assert result.changed_count == 1
    assert result.failures == (
        TefasFundTypeBackfillFailure(
            fund_code="BLH",
            error_type="RuntimeError",
            message="profile failed",
        ),
    )


def test_delay_is_applied_between_funds_but_not_after_final_fund() -> None:
    service, _, _, sleep_calls = _service(
        asset_codes=["AAL", "AB1", "BLH"],
        outcomes={
            "AAL": TefasFundTypeHistoryService.ACTION_CREATED,
            "AB1": TefasFundTypeHistoryService.ACTION_CREATED,
            "BLH": TefasFundTypeHistoryService.ACTION_CREATED,
        },
    )

    service.backfill_missing_active_tefas_funds(
        fund_kind="YAT",
        limit=3,
        delay_seconds=1.25,
    )

    assert sleep_calls == [1.25, 1.25]


def test_no_sleep_when_no_assets_are_eligible() -> None:
    service, _, history_service, sleep_calls = _service(asset_codes=[])

    result = service.backfill_missing_active_tefas_funds(
        fund_kind="YAT",
        limit=10,
    )

    assert result.attempted_count == 0
    assert history_service.calls == []
    assert sleep_calls == []


@pytest.mark.parametrize(
    ("fund_kind", "limit", "delay_seconds", "message"),
    [
        ("ABC", 1, 0, "fund_kind"),
        ("YAT", 0, 0, "limit"),
        ("YAT", 1, -0.1, "delay_seconds"),
    ],
)
def test_backfill_validates_inputs_before_listing_assets(
    fund_kind: str,
    limit: int,
    delay_seconds: float,
    message: str,
) -> None:
    service, asset_repository, history_service, sleep_calls = _service(asset_codes=["AAL"])

    with pytest.raises(ValueError, match=message):
        service.backfill_missing_active_tefas_funds(
            fund_kind=fund_kind,
            limit=limit,
            delay_seconds=delay_seconds,
        )

    assert asset_repository.calls == []
    assert history_service.calls == []
    assert sleep_calls == []
