from decimal import Decimal

import pytest

from src.services.asset_price_value_validation import (
    AssetPriceValueError,
    validate_asset_price_value,
)


@pytest.mark.parametrize(
    "value",
    [
        Decimal("1"),
        Decimal("1.23000000"),
        Decimal("0.00000001"),
        Decimal("999999999999"),
        Decimal("999999999999.99999999"),
        Decimal("1.230000000000000000"),
        Decimal("1.23E+2"),
        Decimal("1E-8"),
    ],
)
def test_accepts_exactly_representable_numeric_20_8_values(value: Decimal) -> None:
    assert validate_asset_price_value(value) is value


@pytest.mark.parametrize(
    "value",
    [
        Decimal("1.00000000000000000000000000001"),
        Decimal("0.000000001"),
        Decimal("999999999999.999999999"),
        Decimal("1000000000000"),
        Decimal("1E-9"),
        Decimal("1E+12"),
    ],
)
def test_rejects_values_outside_exact_numeric_20_8_capacity(value: Decimal) -> None:
    with pytest.raises(AssetPriceValueError):
        validate_asset_price_value(value)