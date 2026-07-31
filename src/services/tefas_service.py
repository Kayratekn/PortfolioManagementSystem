from __future__ import annotations

from datetime import date
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
        fund_code = row.get("fonKodu")
        fund_name = row.get("fonUnvan")

        return {
            "fund_code": (
                fund_code.strip().upper()
                if isinstance(fund_code, str)
                else fund_code
            ),
            "fund_name": (
                fund_name.strip()
                if isinstance(fund_name, str)
                else fund_name
            ),
            "fund_kind": fund_kind,
            "data_date": row.get("tarih"),
            "price": row.get("fiyat"),
            "shares_outstanding": row.get("tedPaySayisi"),
            "investor_count": row.get("kisiSayisi"),
            "portfolio_size": row.get("portfoyBuyukluk"),
            "exchange_bulletin_price": row.get("borsaBultenFiyat"),
        }