from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import time

from src.repositories.asset_repository import AssetRepository
from src.services.tefas_fund_type_history_service import TefasFundTypeHistoryService


@dataclass(frozen=True)
class TefasFundTypeBackfillFailure:
    fund_code: str
    error_type: str
    message: str


@dataclass(frozen=True)
class TefasFundTypeBackfillResult:
    fund_kind: str
    limit: int
    attempted_count: int
    succeeded_count: int
    failed_count: int
    created_count: int
    unchanged_count: int
    changed_count: int
    failures: tuple[TefasFundTypeBackfillFailure, ...]


class TefasFundTypeBackfillService:
    VALID_FUND_KINDS = frozenset({"YAT", "EMK", "BYF", "GYF", "GSYF"})

    def __init__(
        self,
        *,
        asset_repository: AssetRepository,
        fund_type_history_service: TefasFundTypeHistoryService,
        sleep_func: Callable[[float], None] = time.sleep,
    ) -> None:
        self.asset_repository = asset_repository
        self.fund_type_history_service = fund_type_history_service
        self.sleep_func = sleep_func

    def backfill_missing_active_tefas_funds(
        self,
        *,
        fund_kind: str,
        limit: int,
        delay_seconds: float = 1.0,
    ) -> TefasFundTypeBackfillResult:
        normalized_fund_kind = fund_kind.strip().upper()
        if normalized_fund_kind not in self.VALID_FUND_KINDS:
            raise ValueError("fund_kind must be one of: BYF, EMK, GSYF, GYF, YAT")
        if limit <= 0:
            raise ValueError("limit must be positive.")
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be greater than or equal to 0.")

        assets = self.asset_repository.list_active_tefas_without_current_fund_type(
            fund_kind=normalized_fund_kind,
            limit=limit,
        )

        created_count = 0
        unchanged_count = 0
        changed_count = 0
        failures: list[TefasFundTypeBackfillFailure] = []

        for index, asset in enumerate(assets):
            try:
                result = self.fund_type_history_service.observe_fund_type(
                    fund_code=asset.asset_code,
                )
            except Exception as exc:
                failures.append(
                    TefasFundTypeBackfillFailure(
                        fund_code=asset.asset_code,
                        error_type=type(exc).__name__,
                        message=str(exc),
                    )
                )
            else:
                if result.action == TefasFundTypeHistoryService.ACTION_CREATED:
                    created_count += 1
                elif result.action == TefasFundTypeHistoryService.ACTION_UNCHANGED:
                    unchanged_count += 1
                elif result.action == TefasFundTypeHistoryService.ACTION_CHANGED:
                    changed_count += 1
                else:
                    raise ValueError(
                        f"Unexpected TEFAS fund-type backfill action: {result.action}"
                    )

            if index < len(assets) - 1 and delay_seconds > 0:
                self.sleep_func(delay_seconds)

        failed_count = len(failures)
        succeeded_count = created_count + unchanged_count + changed_count

        return TefasFundTypeBackfillResult(
            fund_kind=normalized_fund_kind,
            limit=limit,
            attempted_count=len(assets),
            succeeded_count=succeeded_count,
            failed_count=failed_count,
            created_count=created_count,
            unchanged_count=unchanged_count,
            changed_count=changed_count,
            failures=tuple(failures),
        )
