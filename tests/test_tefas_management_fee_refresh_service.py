from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.repositories.asset_repository import AssetRepository
from src.services.tefas_management_fee_history_service import (
    TefasManagementFeeHistoryService,
)
from src.services.tefas_management_fee_refresh_service import (
    TefasManagementFeeRefreshFailure,
    TefasManagementFeeRefreshResult,
    TefasManagementFeeRefreshService,
)
from src.services.tefas_service import TefasManagementFeeResult


class FakeAssetRepository:
    def __init__(self, assets_by_kind: dict[str, list[str]]) -> None:
        self.assets_by_kind = assets_by_kind
        self.calls: list[str] = []

    def list_active_tefas_by_fund_kind(self, *, fund_kind: str) -> list[SimpleNamespace]:
        self.calls.append(fund_kind)
        return [
            SimpleNamespace(asset_code=asset_code)
            for asset_code in self.assets_by_kind.get(fund_kind, [])
        ]


class FakeTefasService:
    def __init__(self, results_by_kind: dict[str, list[TefasManagementFeeResult]]) -> None:
        self.results_by_kind = results_by_kind
        self.calls: list[str] = []

    def fetch_management_fees(self, *, fund_kind: str) -> list[TefasManagementFeeResult]:
        self.calls.append(fund_kind)
        return self.results_by_kind.get(fund_kind, [])


class FakeManagementFeeHistoryService:
    def __init__(self, outcomes_by_fund_code: dict[str, str | Exception]) -> None:
        self.outcomes_by_fund_code = outcomes_by_fund_code
        self.calls: list[dict[str, object]] = []

    def observe_management_fee(
        self,
        *,
        observation: TefasManagementFeeResult,
        observed_at: datetime | None = None,
    ) -> SimpleNamespace:
        self.calls.append({"observation": observation, "observed_at": observed_at})
        outcome = self.outcomes_by_fund_code[observation.fund_code]
        if isinstance(outcome, Exception):
            raise outcome
        return SimpleNamespace(action=outcome)


def _fee_result(
    fund_code: str,
    *,
    fund_kind: str = "YAT",
    fee: Decimal = Decimal("1"),
) -> TefasManagementFeeResult:
    return TefasManagementFeeResult(
        fund_code=fund_code,
        management_fee_percentage=fee,
        fund_kind=fund_kind,
        raw_field_name="uygulananYu1Y",
        source_endpoint="fonYonetimBazliBilgiGetir",
    )


def _service(
    *,
    assets_by_kind: dict[str, list[str]],
    results_by_kind: dict[str, list[TefasManagementFeeResult]],
    outcomes_by_fund_code: dict[str, str | Exception] | None = None,
) -> tuple[
    TefasManagementFeeRefreshService,
    FakeAssetRepository,
    FakeTefasService,
    FakeManagementFeeHistoryService,
]:
    asset_repository = FakeAssetRepository(assets_by_kind)
    tefas_service = FakeTefasService(results_by_kind)
    history_service = FakeManagementFeeHistoryService(outcomes_by_fund_code or {})
    service = TefasManagementFeeRefreshService(
        asset_repository=asset_repository,  # type: ignore[arg-type]
        management_fee_history_service=history_service,  # type: ignore[arg-type]
        tefas_service=tefas_service,  # type: ignore[arg-type]
    )
    return service, asset_repository, tefas_service, history_service


def _assert_count_invariants(result: TefasManagementFeeRefreshResult) -> None:
    assert result.attempted_count == result.succeeded_count + result.failed_count
    assert result.succeeded_count == (
        result.created_count + result.unchanged_count + result.changed_count
    )


