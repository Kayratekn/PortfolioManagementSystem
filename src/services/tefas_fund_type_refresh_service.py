from __future__ import annotations

from dataclasses import dataclass

from src.repositories.asset_repository import AssetRepository
from src.services.tefas_fund_type_history_service import TefasFundTypeHistoryService


@dataclass(frozen=True)
class TefasFundTypeRefreshFailure:
    fund_code: str
    error_type: str
    message: str


@dataclass(frozen=True)
class TefasFundTypeRefreshResult:
    attempted_count: int
    succeeded_count: int
    failed_count: int
    created_count: int
    unchanged_count: int
    changed_count: int
    failures: tuple[TefasFundTypeRefreshFailure, ...]


class TefasFundTypeRefreshService:
    def __init__(
        self,
        *,
        asset_repository: AssetRepository,
        fund_type_history_service: TefasFundTypeHistoryService,
    ) -> None:
        self.asset_repository = asset_repository
        self.fund_type_history_service = fund_type_history_service

    def refresh_active_tefas_funds(self) -> TefasFundTypeRefreshResult:
        assets = self.asset_repository.list_active_by_data_source("TEFAS")
        created_count = 0
        unchanged_count = 0
        changed_count = 0
        failures: list[TefasFundTypeRefreshFailure] = []

        for asset in assets:
            try:
                result = self.fund_type_history_service.observe_fund_type(
                    fund_code=asset.asset_code,
                )
            except Exception as exc:
                failures.append(
                    TefasFundTypeRefreshFailure(
                        fund_code=asset.asset_code,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
                continue

            if result.action == TefasFundTypeHistoryService.ACTION_CREATED:
                created_count += 1
            elif result.action == TefasFundTypeHistoryService.ACTION_UNCHANGED:
                unchanged_count += 1
            elif result.action == TefasFundTypeHistoryService.ACTION_CHANGED:
                changed_count += 1
            else:
                raise ValueError(f"Unexpected TEFAS fund-type refresh action: {result.action}")

        failed_count = len(failures)
        succeeded_count = created_count + unchanged_count + changed_count

        return TefasFundTypeRefreshResult(
            attempted_count=len(assets),
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            created_count=created_count,
            unchanged_count=unchanged_count,
            changed_count=changed_count,
            failures=tuple(failures),
        )
