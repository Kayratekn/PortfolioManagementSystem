from src.config.supported_precious_metals import (
    BORSA_ISTANBUL_REFERENCE_PRICES_DATASET,
    BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE,
    PRECIOUS_METAL_CURRENCY,
    PRECIOUS_METAL_DATA_SOURCE,
    PRECIOUS_METAL_QUANTITY_UNIT,
    SUPPORTED_PRECIOUS_METALS,
)


def test_supported_precious_metals_lock_the_bist_reference_price_contract() -> None:
    assert list(SUPPORTED_PRECIOUS_METALS) == ["GOLD", "SILVER", "PLATINUM"]
    assert [metal.asset_name for metal in SUPPORTED_PRECIOUS_METALS.values()] == [
        "Gold",
        "Silver",
        "Platinum",
    ]
    assert {metal.asset_type for metal in SUPPORTED_PRECIOUS_METALS.values()} == {
        "PRECIOUS_METAL"
    }
    assert {metal.data_source for metal in SUPPORTED_PRECIOUS_METALS.values()} == {
        PRECIOUS_METAL_DATA_SOURCE
    }
    assert PRECIOUS_METAL_DATA_SOURCE == "BORSA_ISTANBUL"
    assert {metal.dataset for metal in SUPPORTED_PRECIOUS_METALS.values()} == {
        BORSA_ISTANBUL_REFERENCE_PRICES_DATASET
    }
    assert BORSA_ISTANBUL_REFERENCE_PRICES_DATASET == "REFERENCE_PRICES"
    assert {metal.currency for metal in SUPPORTED_PRECIOUS_METALS.values()} == {
        PRECIOUS_METAL_CURRENCY
    }
    assert PRECIOUS_METAL_CURRENCY == "TRY"
    assert {metal.quantity_unit for metal in SUPPORTED_PRECIOUS_METALS.values()} == {
        PRECIOUS_METAL_QUANTITY_UNIT
    }
    assert PRECIOUS_METAL_QUANTITY_UNIT == "GRAM"
    assert {metal.asset_price_source for metal in SUPPORTED_PRECIOUS_METALS.values()} == {
        BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE
    }
    assert BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE == "BORSA_ISTANBUL_REFERENCE_PRICES"
