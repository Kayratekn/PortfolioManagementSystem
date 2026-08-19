from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_detail_snapshot_repository import (
    TefasFundDetailSnapshotRepository,
)
from src.services.tefas_service import TefasService


class TefasFundDetailSnapshotObservationServiceError(RuntimeError):
    """Raised when a TEFAS fund detail snapshot observation cannot be persisted."""


class TefasFundDetailSnapshotObservationService:
    def __init__(
        self,
        db: Session,
        *,
        asset_repository: AssetRepository | None = None,
        detail_snapshot_repository: TefasFundDetailSnapshotRepository | None = None,
        tefas_service: TefasService | None = None,
    ) -> None:
        self.db = db
        self.asset_repository = asset_repository or AssetRepository(db)
        self.detail_snapshot_repository = (
            detail_snapshot_repository or TefasFundDetailSnapshotRepository(db)
        )
        self.tefas_service = tefas_service or TefasService()

    def observe_fund_detail_snapshot(
        self,
        *,
        fund_code: str,
        observed_at: datetime | None = None,
    ) -> TefasFundDetailSnapshot:
        normalized_fund_code = _normalize_fund_code(fund_code)
        resolved_observed_at = _resolve_observed_at(observed_at)

        asset = self.asset_repository.get_by_source_and_code(
            data_source="TEFAS",
            asset_code=normalized_fund_code,
        )
        if asset is None or asset.is_active is not True:
            raise TefasFundDetailSnapshotObservationServiceError(
                f"Active TEFAS asset not found: fund_code={normalized_fund_code}"
            )

        try:
            metadata = self.tefas_service.get_fund_detail_page_metadata(
                fund_code=normalized_fund_code,
            )
            isin_changed = _enrich_asset_isin_from_metadata(
                asset=asset,
                metadata_isin=metadata.isin,
                fund_code=normalized_fund_code,
            )
            existing_snapshot = self.detail_snapshot_repository.get_by_asset_and_observed_at(
                asset_id=asset.id,
                observed_at=resolved_observed_at,
            )
            if existing_snapshot is not None:
                _validate_existing_snapshot_matches_metadata(
                    snapshot=existing_snapshot,
                    fund_code=normalized_fund_code,
                    fund_category=metadata.fund_category,
                    category_rank=metadata.category_rank,
                    category_fund_count=metadata.category_fund_count,
                    market_share_raw=metadata.market_share_raw,
                    risk_value=metadata.risk_value,
                    source_page=metadata.source_page,
                )
                if isin_changed:
                    self.db.commit()
                return existing_snapshot

            snapshot = TefasFundDetailSnapshot(
                asset_id=asset.id,
                fund_category=metadata.fund_category,
                category_rank=metadata.category_rank,
                category_fund_count=metadata.category_fund_count,
                market_share_raw=metadata.market_share_raw,
                risk_value=metadata.risk_value,
                source_page=metadata.source_page,
                observed_at=resolved_observed_at,
            )
            self.detail_snapshot_repository.add(snapshot)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return snapshot


def _enrich_asset_isin_from_metadata(
    *,
    asset: Asset,
    metadata_isin: str | None,
    fund_code: str,
) -> bool:
    if metadata_isin is None:
        return False

    if asset.isin is None:
        asset.isin = metadata_isin
        return True

    if asset.isin == metadata_isin:
        return False

    raise TefasFundDetailSnapshotObservationServiceError(
        "Conflicting TEFAS asset ISIN metadata: "
        f"fund_code={fund_code}, asset_isin={asset.isin}, metadata_isin={metadata_isin}"
    )


def _normalize_fund_code(fund_code: str) -> str:
    normalized_fund_code = fund_code.strip().upper()
    if not normalized_fund_code:
        raise TefasFundDetailSnapshotObservationServiceError("fund_code must not be empty.")
    return normalized_fund_code


def _resolve_observed_at(observed_at: datetime | None) -> datetime:
    resolved_observed_at = observed_at or datetime.now(timezone.utc)
    if resolved_observed_at.tzinfo is None or resolved_observed_at.utcoffset() is None:
        raise TefasFundDetailSnapshotObservationServiceError(
            "observed_at must be timezone-aware."
        )
    return resolved_observed_at.astimezone(timezone.utc)


def _validate_existing_snapshot_matches_metadata(
    *,
    snapshot: TefasFundDetailSnapshot,
    fund_code: str,
    fund_category: str,
    category_rank: int | None,
    category_fund_count: int | None,
    market_share_raw: object,
    risk_value: int | None,
    source_page: str,
) -> None:
    if (
        snapshot.fund_category == fund_category
        and snapshot.category_rank == category_rank
        and snapshot.category_fund_count == category_fund_count
        and snapshot.market_share_raw == market_share_raw
        and snapshot.risk_value == risk_value
        and snapshot.source_page == source_page
    ):
        return

    raise TefasFundDetailSnapshotObservationServiceError(
        "Conflicting TEFAS fund detail snapshot observation: "
        f"fund_code={fund_code}, observed_at={snapshot.observed_at.isoformat()}"
    )
