from decimal import Decimal, localcontext

import pytest

from src.services.borsa_istanbul_reference_price_normalization import (
    BorsaIstanbulReferencePriceNormalizationError,
    normalize_raw_try_per_kg,
)


@pytest.mark.parametrize(
    ("raw_price", "expected"),
    [
        (Decimal("1234567.89000000"), Decimal("1234.56789000")),
        ("123000.000000", Decimal("123.000000")),
        (1, Decimal("0.001")),
    ],
)
def test_normalizes_raw_try_per_kg_to_canonical_try_per_gram_exactly(
    raw_price: object,
    expected: Decimal,
) -> None:
    result = normalize_raw_try_per_kg(raw_price)

    assert result == expected
    assert isinstance(result, Decimal)


@pytest.mark.parametrize("raw_price", [Decimal("0"), Decimal("-0.01"), "NaN", "Infinity", "-Infinity"])
def test_rejects_non_positive_or_non_finite_raw_prices(raw_price: object) -> None:
    with pytest.raises(BorsaIstanbulReferencePriceNormalizationError):
        normalize_raw_try_per_kg(raw_price)


@pytest.mark.parametrize("raw_price", [True, False, 123.45, "", "abc", None])
def test_rejects_bool_float_and_malformed_raw_prices(raw_price: object) -> None:
    with pytest.raises(BorsaIstanbulReferencePriceNormalizationError):
        normalize_raw_try_per_kg(raw_price)


def test_accepts_insignificant_trailing_zeroes_when_canonical_value_is_exactly_storable() -> None:
    assert normalize_raw_try_per_kg(Decimal("123000.000000000")) == Decimal("123.000000000")


def test_rejects_canonical_value_requiring_more_than_eight_decimal_places() -> None:
    with pytest.raises(BorsaIstanbulReferencePriceNormalizationError, match="more than 8 decimal places"):
        normalize_raw_try_per_kg(Decimal("0.000001"))


def test_normalization_is_independent_of_ambient_decimal_context_precision() -> None:
    raw_price = Decimal("123456789012345.67000")
    expected = Decimal("123456789012.34567000")

    with localcontext() as context:
        context.prec = 3
        result = normalize_raw_try_per_kg(raw_price)

    assert result == expected
    assert result.as_tuple() == expected.as_tuple()


def test_previous_context_rounding_blocker_is_rejected_after_exact_conversion() -> None:
    raw_price = Decimal("1000.00000000000000000000000000001")

    with pytest.raises(BorsaIstanbulReferencePriceNormalizationError, match="more than 8 decimal places"):
        normalize_raw_try_per_kg(raw_price)