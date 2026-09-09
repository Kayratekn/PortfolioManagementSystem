from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol

from sqlalchemy.orm import Session

from src.config.supported_precious_metals import SUPPORTED_PRECIOUS_METALS, SupportedPreciousMetal
from src.integrations.borsa_istanbul_reference_prices_client import BorsaIstanbulHistoricalObservation
from src.model.asset import Asset
from src.repositories.asset_repository import AssetRepository
from src.services.asset_price_import_service import AssetPriceImportObservation, AssetPriceImportResult, AssetPriceImportService
from src.services.borsa_istanbul_reference_price_normalization import normalize_raw_try_per_kg


HISTORICAL_MINIMUM_DATE = date(2008, 8, 4)
DEFAULT_BATCH_DAYS = 31
PROVIDER_CODE_BY_ASSET_CODE = {"GOLD": "AU", "SILVER": "AG", "PLATINUM": "PT"}
ASSET_CODE_BY_PROVIDER_CODE = {value: key for key, value in PROVIDER_CODE_BY_ASSET_CODE.items()}


class BorsaIstanbulHistoricalBackfillError(RuntimeError):
    pass


class BorsaIstanbulHistoricalClient(Protocol):
    def fetch_historical(
        self, *, start_date: date, end_date: date, provider_metal_code: str
    ) -> list[BorsaIstanbulHistoricalObservation]: ...


@dataclass(frozen=True)
class BorsaIstanbulHistoricalBackfillResult:
    provider_observations: int
    rows_inserted: int
    rows_skipped: int
    batches_completed: int
    dry_run: bool


class BorsaIstanbulHistoricalBackfillService:
    """Backfills independently committed date batches; a failed batch is atomic, prior batches remain resumable."""

    def __init__(self, db: Session, client: BorsaIstanbulHistoricalClient) -> None:
        self.db = db
        self.client = client
        self.asset_repository = AssetRepository(db)

    def backfill(
        self,
        *,
        start_date: date,
        end_date: date,
        asset_codes: tuple[str, ...] = ("GOLD", "SILVER", "PLATINUM"),
        batch_days: int = DEFAULT_BATCH_DAYS,
        apply: bool = False,
    ) -> BorsaIstanbulHistoricalBackfillResult:
        metadata_by_code = self._validate_request(start_date, end_date, asset_codes, batch_days)
        assets_by_code = {code: self._resolve_canonical_asset(metadata) for code, metadata in metadata_by_code.items()}
        provider_observations = inserted = skipped = completed = 0
        for batch_start, batch_end in self._date_batches(start_date, end_date, batch_days):
            canonical = self._fetch_and_map_batch(
                batch_start=batch_start,
                batch_end=batch_end,
                metadata_by_code=metadata_by_code,
                assets_by_code=assets_by_code,
            )
            provider_observations += len(canonical)
            if apply:
                result = AssetPriceImportService(self.db).import_observations(canonical)
                inserted += result.rows_inserted
                skipped += result.rows_skipped
            completed += 1
        return BorsaIstanbulHistoricalBackfillResult(provider_observations, inserted, skipped, completed, not apply)

    def _fetch_and_map_batch(self, *, batch_start: date, batch_end: date, metadata_by_code: dict[str, SupportedPreciousMetal], assets_by_code: dict[str, Asset]) -> list[AssetPriceImportObservation]:
        observations: list[AssetPriceImportObservation] = []
        for asset_code, metadata in metadata_by_code.items():
            provider_code = PROVIDER_CODE_BY_ASSET_CODE[asset_code]
            fetched = self.client.fetch_historical(start_date=batch_start, end_date=batch_end, provider_metal_code=provider_code)
            for observation in fetched:
                if observation.provider_metal_code != provider_code:
                    raise BorsaIstanbulHistoricalBackfillError("BIST client returned an observation for a different metal.")
                observations.append(AssetPriceImportObservation(
                    asset_id=assets_by_code[asset_code].id,
                    price_date=observation.price_date,
                    price=normalize_raw_try_per_kg(observation.raw_try_per_kg),
                    source=metadata.asset_price_source,
                ))
        # This makes duplicate handling and persistence deterministic irrespective of BIST ordering.
        return sorted(observations, key=lambda item: (item.price_date, item.asset_id, item.source))

    @staticmethod
    def _date_batches(start_date: date, end_date: date, batch_days: int):
        cursor = start_date
        while cursor <= end_date:
            batch_end = min(cursor + timedelta(days=batch_days - 1), end_date)
            yield cursor, batch_end
            cursor = batch_end + timedelta(days=1)

    def _resolve_canonical_asset(self, metadata: SupportedPreciousMetal) -> Asset:
        asset = self.asset_repository.get_by_source_and_code(data_source=metadata.data_source, asset_code=metadata.asset_code)
        if asset is None:
            raise BorsaIstanbulHistoricalBackfillError(
                f"Canonical precious-metal asset is missing: {metadata.data_source}/{metadata.asset_code}. Run the controlled catalog bootstrap first."
            )
        expected = {
            "asset_name": metadata.asset_name, "asset_type": metadata.asset_type,
            "currency": metadata.currency, "data_source": metadata.data_source,
            "fund_kind": None, "isin": None, "is_active": True,
        }
        mismatches = [field for field, expected_value in expected.items() if getattr(asset, field) != expected_value]
        if mismatches:
            raise BorsaIstanbulHistoricalBackfillError(
                f"Canonical precious-metal asset is incompatible: {metadata.data_source}/{metadata.asset_code}; {', '.join(mismatches)}."
            )
        return asset

    @staticmethod
    def _validate_request(start_date: date, end_date: date, asset_codes: tuple[str, ...], batch_days: int) -> dict[str, SupportedPreciousMetal]:
        if not isinstance(start_date, date) or not isinstance(end_date, date):
            raise ValueError("Backfill dates must be date instances.")
        if start_date < HISTORICAL_MINIMUM_DATE:
            raise ValueError(f"BIST reference-price history starts on {HISTORICAL_MINIMUM_DATE.isoformat()}.")
        if end_date < start_date:
            raise ValueError("end_date cannot be earlier than start_date.")
        if isinstance(batch_days, bool) or not isinstance(batch_days, int) or batch_days <= 0:
            raise ValueError("batch_days must be a positive integer.")
        if not asset_codes:
            raise ValueError("At least one precious metal must be requested.")
        if len(set(asset_codes)) != len(asset_codes):
            raise ValueError("Requested precious metals must not contain duplicates.")
        try:
            return {code: SUPPORTED_PRECIOUS_METALS[code] for code in asset_codes}
        except KeyError as exc:
            raise ValueError(f"Unsupported precious metal: {exc.args[0]}.") from exc
