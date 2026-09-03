from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from src.services.benchmark_price_import_parser import parse_benchmark_price_rows


def test_parser_preserves_exact_decimal_values() -> None:
    observations = parse_benchmark_price_rows(
        [{"date": "2026-09-02", "close": "14050.59960938"}]
    )

    assert observations[0].price_date == date(2026, 9, 2)
    assert observations[0].close_value == Decimal("14050.59960938")
    assert isinstance(observations[0].close_value, Decimal)


@pytest.mark.parametrize("value", ["", "   ", "2026-02-30", "not-a-date", None])
def test_parser_rejects_blank_or_malformed_dates(value: str | None) -> None:
    with pytest.raises(ValueError):
        parse_benchmark_price_rows([{"date": value, "close": "100"}])


@pytest.mark.parametrize("value", ["", "   ", "not-decimal", None])
def test_parser_rejects_blank_or_malformed_close(value: str | None) -> None:
    with pytest.raises(ValueError):
        parse_benchmark_price_rows([{"date": "2026-09-02", "close": value}])


@pytest.mark.parametrize("value", ["0", "0.00000000", "-1", "-123.45", "NaN", "Infinity"])
def test_parser_rejects_zero_negative_or_non_finite_close(value: str) -> None:
    with pytest.raises(ValueError):
        parse_benchmark_price_rows([{"date": "2026-09-02", "close": value}])


def test_parser_rejects_float_close_input() -> None:
    with pytest.raises(ValueError):
        parse_benchmark_price_rows([{"date": "2026-09-02", "close": 14050.59960938}])


@pytest.mark.parametrize("value", ["14050.59960938", "123", "1.230000000"])
def test_parser_accepts_values_representable_at_scale_8_without_rounding(value: str) -> None:
    observations = parse_benchmark_price_rows([{"date": "2026-09-02", "close": value}])

    assert observations[0].close_value == Decimal(value)


def test_parser_rejects_value_requiring_scale_8_rounding() -> None:
    with pytest.raises(ValueError):
        parse_benchmark_price_rows([{"date": "2026-09-02", "close": "14050.599609375"}])


def test_parser_rejects_conflicting_duplicate_dates() -> None:
    with pytest.raises(ValueError):
        parse_benchmark_price_rows(
            [
                {"date": "2026-09-02", "close": "100"},
                {"date": "2026-09-02", "close": "101"},
            ]
        )


def test_parser_deduplicates_identical_duplicate_dates_deterministically() -> None:
    observations = parse_benchmark_price_rows(
        [
            {"date": "2026-09-03", "close": "103"},
            {"date": "2026-09-02", "close": "102"},
            {"date": "2026-09-02", "close": "102.00"},
        ]
    )

    assert [(item.price_date, item.close_value) for item in observations] == [
        (date(2026, 9, 2), Decimal("102")),
        (date(2026, 9, 3), Decimal("103")),
    ]


def test_parser_does_not_fabricate_missing_dates() -> None:
    observations = parse_benchmark_price_rows(
        [
            {"date": "2026-09-01", "close": "101"},
            {"date": "2026-09-04", "close": "104"},
        ]
    )

    assert [item.price_date for item in observations] == [date(2026, 9, 1), date(2026, 9, 4)]