from datetime import date
from decimal import Decimal
import json
from typing import Any

import pytest

from src.services.tefas_service import TefasService, TefasServiceError


class FakeTefasClient:
    """Returns a predefined response without making an HTTP request."""

    def __init__(
        self,
        response: dict[str, Any],
        portfolio_response: dict[str, Any] | None = None,
        profile_response: dict[str, Any] | None = None,
        detail_page_html: str = "",
    ) -> None:
        self.response = response
        self.portfolio_response = portfolio_response if portfolio_response is not None else response
        self.profile_response = profile_response if profile_response is not None else response
        self.detail_page_html = detail_page_html
        self.profile_detail_calls: list[dict[str, Any]] = []
        self.detail_page_calls: list[dict[str, Any]] = []

    def fetch_general_info(self, **kwargs: Any) -> dict[str, Any]:
        return self.response

    def fetch_portfolio_breakdown(self, **kwargs: Any) -> dict[str, Any]:
        return self.portfolio_response

    def fetch_fund_profile_detail(self, **kwargs: Any) -> dict[str, Any]:
        self.profile_detail_calls.append(kwargs)
        return self.profile_response

    def fetch_fund_detail_analysis_page(self, **kwargs: Any) -> str:
        self.detail_page_calls.append(kwargs)
        return self.detail_page_html



class ChunkedFakeTefasClient:
    """Returns one predefined response per general-info request."""

    def __init__(self, responses: list[dict[str, Any] | Exception]) -> None:
        self.responses = list(responses)
        self.general_info_calls: list[dict[str, Any]] = []

    def fetch_general_info(self, **kwargs: Any) -> dict[str, Any]:
        self.general_info_calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def fetch_portfolio_breakdown(self, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("portfolio breakdown was not expected")

def test_fetch_general_info_normalizes_tefas_fields() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {
                    "fonKodu": " aal ",
                    "fonUnvan": " ATA PORTFÃ–Y PARA PÄ°YASASI (TL) FONU ",
                    "tarih": "2026-04-24",
                    "fiyat": 3.163587,
                    "tedPaySayisi": 960084201,
                    "kisiSayisi": 4845,
                    "portfoyBuyukluk": 3037309510.91,
                    "borsaBultenFiyat": None,
                    "rn": 1,
                }
            ],
        }
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
        fund_kind="YAT",
        fund_code="AAL",
    )

    assert result == [
        {
            "fund_code": "AAL",
            "fund_name": "ATA PORTFÃ–Y PARA PÄ°YASASI (TL) FONU",
            "fund_kind": "YAT",
            "data_date": date(2026, 4, 24),
            "price": Decimal("3.163587"),
            "shares_outstanding": Decimal("960084201"),
            "investor_count": 4845,
            "portfolio_size": Decimal("3037309510.91"),
            "exchange_bulletin_price": None,
        }
    ]
    normalized_row = result[0]
    assert isinstance(normalized_row["fund_code"], str)
    assert isinstance(normalized_row["fund_name"], str)
    assert isinstance(normalized_row["fund_kind"], str)
    assert isinstance(normalized_row["data_date"], date)
    assert isinstance(normalized_row["price"], Decimal)
    assert isinstance(normalized_row["shares_outstanding"], Decimal)
    assert isinstance(normalized_row["investor_count"], int)
    assert isinstance(normalized_row["portfolio_size"], Decimal)
    assert normalized_row["exchange_bulletin_price"] is None


def test_fetch_general_info_preserves_null_optional_fields() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {
                    "fonKodu": "AAL",
                    "fonUnvan": "Example Fund",
                    "tarih": "2026-04-24",
                    "fiyat": 3.163587,
                    "tedPaySayisi": None,
                    "kisiSayisi": None,
                    "portfoyBuyukluk": None,
                    "borsaBultenFiyat": None,
                }
            ],
        }
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    assert result[0]["shares_outstanding"] is None
    assert result[0]["investor_count"] is None
    assert result[0]["portfolio_size"] is None
    assert result[0]["exchange_bulletin_price"] is None


