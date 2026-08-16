from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from src.repositories.asset_repository import AssetRepository
from src.services.tefas_fund_detail_snapshot_observation_service import (
    TefasFundDetailSnapshotObservationService,
)


@dataclass(frozen=True)
class TefasFundDetailSnapshotBulkRefreshFailure:
    fund_code: str
    error_type: str
    message: str


@dataclass(frozen=True)
class TefasFundDetailSnapshotBulkRefreshResult:
    limit: int
    attempted_count: int
    succeeded_count: int
    failed_count: int
    successful_fund_codes: tuple[str, ...]
    failures: tuple[TefasFundDetailSnapshotBulkRefreshFailure, ...]


class TefasFundDetailSnapshotBulkRefreshService:
    def __init__(
        self,
        *,
        asset_repository: AssetRepository,
        observation_service: TefasFundDetailSnapshotObservationService,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.asset_repository = asset_repository
        self.observation_service = observation_service
        self.sleep_func = sleep_func

    def refresh_active_tefas_fund_detail_snapshots(
        self,
        *,
        limit: int,
        delay_seconds: float = 1.0,
    ) -> TefasFundDetailSnapshotBulkRefreshResult:
        if not isinstance(limit, int) or isinstance(limit, bool):
            raise ValueError("limit must be a positive integer.")
        if limit <= 0:
            raise ValueError("limit must be positive.")
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be greater than or equal to 0.")

        assets = self.asset_repository.list_active_tefas_assets(limit=limit)
        successful_fund_codes: list[str] = []
        failures: list[TefasFundDetailSnapshotBulkRefreshFailure] = []

        for index, asset in enumerate(assets):
            fund_code = asset.asset_code
            try:
                self.observation_service.observe_fund_detail_snapshot(
                    fund_code=fund_code,
                )
            except Exception as exc:
                failures.append(
                    TefasFundDetailSnapshotBulkRefreshFailure(
                        fund_code=fund_code,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
            else:
                successful_fund_codes.append(fund_code)

            if index < len(assets) - 1 and delay_seconds > 0:
                self.sleep_func(delay_seconds)

        failed_count = len(failures)
        succeeded_count = len(successful_fund_codes)

        return TefasFundDetailSnapshotBulkRefreshResult(
            limit=limit,
            attempted_count=len(assets),
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            successful_fund_codes=tuple(successful_fund_codes),
            failures=tuple(failures),
        )
