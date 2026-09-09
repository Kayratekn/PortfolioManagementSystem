from __future__ import annotations

from dataclasses import dataclass


PRECIOUS_METAL_ASSET_TYPE = "PRECIOUS_METAL"
PRECIOUS_METAL_DATA_SOURCE = "BORSA_ISTANBUL"
PRECIOUS_METAL_CURRENCY = "TRY"
PRECIOUS_METAL_QUANTITY_UNIT = "GRAM"
BORSA_ISTANBUL_REFERENCE_PRICES_DATASET = "REFERENCE_PRICES"
BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE = "BORSA_ISTANBUL_REFERENCE_PRICES"


@dataclass(frozen=True)
class SupportedPreciousMetal:
    asset_code: str
    asset_name: str
    asset_type: str
    data_source: str
    currency: str
    quantity_unit: str
    dataset: str
    asset_price_source: str


GOLD = SupportedPreciousMetal(
    asset_code="GOLD",
    asset_name="Gold",
    asset_type=PRECIOUS_METAL_ASSET_TYPE,
    data_source=PRECIOUS_METAL_DATA_SOURCE,
    currency=PRECIOUS_METAL_CURRENCY,
    quantity_unit=PRECIOUS_METAL_QUANTITY_UNIT,
    dataset=BORSA_ISTANBUL_REFERENCE_PRICES_DATASET,
    asset_price_source=BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE,
)
SILVER = SupportedPreciousMetal(
    asset_code="SILVER",
    asset_name="Silver",
    asset_type=PRECIOUS_METAL_ASSET_TYPE,
    data_source=PRECIOUS_METAL_DATA_SOURCE,
    currency=PRECIOUS_METAL_CURRENCY,
    quantity_unit=PRECIOUS_METAL_QUANTITY_UNIT,
    dataset=BORSA_ISTANBUL_REFERENCE_PRICES_DATASET,
    asset_price_source=BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE,
)
PLATINUM = SupportedPreciousMetal(
    asset_code="PLATINUM",
    asset_name="Platinum",
    asset_type=PRECIOUS_METAL_ASSET_TYPE,
    data_source=PRECIOUS_METAL_DATA_SOURCE,
    currency=PRECIOUS_METAL_CURRENCY,
    quantity_unit=PRECIOUS_METAL_QUANTITY_UNIT,
    dataset=BORSA_ISTANBUL_REFERENCE_PRICES_DATASET,
    asset_price_source=BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE,
)

SUPPORTED_PRECIOUS_METALS: dict[str, SupportedPreciousMetal] = {
    GOLD.asset_code: GOLD,
    SILVER.asset_code: SILVER,
    PLATINUM.asset_code: PLATINUM,
}