@pytest.mark.parametrize(
    ("fund_kind", "raw_investor_count", "expected_investor_count"),
    [
        ("BYF", 0, None),
        ("BYF", None, None),
        ("BYF", 12, 12),
        ("YAT", 0, 0),
        ("EMK", 0, 0),
        ("GYF", 0, 0),
        ("GSYF", 0, 0),
        ("YAT", 4845, 4845),
    ],
)
def test_fetch_general_info_normalizes_byf_zero_investor_count_as_unavailable(
    fund_kind: str,
    raw_investor_count: object,
    expected_investor_count: int | None,
) -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {
                    "fonKodu": "BLH",
                    "fonUnvan": "Example Fund",
                    "tarih": "2026-08-11",
                    "fiyat": 49.222014,
                    "tedPaySayisi": 1000,
                    "kisiSayisi": raw_investor_count,
                    "portfoyBuyukluk": 12345,
                    "borsaBultenFiyat": 49.24,
                }
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind=fund_kind,  # type: ignore[arg-type]
        fund_code="BLH",
    )

    assert result[0]["investor_count"] == expected_investor_count
    assert result[0]["price"] == Decimal("49.222014")
    assert result[0]["shares_outstanding"] == Decimal("1000")
    assert result[0]["portfolio_size"] == Decimal("12345")
    assert result[0]["exchange_bulletin_price"] == Decimal("49.24")


def test_fetch_general_info_invalid_iso_date_raises_service_error() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {
                    "fonKodu": "AAL",
                    "fonUnvan": "Example Fund",
                    "tarih": "2026-04-31",
                    "fiyat": 3.163587,
                }
            ],
        }
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(TefasServiceError, match="data_date"):
        service.fetch_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )


@pytest.mark.parametrize(
    "row",
    [
        {
            "fonKodu": "AAL",
            "fonUnvan": "Example Fund",
            "tarih": "2026-04-24",
        },
        {
            "fonKodu": "AAL",
            "fonUnvan": "Example Fund",
            "tarih": "2026-04-24",
            "fiyat": None,
        },
    ],
)
def test_fetch_general_info_missing_or_null_price_raises_service_error(row: dict[str, Any]) -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [row],
        }
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(TefasServiceError, match="price"):
        service.fetch_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )




def _build_general_info_row(
    *,
    fund_code: str,
    fund_name: str = "Example Fund",
    data_date: str = "2026-08-11",
    price: object = "1.23",
) -> dict[str, object]:
    return {
        "fonKodu": fund_code,
        "fonUnvan": fund_name,
        "tarih": data_date,
        "fiyat": price,
        "tedPaySayisi": 1000,
        "kisiSayisi": 100,
        "portfoyBuyukluk": 12345,
        "borsaBultenFiyat": None,
    }


def test_fetch_general_info_filters_requested_fund_code_locally() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                _build_general_info_row(fund_code="AB1", fund_name="Fund AB1"),
                _build_general_info_row(fund_code="AB2", fund_name="Fund AB2"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [row["fund_code"] for row in result] == ["AB1"]
    assert result[0]["fund_name"] == "Fund AB1"


def test_fetch_general_info_filters_requested_fund_code_case_insensitively() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                _build_general_info_row(fund_code="AB1", fund_name="Fund AB1"),
                _build_general_info_row(fund_code="AB2", fund_name="Fund AB2"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="ab1",
    )

    assert [row["fund_code"] for row in result] == ["AB1"]


def test_fetch_general_info_filters_requested_fund_code_with_surrounding_whitespace() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                _build_general_info_row(fund_code="AB1", fund_name="Fund AB1"),
                _build_general_info_row(fund_code="AB2", fund_name="Fund AB2"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code=" AB1 ",
    )

    assert [row["fund_code"] for row in result] == ["AB1"]


def test_fetch_general_info_returns_empty_when_requested_fund_code_absent() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                _build_general_info_row(fund_code="AB2", fund_name="Fund AB2"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert result == []


def test_fetch_general_info_preserves_multiple_returned_funds_without_fund_code() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                _build_general_info_row(fund_code="AB1", fund_name="Fund AB1"),
                _build_general_info_row(fund_code="AB2", fund_name="Fund AB2"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code=None,
    )

    assert [row["fund_code"] for row in result] == ["AB1", "AB2"]


def test_fetch_general_info_preserves_historical_multi_date_rows_for_requested_fund() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                _build_general_info_row(fund_code="AB1", data_date="2026-07-01"),
                _build_general_info_row(fund_code="AB1", data_date="2026-07-02"),
                _build_general_info_row(fund_code="AB1", data_date="2026-07-03"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 3),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [row["fund_code"] for row in result] == ["AB1", "AB1", "AB1"]
    assert [row["data_date"] for row in result] == [
        date(2026, 7, 1),
        date(2026, 7, 2),
        date(2026, 7, 3),
    ]


def test_fetch_general_info_filters_mixed_historical_response_to_requested_fund() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                _build_general_info_row(fund_code="AB1", data_date="2026-07-01"),
                _build_general_info_row(fund_code="AB2", data_date="2026-07-01"),
                _build_general_info_row(fund_code="AB1", data_date="2026-07-02"),
                _build_general_info_row(fund_code="AB2", data_date="2026-07-02"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [row["fund_code"] for row in result] == ["AB1", "AB1"]
    assert [row["data_date"] for row in result] == [date(2026, 7, 1), date(2026, 7, 2)]


def test_fetch_general_info_filtering_preserves_existing_normalization_semantics() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {
                    "fonKodu": " ab1 ",
                    "fonUnvan": " Example Fund ",
                    "tarih": "2026-08-11",
                    "fiyat": "3.50",
                    "tedPaySayisi": "1000.25",
                    "kisiSayisi": "12",
                    "portfoyBuyukluk": "3500.75",
                    "borsaBultenFiyat": None,
                },
                _build_general_info_row(fund_code="AB2", fund_name="Fund AB2"),
            ],
        }
    )
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert result == [
        {
            "fund_code": "AB1",
            "fund_name": "Example Fund",
            "fund_kind": "GYF",
            "data_date": date(2026, 8, 11),
            "price": Decimal("3.50"),
            "shares_outstanding": Decimal("1000.25"),
            "investor_count": 12,
            "portfolio_size": Decimal("3500.75"),
            "exchange_bulletin_price": None,
        }
    ]

