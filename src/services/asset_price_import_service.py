from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset_price import AssetPrice
from src.repositories.asset_price_repository import AssetPriceRepository
from src.services.asset_price_value_validation import validate_asset_price_value


@dataclass(frozen=True)
class AssetPriceImportObservation:
    asset_id: int
    price_date: date
    price: Decimal
    source: str


@dataclass(frozen=True)
class AssetPriceImportResult:
    rows_inserted: int
    rows_skipped: int


class AssetPriceImportConflictError(ValueError):
    def __init__(
        self,
        *,
        asset_id: int,
        price_date: date,
        source: str,
        existing_price: Decimal | None,
        incoming_price: Decimal,
        conflict_kind: str,
    ) -> None:
        self.asset_id = asset_id
        self.price_date = price_date
        self.source = source
        self.existing_price = existing_price
        self.incoming_price = incoming_price
        self.conflict_kind = conflict_kind
        super().__init__(
            "Asset price conflict "
            f"kind={conflict_kind}, asset_id={asset_id}, "
            f"price_date={price_date.isoformat()}, source={source}, "
            f"existing_price={existing_price}, incoming_price={incoming_price}."
        )


class AssetPriceImportService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.asset_price_repository = AssetPriceRepository(db)

    def import_observations(
        self,
        observations: list[AssetPriceImportObservation],
    ) -> AssetPriceImportResult:
        normalized_observations, duplicate_skips = self._validate_and_coalesce(observations)
        if not normalized_observations:
            return AssetPriceImportResult(rows_inserted=0, rows_skipped=duplicate_skips)

        rows_to_insert: list[AssetPriceImportObservation] = []
        existing_skips = 0
        try:
            for observation in normalized_observations:
                existing = self.asset_price_repository.get_by_asset_date_source(
                    asset_id=observation.asset_id,
                    price_date=observation.price_date,
                    source=observation.source,
                )
                if existing is None:
                    rows_to_insert.append(observation)
                    continue
                if existing.price == observation.price:
                    existing_skips += 1
                    continue
                raise AssetPriceImportConflictError(
                    asset_id=observation.asset_id,
                    price_date=observation.price_date,
                    source=observation.source,
                    existing_price=existing.price,
                    incoming_price=observation.price,
                    conflict_kind="EXISTING_OBSERVATION_DIFFERENT_PRICE",
                )

            for observation in rows_to_insert:
                self.asset_price_repository.add(
                    AssetPrice(
                        asset_id=observation.asset_id,
                        price_date=observation.price_date,
                        price=observation.price,
                        source=observation.source,
                    )
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return AssetPriceImportResult(
            rows_inserted=len(rows_to_insert),
            rows_skipped=duplicate_skips + existing_skips,
        )

    @staticmethod
    def _validate_and_coalesce(
        observations: list[AssetPriceImportObservation],
    ) -> tuple[list[AssetPriceImportObservation], int]:
        coalesced: dict[tuple[int, date, str], AssetPriceImportObservation] = {}
        duplicate_skips = 0
        for observation in observations:
            AssetPriceImportService._validate_observation(observation)
            identity = (observation.asset_id, observation.price_date, observation.source)
            previous = coalesced.get(identity)
            if previous is None:
                coalesced[identity] = observation
                continue
            if previous.price == observation.price:
                duplicate_skips += 1
                continue
            raise AssetPriceImportConflictError(
                asset_id=observation.asset_id,
                price_date=observation.price_date,
                source=observation.source,
                existing_price=previous.price,
                incoming_price=observation.price,
                conflict_kind="INCOMING_DUPLICATE_DIFFERENT_PRICE",
            )
        return list(coalesced.values()), duplicate_skips

    @staticmethod
    def _validate_observation(observation: AssetPriceImportObservation) -> None:
        if not isinstance(observation, AssetPriceImportObservation):
            raise ValueError("Asset price observation has an invalid type.")
        if isinstance(observation.asset_id, bool) or not isinstance(observation.asset_id, int) or observation.asset_id <= 0:
            raise ValueError("Asset price observation asset_id must be a positive integer.")
        if isinstance(observation.price_date, datetime) or not isinstance(observation.price_date, date):
            raise ValueError("Asset price observation price_date must be a date.")
        if not isinstance(observation.source, str) or not observation.source.strip():
            raise ValueError("Asset price observation source must not be blank.")
        if observation.source != observation.source.strip():
            raise ValueError("Asset price observation source must not include surrounding whitespace.")
        validate_asset_price_value(observation.price)
