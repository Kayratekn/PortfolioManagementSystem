from __future__ import annotations

from decimal import Decimal


ASSET_PRICE_SCALE_DIGITS = 8
ASSET_PRICE_INTEGER_DIGITS = 12


class AssetPriceValueError(ValueError):
    pass


def validate_asset_price_value(value: Decimal) -> Decimal:
    if not isinstance(value, Decimal):
        raise AssetPriceValueError("Asset price must be a Decimal.")
    if not value.is_finite() or value <= Decimal("0"):
        raise AssetPriceValueError("Asset price must be finite and greater than zero.")

    decimal_tuple = value.as_tuple()
    digits = list(decimal_tuple.digits)
    exponent = decimal_tuple.exponent

    while exponent < 0 and digits[-1] == 0:
        digits.pop()
        exponent += 1

    fractional_digits = max(0, -exponent)
    integer_digits = max(0, len(digits) + exponent)
    if fractional_digits > ASSET_PRICE_SCALE_DIGITS:
        raise AssetPriceValueError(
            "Asset price requires more than 8 decimal places and cannot be stored exactly."
        )
    if integer_digits > ASSET_PRICE_INTEGER_DIGITS:
        raise AssetPriceValueError(
            "Asset price exceeds NUMERIC(20,8) integer precision."
        )
    return value