def test_fetch_portfolio_breakdown_raw_filters_requested_fund_code() -> None:
    fake_client = FakeTefasClient(
        response={"errorCode": None, "errorMessage": None, "resultList": []},
        portfolio_response={
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {"fonKodu": "AB1", "fonUnvan": "Fund 1"},
                {"fonKodu": "AB2", "fonUnvan": "Fund 2"},
            ],
        },
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_portfolio_breakdown_raw(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert result == [{"fonKodu": "AB1", "fonUnvan": "Fund 1"}]


def test_fetch_portfolio_breakdown_raw_filters_case_insensitively() -> None:
    fake_client = FakeTefasClient(
        response={"errorCode": None, "errorMessage": None, "resultList": []},
        portfolio_response={
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {"fonKodu": "ab1", "fonUnvan": "Fund 1"},
                {"fonKodu": "AB2", "fonUnvan": "Fund 2"},
            ],
        },
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_portfolio_breakdown_raw(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert result == [{"fonKodu": "ab1", "fonUnvan": "Fund 1"}]


def test_fetch_portfolio_breakdown_raw_handles_surrounding_whitespace_in_requested_code() -> None:
    fake_client = FakeTefasClient(
        response={"errorCode": None, "errorMessage": None, "resultList": []},
        portfolio_response={
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {"fonKodu": " AB1 ", "fonUnvan": "Fund 1"},
                {"fonKodu": "AB2", "fonUnvan": "Fund 2"},
            ],
        },
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_portfolio_breakdown_raw(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="  ab1  ",
    )

    assert result == [{"fonKodu": " AB1 ", "fonUnvan": "Fund 1"}]


def test_fetch_portfolio_breakdown_raw_preserves_all_rows_without_fund_code() -> None:
    rows = [
        {"fonKodu": "AB1", "fonUnvan": "Fund 1"},
        {"fonKodu": "AB2", "fonUnvan": "Fund 2"},
    ]
    fake_client = FakeTefasClient(
        response={"errorCode": None, "errorMessage": None, "resultList": []},
        portfolio_response={
            "errorCode": None,
            "errorMessage": None,
            "resultList": rows,
        },
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_portfolio_breakdown_raw(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code=None,
    )

    assert result == rows


def test_fetch_portfolio_breakdown_raw_returns_empty_when_requested_code_absent() -> None:
    fake_client = FakeTefasClient(
        response={"errorCode": None, "errorMessage": None, "resultList": []},
        portfolio_response={
            "errorCode": None,
            "errorMessage": None,
            "resultList": [
                {"fonKodu": "AB2", "fonUnvan": "Fund 2"},
            ],
        },
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_portfolio_breakdown_raw(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert result == []


def test_out_of_bounds_response_returns_empty_list() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": None,
            "errorMessage": "Index 0 out of bounds for length 0",
            "resultList": None,
        }
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 30),
        end_date=date(2026, 7, 30),
    )

    assert result == []


def test_tefas_application_error_raises_service_error() -> None:
    fake_client = FakeTefasClient(
        {
            "errorCode": "500",
            "errorMessage": "Unexpected TEFAS error",
            "resultList": None,
        }
    )

    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(
        TefasServiceError,
        match="Unexpected TEFAS error",
    ):
        service.fetch_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )



def _success_response(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "errorCode": None,
        "errorMessage": None,
        "resultList": rows,
    }


def test_fetch_general_info_splits_six_week_range_into_two_provider_safe_chunks() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-07-01")]),
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-08-11")]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [(call["start_date"], call["end_date"]) for call in fake_client.general_info_calls] == [
        (date(2026, 7, 1), date(2026, 7, 28)),
        (date(2026, 7, 29), date(2026, 8, 11)),
    ]
    assert [row["data_date"] for row in result] == [date(2026, 7, 1), date(2026, 8, 11)]


