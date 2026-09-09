from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.config.supported_precious_metals import SUPPORTED_PRECIOUS_METALS, SupportedPreciousMetal
from src.model.asset import Asset
from src.repositories.asset_price_repository import AssetPriceRepository
from src.services.tefas_valuation_price_service import (
    SUPPORTED_FUND_KINDS,
    TEFAS_SOURCE,
    TefasValuationPriceService,
)


BIST_REFERENCE_PRICE_KIND = "REFERENCE_PRICE"


@dataclass(frozen=True)
class ValuationPrice:
    price: Decimal
    price_date: date
    price_kind: str
    source: str


def is_supported_valuation_asset(asset: Asset) -> bool:
    return _is_supported_tefas_asset(asset) or _is_canonical_bist_precious_metal(asset)


def _is_supported_tefas_asset(asset: Asset) -> bool:
    return (
        asset.data_source == TEFAS_SOURCE
        and asset.asset_type == "FUND"
        and asset.fund_kind in SUPPORTED_FUND_KINDS
    )


def _is_canonical_bist_precious_metal(asset: Asset) -> bool:
    metadata = SUPPORTED_PRECIOUS_METALS.get(asset.asset_code)
    if metadata is None:
        return False
    return _asset_matches_metadata(asset, metadata)


def _asset_matches_metadata(asset: Asset, metadata: SupportedPreciousMetal) -> bool:
    return (
        asset.asset_code == metadata.asset_code
        and asset.asset_name == metadata.asset_name
        and asset.asset_type == metadata.asset_type
        and asset.data_source == metadata.data_source
        and asset.currency == metadata.currency
        and asset.fund_kind is None
        and asset.isin is None
        and asset.is_active is True
    )


class ValuationPriceService:
    """Selects persisted canonical prices without provider transport coupling."""

    def __init__(
        self,
        tefas_valuation_price_service: TefasValuationPriceService,
        asset_price_repository: AssetPriceRepository,
    ) -> None:
        self.tefas_valuation_price_service = tefas_valuation_price_service
        self.asset_price_repository = asset_price_repository

    def get_price(self, *, asset: Asset, valuation_date: date) -> ValuationPrice | None:
        if _is_supported_tefas_asset(asset):
            selected = self.tefas_valuation_price_service.get_price(
                asset=asset,
                valuation_date=valuation_date,
            )
            if selected is None:
                return None
            return ValuationPrice(
                price=selected.price,
                price_date=selected.price_date,
                price_kind=selected.price_kind,
                source=selected.source,
            )

        if not _is_canonical_bist_precious_metal(asset):
            raise ValueError("Unsupported asset for valuation price selection.")

        metadata = SUPPORTED_PRECIOUS_METALS[asset.asset_code]
        selected = self.asset_price_repository.get_latest_on_or_before(
            asset_id=asset.id,
            price_date=valuation_date,
            source=metadata.asset_price_source,
        )
        if selected is None:
            return None
        if not isinstance(selected.price, Decimal) or not selected.price.is_finite() or selected.price <= 0:
            raise ValueError("Selected BIST precious-metal valuation price must be finite and greater than 0.")
        return ValuationPrice(
            price=selected.price,
            price_date=selected.price_date,
            price_kind=BIST_REFERENCE_PRICE_KIND,
            source=metadata.asset_price_source,
        )