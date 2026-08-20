from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.tefas_management_fee_history import TefasManagementFeeHistory
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_management_fee_history_repository import (
    TefasManagementFeeHistoryRepository,
)
from src.services.tefas_service import TefasManagementFeeResult


class TefasManagementFeeHistoryServiceError(RuntimeError):
    """Raised when a TEFAS management-fee observation cannot be applied."""


@dataclass(frozen=True)
class TefasManagementFeeHistoryObservationResult:
    asset_id: int
    fund_code: str
    management_fee_percentage: Decimal
    action: str
    observed_at: datetime


class TefasManagementFeeHistoryService:
    ACTION_CREATED = "CREATED"
    ACTION_UNCHANGED = "UNCHANGED"
    ACTION_CHANGED = "CHANGED"

    def __init__(
        self,
        db: Session,
        *,
        asset_repository: AssetRepository | None = None,
        management_fee_history_repository: (
            TefasManagementFeeHistoryRepository | None
        ) = None,
    ) -> None:
        self.db = db
        self.asset_repository = asset_repository or AssetRepository(db)
        self.management_fee_history_repository = (
            management_fee_history_repository or TefasManagementFeeHistoryRepository(db)
        )

    def observe_management_fee(
        self,
        *,
        observation: TefasManagementFeeResult,
        observed_at: datetime | None = None,
    ) -> TefasManagementFeeHistoryObservationResult:
        normalized_fund_code = _normalize_fund_code(observation.fund_code)
        resolved_observed_at = _resolve_observed_at(observed_at)
        source_endpoint = _normalize_required_string(
            observation.source_endpoint,
            field_name="source_endpoint",
        )
        source_field_name = _normalize_required_string(
            observation.raw_field_name,
            field_name="source_field_name",
        )

        asset = self.asset_repository.get_by_source_and_code(
            data_source="TEFAS",
            asset_code=normalized_fund_code,
        )
        if asset is None:
            raise TefasManagementFeeHistoryServiceError(
                f"TEFAS asset not found: fund_code={normalized_fund_code}"
            )

        current = self.management_fee_history_repository.get_current_for_asset(
            asset_id=asset.id,
        )
        if current is not None:
            _validate_observation_order(
                observed_at=resolved_observed_at,
                current=current,
            )

        try:
            if current is None:
                history = TefasManagementFeeHistory(
                    asset_id=asset.id,
                    management_fee_percentage=observation.management_fee_percentage,
                    source_endpoint=source_endpoint,
                    source_field_name=source_field_name,
                    first_observed_at=resolved_observed_at,
                    last_observed_at=resolved_observed_at,
                    closed_at=None,
                )
                self.management_fee_history_repository.add(history)
                action = self.ACTION_CREATED
            elif _decimal_values_equal(
                current.management_fee_percentage,
                observation.management_fee_percentage,
            ):
                current.last_observed_at = resolved_observed_at
                self.db.flush()
                action = self.ACTION_UNCHANGED
            else:
                current.closed_at = resolved_observed_at
                self.db.flush()
                history = TefasManagementFeeHistory(
                    asset_id=asset.id,
                    management_fee_percentage=observation.management_fee_percentage,
                    source_endpoint=source_endpoint,
                    source_field_name=source_field_name,
                    first_observed_at=resolved_observed_at,
                    last_observed_at=resolved_observed_at,
                    closed_at=None,
                )
                self.management_fee_history_repository.add(history)
                action = self.ACTION_CHANGED

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return TefasManagementFeeHistoryObservationResult(
            asset_id=asset.id,
            fund_code=normalized_fund_code,
            management_fee_percentage=observation.management_fee_percentage,
            action=action,
            observed_at=resolved_observed_at,
        )


def _normalize_fund_code(fund_code: str) -> str:
    normalized_fund_code = fund_code.strip().upper()
    if not normalized_fund_code:
        raise TefasManagementFeeHistoryServiceError("fund_code must not be empty.")
    return normalized_fund_code


def _resolve_observed_at(observed_at: datetime | None) -> datetime:
    resolved_observed_at = observed_at or datetime.now(timezone.utc)
    if resolved_observed_at.tzinfo is None or resolved_observed_at.utcoffset() is None:
        raise TefasManagementFeeHistoryServiceError("observed_at must be timezone-aware.")
    return resolved_observed_at.astimezone(timezone.utc)


def _normalize_required_string(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise TefasManagementFeeHistoryServiceError(f"{field_name} must be a string.")

    normalized_value = value.strip()
    if not normalized_value:
        raise TefasManagementFeeHistoryServiceError(f"{field_name} must not be empty.")

    return normalized_value


def _validate_observation_order(
    *,
    observed_at: datetime,
    current: TefasManagementFeeHistory,
) -> None:
    first_observed_at = _coerce_stored_datetime_to_utc(current.first_observed_at)
    last_observed_at = _coerce_stored_datetime_to_utc(current.last_observed_at)
    if observed_at < first_observed_at or observed_at < last_observed_at:
        raise TefasManagementFeeHistoryServiceError(
            "observed_at cannot be earlier than the current management-fee "
            "history period."
        )


def _coerce_stored_datetime_to_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _decimal_values_equal(left: Decimal, right: Decimal) -> bool:
    return Decimal(left) == Decimal(right)
