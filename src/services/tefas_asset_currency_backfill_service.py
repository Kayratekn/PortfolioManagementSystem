from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.repositories.asset_repository import AssetRepository


class TefasAssetCurrencyConflictError(RuntimeError):
    """Raised when existing TEFAS currencies conflict with the canonical value."""


@dataclass(frozen=True)
class TefasAssetCurrencyBackfillResult:
    null_currency_count: int
    try_currency_count: int
    non_try_currency_conflict_count: int
    affected_count: int
    applied: bool


class TefasAssetCurrencyBackfillService:
    def __init__(self, *, db: Session, asset_repository: AssetRepository) -> None:
        self.db = db
        self.asset_repository = asset_repository

    def inspect(self) -> TefasAssetCurrencyBackfillResult:
        return TefasAssetCurrencyBackfillResult(
            null_currency_count=self.asset_repository.count_tefas_assets_with_null_currency(),
            try_currency_count=self.asset_repository.count_tefas_assets_with_try_currency(),
            non_try_currency_conflict_count=(
                self.asset_repository.count_tefas_assets_with_non_try_currency()
            ),
            affected_count=0,
            applied=False,
        )

    def apply(self) -> TefasAssetCurrencyBackfillResult:
        preflight = self.inspect()
        if preflight.non_try_currency_conflict_count:
            raise TefasAssetCurrencyConflictError(
                "TEFAS assets with non-TRY currencies require manual resolution."
            )

        try:
            affected_count = (
                self.asset_repository.set_try_currency_for_tefas_assets_with_null_currency()
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return TefasAssetCurrencyBackfillResult(
            null_currency_count=preflight.null_currency_count,
            try_currency_count=preflight.try_currency_count,
            non_try_currency_conflict_count=preflight.non_try_currency_conflict_count,
            affected_count=affected_count,
            applied=True,
        )