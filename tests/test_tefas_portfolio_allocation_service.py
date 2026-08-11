from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src.services.tefas_portfolio_allocation_mapping import EXPECTED_ALLOCATION_FIELDS
from src.services.tefas_service import TefasService


def build_raw_row(**overrides: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "fonKodu": " ab1 ",
        "fonUnvan": "Örnek Fon",
        "tarih": "2026-08-11",
        "bilFiyat": 49.24,
    }
    row.update({field_name: None for field_name in EXPECTED_ALLOCATION_FIELDS})
    row.update(overrides)
    return row


def get_service() -> TefasService:
    return TefasService(client=object())  # type: ignore[arg-type]


def test_normalize_portfolio_breakdown_row_normalizes_complete_row() -> None:
    service = get_service()
    row = build_raw_row(hs="80", gyy="20")

    snapshot = service.normalize_portfolio_breakdown_row(row)

    assert snapshot.fund_code == "AB1"
    assert snapshot.fund_name == "Örnek Fon"
    assert snapshot.data_date == date(2026, 8, 11)
    assert isinstance(snapshot.allocations, tuple)
    assert {item.raw_field_name for item in snapshot.allocations} == {"gyy", "hs"}


def test_metadata_fields_do_not_become_allocation_items() -> None:
    service = get_service()
    row = build_raw_row(hs="100")

    snapshot = service.normalize_portfolio_breakdown_row(row)

    assert len(snapshot.allocations) == 1
    assert snapshot.allocations[0].raw_field_name == "hs"


def test_null_allocation_values_are_omitted() -> None:
    service = get_service()
    row = build_raw_row(hs=None, gyy="5")

    snapshot = service.normalize_portfolio_breakdown_row(row)

    assert [item.raw_field_name for item in snapshot.allocations] == ["gyy"]


def test_zero_allocation_is_preserved_as_decimal_zero() -> None:
    service = get_service()
    row = build_raw_row(hs=0)

    snapshot = service.normalize_portfolio_breakdown_row(row)

    assert snapshot.allocations[0].allocation_percentage == Decimal("0")


def test_negative_allocation_is_preserved() -> None:
    service = get_service()
    row = build_raw_row(r="-1.25")

    snapshot = service.normalize_portfolio_breakdown_row(row)

    assert snapshot.allocations[0].raw_field_name == "r"
    assert snapshot.allocations[0].allocation_percentage == Decimal("-1.25")


def test_float_allocation_uses_string_decimal_conversion() -> None:
    service = get_service()
    row = build_raw_row(hs=99.95)

    snapshot = service.normalize_portfolio_breakdown_row(row)

    assert snapshot.allocations[0].allocation_percentage == Decimal("99.95")


def test_verified_field_has_label_and_status() -> None:
    service = get_service()
    row = build_raw_row(hs="10")

    snapshot = service.normalize_portfolio_breakdown_row(row)
    item = snapshot.allocations[0]

    assert item.label == "Hisse Senedi"
    assert item.mapping_status == "VERIFIED"


def test_verified_turkish_label_is_preserved() -> None:
    service = get_service()
    row = build_raw_row(gyy="10")

    snapshot = service.normalize_portfolio_breakdown_row(row)

    assert snapshot.allocations[0].label == "Gayrimenkul Yatırımları"


def test_unresolved_field_has_no_label_and_unresolved_status() -> None:
    service = get_service()
    row = build_raw_row(bb="10")

    snapshot = service.normalize_portfolio_breakdown_row(row)
    item = snapshot.allocations[0]

    assert item.label is None
    assert item.mapping_status == "UNRESOLVED"


def test_missing_one_expected_field_raises_value_error() -> None:
    service = get_service()
    row = build_raw_row()
    row.pop("hs")

    with pytest.raises(ValueError, match="hs"):
        service.normalize_portfolio_breakdown_row(row)


def test_missing_multiple_expected_fields_are_reported() -> None:
    service = get_service()
    row = build_raw_row()
    row.pop("bb")
    row.pop("hs")

    with pytest.raises(ValueError) as exc_info:
        service.normalize_portfolio_breakdown_row(row)

    message = str(exc_info.value)
    assert "bb" in message
    assert "hs" in message


def test_unexpected_field_raises_value_error() -> None:
    service = get_service()
    row = build_raw_row(yeniAlan="1")

    with pytest.raises(ValueError, match="yeniAlan"):
        service.normalize_portfolio_breakdown_row(row)


def test_invalid_non_numeric_allocation_value_raises_value_error() -> None:
    service = get_service()
    row = build_raw_row(hs="not-a-number")

    with pytest.raises(ValueError, match="hs"):
        service.normalize_portfolio_breakdown_row(row)


def test_bool_allocation_value_raises_value_error() -> None:
    service = get_service()
    row = build_raw_row(hs=True)

    with pytest.raises(ValueError, match="bool is not allowed"):
        service.normalize_portfolio_breakdown_row(row)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_allocation_values_are_rejected(value: float) -> None:
    service = get_service()
    row = build_raw_row(hs=value)

    with pytest.raises(ValueError, match="non-finite"):
        service.normalize_portfolio_breakdown_row(row)


def test_input_dictionary_is_not_mutated() -> None:
    service = get_service()
    row = build_raw_row(hs="10", bb="5")
    original_row = dict(row)

    service.normalize_portfolio_breakdown_row(row)

    assert row == original_row
