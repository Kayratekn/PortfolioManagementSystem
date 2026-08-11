from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from src.services.tefas_service import TefasService, TefasServiceError


class FakeTefasClient:
    """Returns a predefined response without making an HTTP request."""

    def __init__(
        self,
        response: dict[str, Any],
        portfolio_response: dict[str, Any] | None = None,
    ) -> None:
        self.response = response
        self.portfolio_response = portfolio_response if portfolio_response is not None else response

    def fetch_general_info(self, **kwargs: Any) -> dict[str, Any]:
        return self.response

    def fetch_portfolio_breakdown(self, **kwargs: Any) -> dict[str, Any]:
        return self.portfolio_response


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