def test_fetch_general_info_uses_one_client_call_for_28_day_inclusive_range() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-07-28")]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 28),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [(call["start_date"], call["end_date"]) for call in fake_client.general_info_calls] == [
        (date(2026, 7, 1), date(2026, 7, 28)),
    ]


def test_fetch_general_info_splits_29_day_inclusive_range_into_two_calls() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-07-28")]),
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-07-29")]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 29),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [(call["start_date"], call["end_date"]) for call in fake_client.general_info_calls] == [
        (date(2026, 7, 1), date(2026, 7, 28)),
        (date(2026, 7, 29), date(2026, 7, 29)),
    ]


def test_fetch_general_info_uses_one_client_call_for_one_day_request() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-08-11")]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    service.fetch_general_info(
        start_date=date(2026, 8, 11),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [(call["start_date"], call["end_date"]) for call in fake_client.general_info_calls] == [
        (date(2026, 8, 11), date(2026, 8, 11)),
    ]


def test_fetch_general_info_chunks_have_no_gaps_or_overlaps() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([]),
        _success_response([]),
        _success_response([]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 30),
        fund_kind="GYF",
        fund_code="AB1",
    )

    ranges = [(call["start_date"], call["end_date"]) for call in fake_client.general_info_calls]
    assert ranges == [
        (date(2026, 7, 1), date(2026, 7, 28)),
        (date(2026, 7, 29), date(2026, 8, 25)),
        (date(2026, 8, 26), date(2026, 8, 30)),
    ]
    assert all(ranges[index][1].toordinal() + 1 == ranges[index + 1][0].toordinal() for index in range(len(ranges) - 1))


def test_fetch_general_info_combines_rows_from_all_chunks() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-07-01")]),
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-08-11")]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [row["data_date"] for row in result] == [date(2026, 7, 1), date(2026, 8, 11)]


