from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from src.integrations.tefas_client import CustomTefasClient, FundKind


class TefasServiceError(RuntimeError):
    """Raised when TEFAS returns an unusable application response."""


class TefasService:
    """Coordinates TEFAS requests and normalizes returned data."""

    def __init__(
        self,
        client: CustomTefasClient | None = None,
    ) -> None:
        self.client = client or CustomTefasClient()

    def fetch_general_info(
        self,
        *,
        start_date: date,
        end_date: date,
        fund_kind: FundKind = "YAT",
        fund_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch and normalize general fund information."""

        response = self.client.fetch_general_info(
            start_date=start_date,
            end_date=end_date,
            fund_kind=fund_kind,
            fund_code=fund_code,
        )

        rows = self._extract_result_list(response)

        return [
            self._normalize_general_info_row(
                row=row,
                fund_kind=fund_kind,
            )
            for row in rows
        ]

    def fetch_portfolio_breakdown_raw(
        self,
        *,
        start_date: date,
        end_date: date,
        fund_kind: FundKind = "YAT",
        fund_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch raw portfolio-breakdown records.

        Normalization will be added after the endpoint fields are tested.
        """

        response = self.client.fetch_portfolio_breakdown(
            start_date=start_date,
            end_date=end_date,
            fund_kind=fund_kind,
            fund_code=fund_code,
        )

        return self._extract_result_list(response)

    @staticmethod
    def _extract_result_list(
        response: dict[str, Any],
    ) -> list[dict[str, Any]]:
        error_code = response.get("errorCode")
        error_message = response.get("errorMessage")

        if error_message and "out of bounds" in error_message.lower():
            return []

        if error_code or error_message:
            raise TefasServiceError(
                f"TEFAS application error: {error_message or error_code}"
            )

        result_list = response.get("resultList") or []

        if not isinstance(result_list, list):
            raise TefasServiceError(
                "TEFAS resultList must be a list."
            )

        return [
            row
            for row in result_list
            if isinstance(row, dict)
        ]

    @staticmethod
    def _normalize_general_info_row(
        *,
        row: dict[str, Any],
        fund_kind: FundKind,
    ) -> dict[str, Any]:
        return {
            "fund_code": TefasService._normalize_required_string(
                row.get("fonKodu"),
                field_name="fund_code",
                uppercase=True,
            ),
            "fund_name": TefasService._normalize_required_string(
                row.get("fonUnvan"),
                field_name="fund_name",
            ),
            "fund_kind": TefasService._normalize_required_string(
                fund_kind,
                field_name="fund_kind",
                uppercase=True,
            ),
            "data_date": TefasService._normalize_date(
                row.get("tarih"),
                field_name="data_date",
            ),
            "price": TefasService._normalize_required_decimal(
                row.get("fiyat"),
                field_name="price",
            ),
            "shares_outstanding": TefasService._normalize_optional_decimal(
                row.get("tedPaySayisi"),
                field_name="shares_outstanding",
            ),
            "investor_count": TefasService._normalize_optional_int(
                row.get("kisiSayisi"),
                field_name="investor_count",
            ),
            "portfolio_size": TefasService._normalize_optional_decimal(
                row.get("portfoyBuyukluk"),
                field_name="portfolio_size",
            ),
            "exchange_bulletin_price": TefasService._normalize_optional_decimal(
                row.get("borsaBultenFiyat"),
                field_name="exchange_bulletin_price",
            ),
        }

    @staticmethod
    def _normalize_required_string(
        value: Any,
        *,
        field_name: str,
        uppercase: bool = False,
    ) -> str:
        if not isinstance(value, str):
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        normalized_value = value.strip()
        if not normalized_value:
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        if uppercase:
            normalized_value = normalized_value.upper()

        return normalized_value

    @staticmethod
    def _normalize_date(value: Any, *, field_name: str) -> date:
        if isinstance(value, date):
            return value

        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError as exc:
                raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc

        raise TefasServiceError(f"Invalid normalized field: {field_name}")

    @staticmethod
    def _normalize_required_decimal(value: Any, *, field_name: str) -> Decimal:
        if value is None:
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc

    @staticmethod
    def _normalize_optional_decimal(value: Any, *, field_name: str) -> Decimal | None:
        if value is None:
            return None

        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc

    @staticmethod
    def _normalize_optional_int(value: Any, *, field_name: str) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (ValueError, TypeError) as exc:
            raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc
