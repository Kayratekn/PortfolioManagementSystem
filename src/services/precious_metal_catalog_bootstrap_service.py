from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.config.supported_precious_metals import (
    SUPPORTED_PRECIOUS_METALS,
    SupportedPreciousMetal,
)
from src.model.asset import Asset
from src.repositories.asset_repository import AssetRepository


class PreciousMetalCatalogBootstrapConflictError(ValueError):
    pass


@dataclass(frozen=True)
class PreciousMetalCatalogBootstrapResult:
    assets_created: int
    assets_skipped: int


class PreciousMetalCatalogBootstrapService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.asset_repository = AssetRepository(db)

    def bootstrap(self) -> PreciousMetalCatalogBootstrapResult:
        assets_created = 0
        assets_skipped = 0
        try:
            for metadata in SUPPORTED_PRECIOUS_METALS.values():
                existing = self.asset_repository.get_by_source_and_code(
                    data_source=metadata.data_source,
                    asset_code=metadata.asset_code,
                )
                if existing is None:
                    self.asset_repository.add(self._build_asset(metadata))
                    assets_created += 1
                    continue

                self._raise_if_incompatible(existing, metadata)
                assets_skipped += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return PreciousMetalCatalogBootstrapResult(
            assets_created=assets_created,
            assets_skipped=assets_skipped,
        )

    @staticmethod
    def _build_asset(metadata: SupportedPreciousMetal) -> Asset:
        return Asset(
            asset_code=metadata.asset_code,
            asset_name=metadata.asset_name,
            asset_type=metadata.asset_type,
            fund_kind=None,
            isin=None,
            currency=metadata.currency,
            data_source=metadata.data_source,
            is_active=True,
        )

    @staticmethod
    def _raise_if_incompatible(
        existing: Asset,
        metadata: SupportedPreciousMetal,
    ) -> None:
        expected = {
            "asset_code": metadata.asset_code,
            "asset_name": metadata.asset_name,
            "asset_type": metadata.asset_type,
            "fund_kind": None,
            "isin": None,
            "currency": metadata.currency,
            "data_source": metadata.data_source,
            "is_active": True,
        }
        mismatches = [
            field_name
            for field_name, expected_value in expected.items()
            if getattr(existing, field_name) != expected_value
        ]
        if mismatches:
            raise PreciousMetalCatalogBootstrapConflictError(
                "Precious-metal catalog conflict for "
                f"data_source={metadata.data_source}, asset_code={metadata.asset_code}: "
                f"{', '.join(mismatches)}."
            )