def test_fetch_general_info_combined_result_is_chronological() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([
            _build_general_info_row(fund_code="AB1", data_date="2026-07-03"),
            _build_general_info_row(fund_code="AB1", data_date="2026-07-01"),
        ]),
        _success_response([
            _build_general_info_row(fund_code="AB1", data_date="2026-08-11"),
            _build_general_info_row(fund_code="AB1", data_date="2026-07-29"),
        ]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [row["data_date"] for row in result] == [
        date(2026, 7, 1),
        date(2026, 7, 3),
        date(2026, 7, 29),
        date(2026, 8, 11),
    ]


def test_fetch_general_info_filters_requested_fund_code_across_all_chunks() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([
            _build_general_info_row(fund_code="AB1", data_date="2026-07-01"),
            _build_general_info_row(fund_code="AB2", data_date="2026-07-01"),
        ]),
        _success_response([
            _build_general_info_row(fund_code="AB1", data_date="2026-08-11"),
            _build_general_info_row(fund_code="AB2", data_date="2026-08-11"),
        ]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [row["fund_code"] for row in result] == ["AB1", "AB1"]
    assert [row["data_date"] for row in result] == [date(2026, 7, 1), date(2026, 8, 11)]


def test_fetch_general_info_returns_empty_when_requested_fund_absent_across_all_chunks() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([_build_general_info_row(fund_code="AB2", data_date="2026-07-01")]),
        _success_response([_build_general_info_row(fund_code="AB2", data_date="2026-08-11")]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 8, 11),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert result == []


def test_fetch_general_info_second_chunk_failure_propagates_without_partial_result() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([_build_general_info_row(fund_code="AB1", data_date="2026-07-01")]),
        TefasServiceError("second chunk failed"),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(TefasServiceError, match="second chunk failed"):
        service.fetch_general_info(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 8, 11),
            fund_kind="GYF",
            fund_code="AB1",
        )

    assert [(call["start_date"], call["end_date"]) for call in fake_client.general_info_calls] == [
        (date(2026, 7, 1), date(2026, 7, 28)),
        (date(2026, 7, 29), date(2026, 8, 11)),
    ]


def test_fetch_general_info_deduplicates_identical_provider_rows() -> None:
    duplicate_row = _build_general_info_row(fund_code="AB1", data_date="2026-07-01")
    fake_client = ChunkedFakeTefasClient([
        _success_response([duplicate_row, dict(duplicate_row)]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    result = service.fetch_general_info(
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 1),
        fund_kind="GYF",
        fund_code="AB1",
    )

    assert [row["data_date"] for row in result] == [date(2026, 7, 1)]


def test_fetch_general_info_rejects_conflicting_duplicate_provider_rows() -> None:
    fake_client = ChunkedFakeTefasClient([
        _success_response([
            _build_general_info_row(fund_code="AB1", data_date="2026-07-01", price="1.23"),
            _build_general_info_row(fund_code="AB1", data_date="2026-07-01", price="1.24"),
        ]),
    ])
    service = TefasService(client=fake_client)  # type: ignore[arg-type]

    with pytest.raises(TefasServiceError, match="Conflicting duplicate"):
        service.fetch_general_info(
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
            fund_kind="GYF",
            fund_code="AB1",
        )


def _build_profile_row(
    *,
    fund_code: str,
    fund_type_name: object = "Para Piyasasi Semsiye Fonu",
) -> dict[str, object]:
    return {
        "fonKodu": fund_code,
        "fonUnvan": f"{fund_code} Fund",
        "fonTuru": fund_type_name,
        "fonTurGetiri": "0.1",
    }


def _profile_response(rows: list[dict[str, object]]) -> dict[str, object]:
    return {
        "errorCode": None,
        "errorMessage": None,
        "resultList": rows,
    }


def _service_with_profile_rows(rows: list[dict[str, object]]) -> tuple[TefasService, FakeTefasClient]:
    fake_client = FakeTefasClient(
        response={"errorCode": None, "errorMessage": None, "resultList": []},
        profile_response=_profile_response(rows),
    )
    return TefasService(client=fake_client), fake_client  # type: ignore[arg-type]


def test_get_fund_type_selects_aal_style_requested_row() -> None:
    service, fake_client = _service_with_profile_rows([
        _build_profile_row(fund_code="ALTIN", fund_type_name="ALTIN"),
        _build_profile_row(fund_code="AAL", fund_type_name="Para Piyasasi Semsiye Fonu"),
    ])

    result = service.get_fund_type(fund_code="AAL")

    assert result.fund_code == "AAL"
    assert result.fund_type_name == "Para Piyasasi Semsiye Fonu"
    assert result.raw_field_name == "fonTuru"
    assert result.source_endpoint == "fonProfilDtyGetir"
    assert fake_client.profile_detail_calls == [{"fund_code": "AAL"}]


def test_get_fund_type_selects_blh_style_requested_row() -> None:
    service, _ = _service_with_profile_rows([
        _build_profile_row(fund_code="BLH", fund_type_name="Hisse Senedi Yogun"),
        _build_profile_row(fund_code="BIST100", fund_type_name="BIST100"),
    ])

    result = service.get_fund_type(fund_code="BLH")

    assert result.fund_code == "BLH"
    assert result.fund_type_name == "Hisse Senedi Yogun"


def test_get_fund_type_selects_ab1_style_requested_row() -> None:
    service, _ = _service_with_profile_rows([
        _build_profile_row(fund_code="AB1", fund_type_name="Gayrimenkul Yatirim Fonlari"),
        _build_profile_row(fund_code="EUR", fund_type_name="EUR"),
    ])

    result = service.get_fund_type(fund_code="AB1")

    assert result.fund_code == "AB1"
    assert result.fund_type_name == "Gayrimenkul Yatirim Fonlari"


def test_get_fund_type_ignores_comparator_rows_before_and_after_requested_row() -> None:
    service, _ = _service_with_profile_rows([
        _build_profile_row(fund_code="ALTIN", fund_type_name="ALTIN"),
        _build_profile_row(fund_code="BIST100", fund_type_name="BIST100"),
        _build_profile_row(fund_code="BLH", fund_type_name="Hisse Senedi Yogun"),
        _build_profile_row(fund_code="EUR", fund_type_name="EUR"),
    ])

    result = service.get_fund_type(fund_code="BLH")

    assert result.fund_code == "BLH"
    assert result.fund_type_name == "Hisse Senedi Yogun"


def test_get_fund_type_matches_requested_code_case_insensitively_with_whitespace() -> None:
    service, fake_client = _service_with_profile_rows([
        _build_profile_row(fund_code=" aal ", fund_type_name=" Para Piyasasi Semsiye Fonu "),
    ])

    result = service.get_fund_type(fund_code=" aal ")

    assert result.fund_code == "AAL"
    assert result.fund_type_name == "Para Piyasasi Semsiye Fonu"
    assert fake_client.profile_detail_calls == [{"fund_code": "AAL"}]


def test_get_fund_type_raises_when_requested_row_is_absent() -> None:
    service, _ = _service_with_profile_rows([
        _build_profile_row(fund_code="ALTIN", fund_type_name="ALTIN"),
    ])

    with pytest.raises(TefasServiceError, match="not found"):
        service.get_fund_type(fund_code="AAL")


def test_get_fund_type_raises_on_duplicate_requested_rows() -> None:
    service, _ = _service_with_profile_rows([
        _build_profile_row(fund_code="AAL", fund_type_name="Para Piyasasi Semsiye Fonu"),
        _build_profile_row(fund_code=" aal ", fund_type_name="Para Piyasasi Semsiye Fonu"),
    ])

    with pytest.raises(TefasServiceError, match="Duplicate"):
        service.get_fund_type(fund_code="AAL")


@pytest.mark.parametrize(
    "row",
    [
        {"fonKodu": "AAL", "fonUnvan": "AAL Fund"},
        _build_profile_row(fund_code="AAL", fund_type_name=None),
        _build_profile_row(fund_code="AAL", fund_type_name=""),
        _build_profile_row(fund_code="AAL", fund_type_name="   "),
        _build_profile_row(fund_code="AAL", fund_type_name=123),
    ],
)
def test_get_fund_type_raises_on_invalid_fon_turu(row: dict[str, object]) -> None:
    service, _ = _service_with_profile_rows([row])

    with pytest.raises(TefasServiceError, match="fund_type_name"):
        service.get_fund_type(fund_code="AAL")


def test_get_fund_type_uses_only_mocked_client_without_database_or_network() -> None:
    service, fake_client = _service_with_profile_rows([
        _build_profile_row(fund_code="AAL", fund_type_name="Para Piyasasi Semsiye Fonu"),
    ])

    result = service.get_fund_type(fund_code="AAL")

    assert result.fund_type_name == "Para Piyasasi Semsiye Fonu"
    assert fake_client.profile_detail_calls == [{"fund_code": "AAL"}]

def _detail_page_html(bilgi_data_json: str) -> str:
    return _detail_page_html_with_bilgi_data(bilgi_data_json)


def _detail_page_html_with_bilgi_data(*bilgi_data_json_values: str) -> str:
    scripts = "".join(
        f'<script>{{"props":{{"pageProps":{{"bilgiData":{bilgi_data_json}}}}}}}</script>'
        for bilgi_data_json in bilgi_data_json_values
    )
    return f"<html><head></head><body>{scripts}</body></html>"


def _detail_page_next_f_html(*payload_texts: str) -> str:
    scripts = "".join(
        f"<script>self.__next_f.push([1,{json.dumps(payload_text)}]);</script>"
        for payload_text in payload_texts
    )
    return f"<html><head></head><body>{scripts}</body></html>"


def _next_f_payload_with_bilgi_data(bilgi_data_json: str) -> str:
    return f'0:["$","$L1",null,{{"bilgiData":{bilgi_data_json}}}]'


def _service_with_detail_page_html(html_text: str) -> tuple[TefasService, FakeTefasClient]:
    fake_client = FakeTefasClient(
        response={"errorCode": None, "errorMessage": None, "resultList": []},
        detail_page_html=html_text,
    )
    return TefasService(client=fake_client), fake_client  # type: ignore[arg-type]


def test_get_fund_detail_page_metadata_parses_aal_bilgi_data() -> None:
    service, fake_client = _service_with_detail_page_html(
        _detail_page_html(
            '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11}'
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code=" aal ")

    assert result.fund_code == "AAL"
    assert result.fund_category == "Para Piyasas? Fonu"
    assert result.category_rank == 71
    assert result.category_fund_count == 84
    assert result.market_share_raw == Decimal("0.11")
    assert result.risk_value is None
    assert result.source_page == "fon-detayli-analiz"
    assert result.source_field_names == (
        "fonKodu",
        "fonKategori",
        "kategoriDerece",
        "kategoriFonSay",
        "pazarPayi",
        "riskDegeri",
    )
    assert fake_client.detail_page_calls == [{"fund_code": "AAL"}]


def test_get_fund_detail_page_metadata_parses_matching_profil_data_risk_value() -> None:
    service, _ = _service_with_detail_page_html(
        "<html><script>"
        '{"props":{"pageProps":{'
        '"bilgiData":{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
        '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11},'
        '"profilData":{"fonKodu":"AAL","riskDegeri":"1"}'
        "}}}"
        "</script></html>"
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.risk_value == 1


def test_get_fund_detail_page_metadata_ignores_next_reference_profil_data_string() -> None:
    service, _ = _service_with_detail_page_html(
        "<html><script>"
        '{"props":{"pageProps":{'
        '"bilgiData":{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
        '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11},'
        '"profilData":{"fonKodu":"AAL","isinKodu":"TRMAALWWWWW5","riskDegeri":1}'
        "}}}"
        "</script>"
        "<script>"
        '{"props":{"pageProps":{'
        '"profilData":"$3d:props:children:0:props:children:props:profilData"'
        "}}}"
        "</script></html>"
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.risk_value == 1

def test_get_fund_detail_page_metadata_ignores_unidentified_profil_data() -> None:
    service, _ = _service_with_detail_page_html(
        "<html><script>"
        '{"props":{"pageProps":{'
        '"bilgiData":{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
        '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11},'
        '"profilData":{"riskDegeri":"3"}'
        "}}}"
        "</script></html>"
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.risk_value is None

def test_get_fund_detail_page_metadata_parses_ba1_bilgi_data() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_html(
            '{"fonKodu":"BA1","fonKategori":"Serbest Fon",'
            '"kategoriDerece":0,"kategoriFonSay":1340,"pazarPayi":0.01}'
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code="BA1")

    assert result.fund_code == "BA1"
    assert result.fund_category == "Serbest Fon"
    assert result.category_rank == 0
    assert result.category_fund_count == 1340
    assert result.market_share_raw == Decimal("0.01")


def test_get_fund_detail_page_metadata_parses_escaped_next_f_payload() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_next_f_html(
            _next_f_payload_with_bilgi_data(
                '{"fonKodu":"AAL","fonKategori":"Para Piyasas\u0131 Fonu",'
                '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.1100}'
            )
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.fund_code == "AAL"
    assert result.fund_category == "Para Piyasas\u0131 Fonu"
    assert result.category_rank == 71
    assert result.category_fund_count == 84
    assert result.market_share_raw == Decimal("0.1100")


def test_get_fund_detail_page_metadata_selects_exact_matching_profil_data() -> None:
    service, _ = _service_with_detail_page_html(
        "<html><script>"
        '{"props":{"pageProps":{'
        '"bilgiData":{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
        '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11},'
        '"profilData":{"fonKodu":"BA1","riskDegeri":"7"}'
        "}}}"
        "</script>"
        "<script>"
        '{"props":{"pageProps":{'
        '"profilData":{"fonKodu":"AAL","riskDegeri":"2"}'
        "}}}"
        "</script></html>"
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.risk_value == 2


def test_get_fund_detail_page_metadata_selects_exact_matching_bilgi_data() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_html_with_bilgi_data(
            '{"fonKodu":"BA1","fonKategori":"Serbest Fon",'
            '"kategoriDerece":0,"kategoriFonSay":1340,"pazarPayi":0.01}',
            '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11}',
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.fund_code == "AAL"
    assert result.fund_category == "Para Piyasas? Fonu"
    assert result.category_rank == 71
    assert result.category_fund_count == 84
    assert result.market_share_raw == Decimal("0.11")


def test_get_fund_detail_page_metadata_raises_when_no_exact_bilgi_data_match() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_html_with_bilgi_data(
            '{"fonKodu":"BA1","fonKategori":"Serbest Fon",'
            '"kategoriDerece":0,"kategoriFonSay":1340,"pazarPayi":0.01}',
            '{"fonKodu":"BIST100","fonKategori":"Comparator",'
            '"kategoriDerece":1,"kategoriFonSay":10,"pazarPayi":1.25}',
        )
    )

    with pytest.raises(TefasServiceError, match="exact match not found"):
        service.get_fund_detail_page_metadata(fund_code="AAL")


def test_get_fund_detail_page_metadata_accepts_identical_duplicate_exact_matches() -> None:
    bilgi_data_json = (
        '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
        '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11}'
    )
    service, _ = _service_with_detail_page_html(
        _detail_page_next_f_html(
            _next_f_payload_with_bilgi_data(bilgi_data_json),
            _next_f_payload_with_bilgi_data(bilgi_data_json),
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.fund_code == "AAL"
    assert result.category_rank == 71
    assert result.market_share_raw == Decimal("0.11")


def test_get_fund_detail_page_metadata_raises_on_conflicting_duplicate_exact_matches() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_next_f_html(
            _next_f_payload_with_bilgi_data(
                '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
                '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11}'
            ),
            _next_f_payload_with_bilgi_data(
                '{"fonKodu":" aal ","fonKategori":"Para Piyasas? Fonu",'
                '"kategoriDerece":72,"kategoriFonSay":84,"pazarPayi":0.12}'
            ),
        )
    )

    with pytest.raises(TefasServiceError, match="Conflicting"):
        service.get_fund_detail_page_metadata(fund_code="AAL")


def test_get_fund_detail_page_metadata_raises_when_next_f_payload_has_no_exact_match() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_next_f_html(
            _next_f_payload_with_bilgi_data(
                '{"fonKodu":"BA1","fonKategori":"Serbest Fon",'
                '"kategoriDerece":0,"kategoriFonSay":1340,"pazarPayi":0.01}'
            )
        )
    )

    with pytest.raises(TefasServiceError, match="exact match not found"):
        service.get_fund_detail_page_metadata(fund_code="AAL")


def test_get_fund_detail_page_metadata_parses_next_f_profil_data() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_next_f_html(
            '0:["$","$L1",null,{"bilgiData":{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11},'
            '"profilData":{"fonKodu":"AAL","riskDegeri":7}}]'
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.risk_value == 7


def test_get_fund_detail_page_metadata_preserves_raw_market_share_scale() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_html(
            '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.1100}'
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.market_share_raw == Decimal("0.1100")


def test_get_fund_detail_page_metadata_allows_null_optional_numeric_fields() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_html(
            '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":null,"kategoriFonSay":null,"pazarPayi":null}'
        )
    )

    result = service.get_fund_detail_page_metadata(fund_code="AAL")

    assert result.category_rank is None
    assert result.category_fund_count is None
    assert result.market_share_raw is None


def test_get_fund_detail_page_metadata_allows_null_or_missing_risk_value() -> None:
    for profil_data_json in [
        '{"fonKodu":"AAL","riskDegeri":null}',
        '{"fonKodu":"AAL"}',
    ]:
        service, _ = _service_with_detail_page_html(
            "<html><script>"
            '{"props":{"pageProps":{'
            '"bilgiData":{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11},'
            f'"profilData":{profil_data_json}'
            "}}}"
            "</script></html>"
        )

        result = service.get_fund_detail_page_metadata(fund_code="AAL")

        assert result.risk_value is None


@pytest.mark.parametrize("risk_value", ["bad", "1.5", "0", "8", True])
def test_get_fund_detail_page_metadata_rejects_invalid_risk_value(risk_value: object) -> None:
    service, _ = _service_with_detail_page_html(
        "<html><script>"
        '{"props":{"pageProps":{'
        '"bilgiData":{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
        '"kategoriDerece":71,"kategoriFonSay":84,"pazarPayi":0.11},'
        f'"profilData":{{"fonKodu":"AAL","riskDegeri":{json.dumps(risk_value)}}}'
        "}}}"
        "</script></html>"
    )

    with pytest.raises(TefasServiceError, match="risk_value"):
        service.get_fund_detail_page_metadata(fund_code="AAL")


def test_get_fund_detail_page_metadata_raises_when_bilgi_data_missing() -> None:
    service, _ = _service_with_detail_page_html("<html><script>{}</script></html>")

    with pytest.raises(TefasServiceError, match="bilgiData not found"):
        service.get_fund_detail_page_metadata(fund_code="AAL")


@pytest.mark.parametrize(
    "bilgi_data_json",
    [
        '{"fonKategori":"Para Piyasas? Fonu","kategoriDerece":71}',
        '{"fonKodu":"AAL","kategoriDerece":71}',
        '{"fonKodu":"AAL","fonKategori":"   ","kategoriDerece":71}',
    ],
)
def test_get_fund_detail_page_metadata_requires_identity_and_category(
    bilgi_data_json: str,
) -> None:
    service, _ = _service_with_detail_page_html(_detail_page_html(bilgi_data_json))

    with pytest.raises(TefasServiceError):
        service.get_fund_detail_page_metadata(fund_code="AAL")


def test_get_fund_detail_page_metadata_rejects_invalid_optional_numeric_fields() -> None:
    service, _ = _service_with_detail_page_html(
        _detail_page_html(
            '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":"bad","kategoriFonSay":84,"pazarPayi":0.11}'
        )
    )

    with pytest.raises(TefasServiceError, match="category_rank"):
        service.get_fund_detail_page_metadata(fund_code="AAL")


@pytest.mark.parametrize(
    ("field_name", "bilgi_data_json"),
    [
        (
            "category_rank",
            '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":71.5,"kategoriFonSay":84,"pazarPayi":0.11}',
        ),
        (
            "category_fund_count",
            '{"fonKodu":"AAL","fonKategori":"Para Piyasas? Fonu",'
            '"kategoriDerece":71,"kategoriFonSay":84.5,"pazarPayi":0.11}',
        ),
    ],
)
def test_get_fund_detail_page_metadata_rejects_non_integral_category_fields(
    field_name: str,
    bilgi_data_json: str,
) -> None:
    service, _ = _service_with_detail_page_html(_detail_page_html(bilgi_data_json))

    with pytest.raises(TefasServiceError, match=field_name):
        service.get_fund_detail_page_metadata(fund_code="AAL")
