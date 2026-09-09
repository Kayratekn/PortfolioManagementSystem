from __future__ import annotations

from decimal import Decimal, DecimalTuple, InvalidOperation
from typing import Any

from src.services.asset_price_value_validation import validate_asset_price_value


RAW_TRY_PER_KG_DIVISOR = Decimal("1000")


class BorsaIstanbulReferencePriceNormalizationError(ValueError):
    pass


def normalize_raw_try_per_kg(raw_value: Any) -> Decimal:
    if isinstance(raw_value, bool) or isinstance(raw_value, float):
        raise BorsaIstanbulReferencePriceNormalizationError(
            "BIST raw TRY/kg price must be Decimal-compatible and not bool or float."
        )
    try:
        raw_price = Decimal(str(raw_value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise BorsaIstanbulReferencePriceNormalizationError(
            "BIST raw TRY/kg price is malformed."
        ) from exc

    if not raw_price.is_finite() or raw_price <= Decimal("0"):
        raise BorsaIstanbulReferencePriceNormalizationError(
            "BIST raw TRY/kg price must be finite and greater than zero."
        )

    raw_tuple = raw_price.as_tuple()
    canonical_price = Decimal(
        DecimalTuple(
            sign=raw_tuple.sign,
            digits=raw_tuple.digits,
            exponent=raw_tuple.exponent - 3,
        )
    )
    try:
        return validate_asset_price_value(canonical_price)
    except ValueError as exc:
        raise BorsaIstanbulReferencePriceNormalizationError(str(exc)) from exc