def _add_asset(
    db_session: Session,
    *,
    asset_code: str,
    fund_kind: str = "YAT",
    data_source: str = "TEFAS",
    is_active: bool = True,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Fund",
        asset_type="FUND",
        fund_kind=fund_kind,
        currency=None,
        data_source=data_source,
        is_active=is_active,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def test_asset_repository_lists_active_tefas_by_fund_kind_in_code_order(
    db_session: Session,
) -> None:
    _add_asset(db_session, asset_code="BLH", fund_kind="YAT")
    _add_asset(db_session, asset_code="AAL", fund_kind="YAT")
    _add_asset(db_session, asset_code="EMK1", fund_kind="EMK")
    _add_asset(db_session, asset_code="OLD", fund_kind="YAT", is_active=False)
    _add_asset(db_session, asset_code="EXT", fund_kind="YAT", data_source="OTHER")

    result = AssetRepository(db_session).list_active_tefas_by_fund_kind(
        fund_kind="YAT",
    )

    assert [asset.asset_code for asset in result] == ["AAL", "BLH"]


def test_refresh_yat_makes_exactly_one_bulk_tefas_fetch() -> None:
    service, asset_repository, tefas_service, history_service = _service(
        assets_by_kind={"YAT": ["AAL", "BLH"]},
        results_by_kind={"YAT": [_fee_result("AAL"), _fee_result("BLH")]},
        outcomes_by_fund_code={
            "AAL": TefasManagementFeeHistoryService.ACTION_CREATED,
            "BLH": TefasManagementFeeHistoryService.ACTION_UNCHANGED,
        },
    )

    result = service.refresh_fund_kind(fund_kind="YAT")

    assert asset_repository.calls == ["YAT"]
    assert tefas_service.calls == ["YAT"]
    assert [call["observation"].fund_code for call in history_service.calls] == [
        "AAL",
        "BLH",
    ]
    assert result.attempted_count == 2
    _assert_count_invariants(result)


def test_refresh_emk_makes_exactly_one_bulk_tefas_fetch() -> None:
    service, asset_repository, tefas_service, history_service = _service(
        assets_by_kind={"EMK": ["EMK1", "EMK2"]},
        results_by_kind={
            "EMK": [
                _fee_result("EMK1", fund_kind="EMK"),
                _fee_result("EMK2", fund_kind="EMK"),
            ]
        },
        outcomes_by_fund_code={
            "EMK1": TefasManagementFeeHistoryService.ACTION_CREATED,
            "EMK2": TefasManagementFeeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.refresh_fund_kind(fund_kind="EMK")

    assert asset_repository.calls == ["EMK"]
    assert tefas_service.calls == ["EMK"]
    assert [call["observation"].fund_code for call in history_service.calls] == [
        "EMK1",
        "EMK2",
    ]
    assert result.attempted_count == 2
    _assert_count_invariants(result)


def test_yat_and_emk_refresh_make_exactly_two_bulk_fetches_total() -> None:
    service, asset_repository, tefas_service, history_service = _service(
        assets_by_kind={"YAT": ["AAL"], "EMK": ["EMK1"]},
        results_by_kind={
            "YAT": [_fee_result("AAL")],
            "EMK": [_fee_result("EMK1", fund_kind="EMK")],
        },
        outcomes_by_fund_code={
            "AAL": TefasManagementFeeHistoryService.ACTION_CREATED,
            "EMK1": TefasManagementFeeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.refresh_fund_kinds(fund_kinds=("YAT", "EMK"))

    assert asset_repository.calls == ["YAT", "EMK"]
    assert tefas_service.calls == ["YAT", "EMK"]
    assert len(history_service.calls) == 2
    assert result.attempted_count == 2
    assert result.succeeded_count == 2
    _assert_count_invariants(result)


def test_no_per_fund_tefas_network_pattern_is_used() -> None:
    service, _, tefas_service, history_service = _service(
        assets_by_kind={"YAT": ["AAL", "AB1", "BLH"]},
        results_by_kind={
            "YAT": [_fee_result("AAL"), _fee_result("AB1"), _fee_result("BLH")]
        },
        outcomes_by_fund_code={
            "AAL": TefasManagementFeeHistoryService.ACTION_CREATED,
            "AB1": TefasManagementFeeHistoryService.ACTION_UNCHANGED,
            "BLH": TefasManagementFeeHistoryService.ACTION_CHANGED,
        },
    )

    service.refresh_fund_kind(fund_kind="YAT")

    assert tefas_service.calls == ["YAT"]
    assert len(history_service.calls) == 3


def test_only_active_assets_of_matching_kind_are_attempted() -> None:
    service, asset_repository, tefas_service, history_service = _service(
        assets_by_kind={"YAT": ["AAL"], "EMK": ["EMK1"]},
        results_by_kind={
            "YAT": [_fee_result("AAL")],
            "EMK": [_fee_result("EMK1", fund_kind="EMK")],
        },
        outcomes_by_fund_code={
            "AAL": TefasManagementFeeHistoryService.ACTION_CREATED,
            "EMK1": TefasManagementFeeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.refresh_fund_kind(fund_kind="YAT")

    assert asset_repository.calls == ["YAT"]
    assert tefas_service.calls == ["YAT"]
    assert [call["observation"].fund_code for call in history_service.calls] == ["AAL"]
    assert result.attempted_count == 1


def test_extra_tefas_rows_absent_from_active_db_assets_are_ignored() -> None:
    service, _, _, history_service = _service(
        assets_by_kind={"YAT": ["AAL"]},
        results_by_kind={"YAT": [_fee_result("AAL"), _fee_result("OLD")]},
        outcomes_by_fund_code={
            "AAL": TefasManagementFeeHistoryService.ACTION_CREATED,
            "OLD": RuntimeError("must not be used"),
        },
    )

    result = service.refresh_fund_kind(fund_kind="YAT")

    assert [call["observation"].fund_code for call in history_service.calls] == ["AAL"]
    assert result.failed_count == 0
    assert result.succeeded_count == 1


def test_active_db_asset_missing_from_tefas_response_becomes_failure() -> None:
    service, _, _, history_service = _service(
        assets_by_kind={"YAT": ["AAL", "BLH"]},
        results_by_kind={"YAT": [_fee_result("AAL")]},
        outcomes_by_fund_code={"AAL": TefasManagementFeeHistoryService.ACTION_CREATED},
    )

    result = service.refresh_fund_kind(fund_kind="YAT")

    assert [call["observation"].fund_code for call in history_service.calls] == ["AAL"]
    assert result.attempted_count == 2
    assert result.succeeded_count == 1
    assert result.failed_count == 1
    assert result.failures == (
        TefasManagementFeeRefreshFailure(
            fund_code="BLH",
            fund_kind="YAT",
            error_type="LookupError",
            message="TEFAS management-fee row not found for active asset.",
        ),
    )
    _assert_count_invariants(result)


def test_created_unchanged_changed_counters_are_correct() -> None:
    service, _, _, _ = _service(
        assets_by_kind={"YAT": ["AAL", "AB1", "BLH"]},
        results_by_kind={
            "YAT": [_fee_result("AAL"), _fee_result("AB1"), _fee_result("BLH")]
        },
        outcomes_by_fund_code={
            "AAL": TefasManagementFeeHistoryService.ACTION_CREATED,
            "AB1": TefasManagementFeeHistoryService.ACTION_UNCHANGED,
            "BLH": TefasManagementFeeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.refresh_fund_kind(fund_kind="YAT")

    assert result.attempted_count == 3
    assert result.succeeded_count == 3
    assert result.failed_count == 0
    assert result.created_count == 1
    assert result.unchanged_count == 1
    assert result.changed_count == 1
    assert result.failures == ()
    _assert_count_invariants(result)


def test_one_observation_failure_does_not_stop_other_funds() -> None:
    service, _, _, history_service = _service(
        assets_by_kind={"YAT": ["AAL", "AB1", "BLH"]},
        results_by_kind={
            "YAT": [_fee_result("AAL"), _fee_result("AB1"), _fee_result("BLH")]
        },
        outcomes_by_fund_code={
            "AAL": TefasManagementFeeHistoryService.ACTION_CREATED,
            "AB1": RuntimeError("history failed"),
            "BLH": TefasManagementFeeHistoryService.ACTION_CHANGED,
        },
    )

    result = service.refresh_fund_kind(fund_kind="YAT")

    assert [call["observation"].fund_code for call in history_service.calls] == [
        "AAL",
        "AB1",
        "BLH",
    ]
    assert result.attempted_count == 3
    assert result.succeeded_count == 2
    assert result.failed_count == 1
    assert result.created_count == 1
    assert result.changed_count == 1
    assert result.failures == (
        TefasManagementFeeRefreshFailure(
            fund_code="AB1",
            fund_kind="YAT",
            error_type="RuntimeError",
            message="history failed",
        ),
    )
    _assert_count_invariants(result)


def test_unsupported_fund_kind_is_rejected_before_network_call() -> None:
    service, asset_repository, tefas_service, history_service = _service(
        assets_by_kind={"BYF": ["BYF1"]},
        results_by_kind={"BYF": [_fee_result("BYF1", fund_kind="BYF")]},
        outcomes_by_fund_code={"BYF1": TefasManagementFeeHistoryService.ACTION_CREATED},
    )

    with pytest.raises(ValueError, match="YAT and EMK"):
        service.refresh_fund_kind(fund_kind="BYF")  # type: ignore[arg-type]

    assert asset_repository.calls == []
    assert tefas_service.calls == []
    assert history_service.calls == []


def test_unsupported_fund_kind_in_multi_kind_request_is_rejected_before_any_fetch() -> None:
    service, asset_repository, tefas_service, history_service = _service(
        assets_by_kind={"YAT": ["AAL"], "BYF": ["BYF1"]},
        results_by_kind={"YAT": [_fee_result("AAL")]},
        outcomes_by_fund_code={"AAL": TefasManagementFeeHistoryService.ACTION_CREATED},
    )

    with pytest.raises(ValueError, match="YAT and EMK"):
        service.refresh_fund_kinds(fund_kinds=("YAT", "BYF"))  # type: ignore[arg-type]

    assert asset_repository.calls == []
    assert tefas_service.calls == []
    assert history_service.calls == []


def test_unexpected_history_action_fails_loudly() -> None:
    service, _, _, _ = _service(
        assets_by_kind={"YAT": ["AAL"]},
        results_by_kind={"YAT": [_fee_result("AAL")]},
        outcomes_by_fund_code={"AAL": "RENAMED"},
    )

    with pytest.raises(
        ValueError,
        match="Unexpected TEFAS management-fee refresh action: RENAMED",
    ):
        service.refresh_fund_kind(fund_kind="YAT")


def test_observed_at_is_passed_to_history_service() -> None:
    observed_at = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
    service, _, _, history_service = _service(
        assets_by_kind={"YAT": ["AAL"]},
        results_by_kind={"YAT": [_fee_result("AAL")]},
        outcomes_by_fund_code={"AAL": TefasManagementFeeHistoryService.ACTION_CREATED},
    )

    service.refresh_fund_kind(fund_kind="YAT", observed_at=observed_at)

    assert history_service.calls == [
        {"observation": _fee_result("AAL"), "observed_at": observed_at}
    ]
