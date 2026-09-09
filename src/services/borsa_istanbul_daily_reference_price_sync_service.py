from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session

from src.config.supported_precious_metals import SUPPORTED_PRECIOUS_METALS, SupportedPreciousMetal
from src.integrations.borsa_istanbul_current_reference_prices_client import (
    BorsaIstanbulCurrentReferencePricesClient,
    BorsaIstanbulCurrentReferencePricesSnapshot,
)
from src.model.asset import Asset
from src.repositories.asset_repository import AssetRepository
from src.services.asset_price_import_service import (
    AssetPriceImportObservation,
    AssetPriceImportService,
)
from src.services.borsa_istanbul_reference_price_normalization import normalize_raw_try_per_kg


class BorsaIstanbulDailyReferencePriceSyncError(RuntimeError):
    pass


class BorsaIstanbulCurrentReferencePriceClient(Protocol):
    def fetch_current(self) -> BorsaIstanbulCurrentReferencePricesSnapshot: ...


@dataclass(frozen=True)
class BorsaIstanbulDailyReferencePriceSyncResult:
    effective_date: date
    provider_observations: int
    rows_inserted: int
    rows_skipped: int


class BorsaIstanbulDailyReferencePriceSyncService:
    """Persists one complete current BIST snapshot as a single atomic price batch."""

    def __init__(
        self,
        db: Session,
        client: BorsaIstanbulCurrentReferencePriceClient | None = None,
    ) -> None:
        self.db = db
        self.client = client or BorsaIstanbulCurrentReferencePricesClient()
        self.asset_repository = AssetRepository(db)

    def sync(self) -> BorsaIstanbulDailyReferencePriceSyncResult:
        snapshot = self.client.fetch_current()
        observations = self._build_observations(snapshot)
        import_result = AssetPriceImportService(self.db).import_observations(observations)
        return BorsaIstanbulDailyReferencePriceSyncResult(
            effective_date=snapshot.effective_date,
            provider_observations=len(observations),
            rows_inserted=import_result.rows_inserted,
            rows_skipped=import_result.rows_skipped,
        )

    def _build_observations(
        self,
        snapshot: BorsaIstanbulCurrentReferencePricesSnapshot,
    ) -> list[AssetPriceImportObservation]:
        if not isinstance(snapshot, BorsaIstanbulCurrentReferencePricesSnapshot):
            raise BorsaIstanbulDailyReferencePriceSyncError(
                "BIST current client returned an invalid snapshot type."
            )
        if not isinstance(snapshot.effective_date, date):
            raise BorsaIstanbulDailyReferencePriceSyncError(
                "BIST current snapshot effective date must be a date."
            )

        raw_by_asset_code: dict[str, Decimal] = {
            "GOLD": snapshot.gold_raw_try_per_kg,
            "SILVER": snapshot.silver_raw_try_per_kg,
            "PLATINUM": snapshot.platinum_raw_try_per_kg,
        }
        # Resolve and normalize all three observations before the importer can
        # mutate the session, making malformed or partial snapshots write-free.
        observations: list[AssetPriceImportObservation] = []
        for asset_code in ("GOLD", "SILVER", "PLATINUM"):
            metadata = SUPPORTED_PRECIOUS_METALS[asset_code]
            asset = self._resolve_canonical_asset(metadata)
            observations.append(
                AssetPriceImportObservation(
                    asset_id=asset.id,
                    price_date=snapshot.effective_date,
                    price=normalize_raw_try_per_kg(raw_by_asset_code[asset_code]),
                    source=metadata.asset_price_source,
                )
            )
        return observations

    def _resolve_canonical_asset(self, metadata: SupportedPreciousMetal) -> Asset:
        asset = self.asset_repository.get_by_source_and_code(
            data_source=metadata.data_source,
            asset_code=metadata.asset_code,
        )
        if asset is None:
            raise BorsaIstanbulDailyReferencePriceSyncError(
                "Canonical precious-metal asset is missing: "
                f"{metadata.data_source}/{metadata.asset_code}. "
                "Run the controlled catalog bootstrap first."
            )
        expected = {
            "asset_code": metadata.asset_code,
            "asset_name": metadata.asset_name,
            "asset_type": metadata.asset_type,
            "currency": metadata.currency,
            "data_source": metadata.data_source,
            "fund_kind": None,
            "isin": None,
            "is_active": True,
        }
        mismatches = [
            field_name
            for field_name, expected_value in expected.items()
            if getattr(asset, field_name) != expected_value
        ]
        if mismatches:
            raise BorsaIstanbulDailyReferencePriceSyncError(
                "Canonical precious-metal asset is incompatible: "
                f"{metadata.data_source}/{metadata.asset_code}; {', '.join(mismatches)}."
            )
        return asset
