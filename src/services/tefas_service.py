from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from src.integrations.tefas_client import CustomTefasClient, FundKind
from src.services.tefas_portfolio_allocation_mapping import (
    EXPECTED_ALLOCATION_FIELDS,
    get_allocation_label,
    get_mapping_status,
)


class TefasServiceError(RuntimeError):
    """Raised when TEFAS returns an unusable application response."""


GENERAL_INFO_MAX_CHUNK_DAYS = 28


PORTFOLIO_BREAKDOWN_METADATA_FIELDS = frozenset(
    {"fonKodu", "fonUnvan", "tarih", "bilFiyat"}
)


@dataclass(frozen=True)
class TefasPortfolioAllocationItem:
    raw_field_name: str
    allocation_percentage: Decimal
    label: str | None
    mapping_status: str


@dataclass(frozen=True)
class TefasPortfolioBreakdownSnapshot:
    fund_code: str
    fund_name: str
    data_date: date
    allocations: tuple[TefasPortfolioAllocationItem, ...]


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

        rows: list[dict[str, Any]] = []
        for chunk_start_date, chunk_end_date in self._iter_general_info_date_chunks(
            start_date=start_date,
            end_date=end_date,
        ):
            response = self.client.fetch_general_info(
                start_date=chunk_start_date,
                end_date=chunk_end_date,
                fund_kind=fund_kind,
                fund_code=fund_code,
            )
            rows.extend(self._extract_result_list(response))

        rows = self._filter_rows_by_fund_code(rows=rows, fund_code=fund_code)
        normalized_rows = [
            self._normalize_general_info_row(
                row=row,
                fund_kind=fund_kind,
            )
            for row in rows
        ]

        return self._deduplicate_and_sort_general_info_rows(normalized_rows)

    @staticmethod
    def _iter_general_info_date_chunks(
        *,
        start_date: date,
        end_date: date,
    ) -> list[tuple[date, date]]:
        if start_date > end_date:
            raise ValueError("start_date cannot be later than end_date.")

        chunks: list[tuple[date, date]] = []
        chunk_start_date = start_date
        while chunk_start_date <= end_date:
            chunk_end_date = min(
                chunk_start_date + timedelta(days=GENERAL_INFO_MAX_CHUNK_DAYS - 1),
                end_date,
            )
            chunks.append((chunk_start_date, chunk_end_date))
            chunk_start_date = chunk_end_date + timedelta(days=1)

        return chunks

    @staticmethod
    def _deduplicate_and_sort_general_info_rows(
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows_by_key: dict[tuple[str, date], dict[str, Any]] = {}
        for row in rows:
            key = (row["fund_code"], row["data_date"])
            existing_row = rows_by_key.get(key)
            if existing_row is None:
                rows_by_key[key] = row
                continue

            if existing_row != row:
                fund_code, data_date = key
                raise TefasServiceError(
                    "Conflicting duplicate TEFAS general-info row: "
                    f"fund_code={fund_code}, data_date={data_date.isoformat()}"
                )

        return sorted(
            rows_by_key.values(),
            key=lambda row: (row["data_date"], row["fund_code"]),
        )
    def fetch_portfolio_breakdown_raw(
        self,
        *,
        start_date: date,
        end_date: date,
        fund_kind: FundKind = "YAT",
        fund_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch raw portfolio-breakdown records."""

        response = self.client.fetch_portfolio_breakdown(
            start_date=start_date,
            end_date=end_date,
            fund_kind=fund_kind,
            fund_code=fund_code,
        )

        rows = self._extract_result_list(response)
        return self._filter_rows_by_fund_code(rows=rows, fund_code=fund_code)

    def normalize_portfolio_breakdown_row(
        self,
        row: dict[str, Any],
    ) -> TefasPortfolioBreakdownSnapshot:
        row_keys = set(row)
        missing_fields = sorted(EXPECTED_ALLOCATION_FIELDS - row_keys)
        if missing_fields:
            raise ValueError(
                "Missing expected TEFAS portfolio allocation fields: "
                + ", ".join(missing_fields)
            )

        unexpected_fields = sorted(
            row_keys - EXPECTED_ALLOCATION_FIELDS - PORTFOLIO_BREAKDOWN_METADATA_FIELDS
        )
        if unexpected_fields:
            raise ValueError(
                "Unexpected TEFAS portfolio breakdown fields: "
                + ", ".join(unexpected_fields)
            )

        allocations: list[TefasPortfolioAllocationItem] = []
        for raw_field_name in sorted(EXPECTED_ALLOCATION_FIELDS):
            raw_value = row[raw_field_name]
            if raw_value is None:
                continue

            allocation_percentage = self._normalize_allocation_decimal(
                raw_value,
                raw_field_name=raw_field_name,
            )
            allocations.append(
                TefasPortfolioAllocationItem(
                    raw_field_name=raw_field_name,
                    allocation_percentage=allocation_percentage,
                    label=get_allocation_label(raw_field_name),
                    mapping_status=get_mapping_status(raw_field_name),
                )
            )

        return TefasPortfolioBreakdownSnapshot(
            fund_code=self._normalize_required_string(
                row.get("fonKodu"),
                field_name="fund_code",
                uppercase=True,
            ),
            fund_name=self._normalize_required_string(
                row.get("fonUnvan"),
                field_name="fund_name",
            ),
            data_date=self._normalize_date(
                row.get("tarih"),
                field_name="data_date",
            ),
            allocations=tuple(allocations),
        )

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
    def _filter_rows_by_fund_code(
        *,
        rows: list[dict[str, Any]],
        fund_code: str | None,
    ) -> list[dict[str, Any]]:
        if fund_code is None:
            return rows

        normalized_fund_code = fund_code.strip().upper()
        return [
            row
            for row in rows
            if isinstance(row.get("fonKodu"), str)
            and row["fonKodu"].strip().upper() == normalized_fund_code
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

    @staticmethod
    def _normalize_allocation_decimal(
        value: Any,
        *,
        raw_field_name: str,
    ) -> Decimal:
        if isinstance(value, bool):
            raise ValueError(
                f"Invalid TEFAS allocation value for field '{raw_field_name}': bool is not allowed"
            )

        try:
            normalized_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(
                f"Invalid TEFAS allocation value for field '{raw_field_name}'"
            ) from exc

        if not normalized_value.is_finite():
            raise ValueError(
                f"Invalid TEFAS allocation value for field '{raw_field_name}': non-finite values are not allowed"
            )

        return normalized_value
