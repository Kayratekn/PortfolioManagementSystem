from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.model.tefas_fund_type_history import TefasFundTypeHistory
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_type_history_repository import TefasFundTypeHistoryRepository
from src.services.tefas_service import TefasService


class TefasFundTypeHistoryServiceError(RuntimeError):
    """Raised when a TEFAS fund-type observation cannot be applied."""


@dataclass(frozen=True)
class TefasFundTypeHistoryObservationResult:
    asset_id: int
    fund_code: str
    fund_type_name: str
    action: str
    observed_at: datetime


class TefasFundTypeHistoryService:
    ACTION_CREATED = "CREATED"
    ACTION_UNCHANGED = "UNCHANGED"
    ACTION_CHANGED = "CHANGED"

    def __init__(
        self,
        db: Session,
        *,
        asset_repository: AssetRepository | None = None,
        fund_type_history_repository: TefasFundTypeHistoryRepository | None = None,
        tefas_service: TefasService | None = None,
    ) -> None:
        self.db = db
        self.asset_repository = asset_repository or AssetRepository(db)
        self.fund_type_history_repository = (
            fund_type_history_repository or TefasFundTypeHistoryRepository(db)
        )
        self.tefas_service = tefas_service or TefasService()

    def observe_fund_type(
        self,
        *,
        fund_code: str,
        observed_at: datetime | None = None,
    ) -> TefasFundTypeHistoryObservationResult:
        normalized_fund_code = _normalize_fund_code(fund_code)
        resolved_observed_at = _resolve_observed_at(observed_at)

        asset = self.asset_repository.get_by_source_and_code(
            data_source="TEFAS",
            asset_code=normalized_fund_code,
        )
        if asset is None:
            raise TefasFundTypeHistoryServiceError(
                f"TEFAS asset not found: fund_code={normalized_fund_code}"
            )

        fund_type_result = self.tefas_service.get_fund_type(
            fund_code=normalized_fund_code,
        )
        current = self.fund_type_history_repository.get_current_for_asset(
            asset_id=asset.id,
        )
        if current is not None:
            _validate_observation_order(
                observed_at=resolved_observed_at,
                current=current,
            )

        try:
            if current is None:
                history = TefasFundTypeHistory(
                    asset_id=asset.id,
                    fund_type_name=fund_type_result.fund_type_name,
                    source_endpoint=fund_type_result.source_endpoint,
                    source_field_name=fund_type_result.raw_field_name,
                    first_observed_at=resolved_observed_at,
                    last_observed_at=resolved_observed_at,
                    closed_at=None,
                )
                self.fund_type_history_repository.add(history)
                action = self.ACTION_CREATED
            elif current.fund_type_name == fund_type_result.fund_type_name:
                current.last_observed_at = resolved_observed_at
                self.db.flush()
                action = self.ACTION_UNCHANGED
            else:
                current.closed_at = resolved_observed_at
                self.db.flush()
                history = TefasFundTypeHistory(
                    asset_id=asset.id,
                    fund_type_name=fund_type_result.fund_type_name,
                    source_endpoint=fund_type_result.source_endpoint,
                    source_field_name=fund_type_result.raw_field_name,
                    first_observed_at=resolved_observed_at,
                    last_observed_at=resolved_observed_at,
                    closed_at=None,
                )
                self.fund_type_history_repository.add(history)
                action = self.ACTION_CHANGED

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return TefasFundTypeHistoryObservationResult(
            asset_id=asset.id,
            fund_code=normalized_fund_code,
            fund_type_name=fund_type_result.fund_type_name,
            action=action,
            observed_at=resolved_observed_at,
        )


def _normalize_fund_code(fund_code: str) -> str:
    normalized_fund_code = fund_code.strip().upper()
    if not normalized_fund_code:
        raise TefasFundTypeHistoryServiceError("fund_code must not be empty.")
    return normalized_fund_code


def _resolve_observed_at(observed_at: datetime | None) -> datetime:
    resolved_observed_at = observed_at or datetime.now(timezone.utc)
    if resolved_observed_at.tzinfo is None or resolved_observed_at.utcoffset() is None:
        raise TefasFundTypeHistoryServiceError("observed_at must be timezone-aware.")
    return resolved_observed_at.astimezone(timezone.utc)


def _validate_observation_order(
    *,
    observed_at: datetime,
    current: TefasFundTypeHistory,
) -> None:
    first_observed_at = _coerce_stored_datetime_to_utc(current.first_observed_at)
    last_observed_at = _coerce_stored_datetime_to_utc(current.last_observed_at)
    if observed_at < first_observed_at or observed_at < last_observed_at:
        raise TefasFundTypeHistoryServiceError(
            "observed_at cannot be earlier than the current fund-type history period."
        )


def _coerce_stored_datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)