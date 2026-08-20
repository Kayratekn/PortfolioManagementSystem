from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.integrations.tefas_client import FundKind
from src.repositories.asset_repository import AssetRepository
from src.services.tefas_management_fee_history_service import (
    TefasManagementFeeHistoryService,
)
from src.services.tefas_service import TefasManagementFeeResult, TefasService


SUPPORTED_MANAGEMENT_FEE_REFRESH_KINDS = frozenset({"YAT", "EMK"})


@dataclass(frozen=True)
class TefasManagementFeeRefreshFailure:
    fund_code: str
    fund_kind: str
    error_type: str
    message: str


@dataclass(frozen=True)
class TefasManagementFeeRefreshResult:
    attempted_count: int
    succeeded_count: int
    failed_count: int
    created_count: int
    unchanged_count: int
    changed_count: int
    failures: tuple[TefasManagementFeeRefreshFailure, ...]


class TefasManagementFeeRefreshService:
    def __init__(
        self,
        *,
        asset_repository: AssetRepository,
        management_fee_history_service: TefasManagementFeeHistoryService,
        tefas_service: TefasService,
    ) -> None:
        self.asset_repository = asset_repository
        self.management_fee_history_service = management_fee_history_service
        self.tefas_service = tefas_service

    def refresh_fund_kind(
        self,
        *,
        fund_kind: FundKind,
        observed_at: datetime | None = None,
    ) -> TefasManagementFeeRefreshResult:
        return self.refresh_fund_kinds(
            fund_kinds=(fund_kind,),
            observed_at=observed_at,
        )

    def refresh_fund_kinds(
        self,
        *,
        fund_kinds: tuple[FundKind, ...] = ("YAT", "EMK"),
        observed_at: datetime | None = None,
    ) -> TefasManagementFeeRefreshResult:
        normalized_fund_kinds = tuple(
            _normalize_supported_fund_kind(fund_kind) for fund_kind in fund_kinds
        )

        attempted_count = 0
        created_count = 0
        unchanged_count = 0
        changed_count = 0
        failures: list[TefasManagementFeeRefreshFailure] = []

        for fund_kind in normalized_fund_kinds:
            assets = self.asset_repository.list_active_tefas_by_fund_kind(
                fund_kind=fund_kind,
            )
            fees_by_fund_code = {
                result.fund_code: result
                for result in self.tefas_service.fetch_management_fees(
                    fund_kind=fund_kind,
                )
            }

            for asset in assets:
                attempted_count += 1
                observation = fees_by_fund_code.get(asset.asset_code)
                if observation is None:
                    failures.append(
                        TefasManagementFeeRefreshFailure(
                            fund_code=asset.asset_code,
                            fund_kind=fund_kind,
                            error_type="LookupError",
                            message="TEFAS management-fee row not found for active asset.",
                        )
                    )
                    continue

                try:
                    history_result = (
                        self.management_fee_history_service.observe_management_fee(
                            observation=observation,
                            observed_at=observed_at,
                        )
                    )
                except Exception as exc:
                    failures.append(
                        TefasManagementFeeRefreshFailure(
                            fund_code=asset.asset_code,
                            fund_kind=fund_kind,
                            error_type=type(exc).__name__,
                            message=str(exc),
                        )
                    )
                    continue

                if (
                    history_result.action
                    == TefasManagementFeeHistoryService.ACTION_CREATED
                ):
                    created_count += 1
                elif (
                    history_result.action
                    == TefasManagementFeeHistoryService.ACTION_UNCHANGED
                ):
                    unchanged_count += 1
                elif (
                    history_result.action
                    == TefasManagementFeeHistoryService.ACTION_CHANGED
                ):
                    changed_count += 1
                else:
                    raise ValueError(
                        "Unexpected TEFAS management-fee refresh action: "
                        f"{history_result.action}"
                    )

        failed_count = len(failures)
        succeeded_count = created_count + unchanged_count + changed_count

        return TefasManagementFeeRefreshResult(
            attempted_count=attempted_count,
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            created_count=created_count,
            unchanged_count=unchanged_count,
            changed_count=changed_count,
            failures=tuple(failures),
        )


def _normalize_supported_fund_kind(fund_kind: str) -> FundKind:
    normalized_fund_kind = fund_kind.strip().upper()
    if normalized_fund_kind not in SUPPORTED_MANAGEMENT_FEE_REFRESH_KINDS:
        raise ValueError("management-fee refresh supports only YAT and EMK.")
    return normalized_fund_kind  # type: ignore[return-value]
