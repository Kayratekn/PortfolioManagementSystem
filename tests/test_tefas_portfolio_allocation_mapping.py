from src.services.tefas_portfolio_allocation_mapping import (
    EXPECTED_ALLOCATION_FIELDS,
    UNRESOLVED_ALLOCATION_FIELDS,
    VERIFIED_ALLOCATION_LABELS,
    get_allocation_label,
    get_mapping_status,
)


def test_verified_mapping_count_is_43() -> None:
    assert len(VERIFIED_ALLOCATION_LABELS) == 43


def test_unresolved_field_count_is_11() -> None:
    assert len(UNRESOLVED_ALLOCATION_FIELDS) == 11


def test_expected_allocation_field_count_is_54() -> None:
    assert len(EXPECTED_ALLOCATION_FIELDS) == 54


def test_verified_and_unresolved_sets_do_not_overlap() -> None:
    assert set(VERIFIED_ALLOCATION_LABELS).isdisjoint(UNRESOLVED_ALLOCATION_FIELDS)


def test_metadata_fields_are_not_in_expected_allocation_fields() -> None:
    for field_name in ("fonKodu", "fonUnvan", "tarih", "bilFiyat"):
        assert field_name not in EXPECTED_ALLOCATION_FIELDS


def test_known_verified_labels_match_exact_text() -> None:
    assert get_allocation_label("hs") == "Hisse Senedi"
    assert get_allocation_label("gyy") == "Gayrimenkul Yatırımları"
    assert get_allocation_label("vmau") == "Mevduat (Altın)"
    assert get_allocation_label("btaa") == "BİST Taahhütlü İşlem Pazarı Alım"


def test_unresolved_fields_return_no_label() -> None:
    assert get_allocation_label("bb") is None
    assert get_allocation_label("ymk") is None


def test_verified_status_is_verified() -> None:
    assert get_mapping_status("hs") == "VERIFIED"


def test_unresolved_status_is_unresolved() -> None:
    assert get_mapping_status("bb") == "UNRESOLVED"


def test_unknown_field_raises_value_error() -> None:
    try:
        get_mapping_status("fonKodu")
    except ValueError as exc:
        assert "Unknown TEFAS allocation raw field" in str(exc)
    else:
        raise AssertionError("ValueError was not raised for unknown field")
