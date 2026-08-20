from __future__ import annotations

from dataclasses import dataclass
import html as html_module
import json
import re
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


SUPPORTED_MANAGEMENT_FEE_FUND_KINDS = frozenset({"YAT", "EMK"})
TEFAS_MANAGEMENT_FEE_LOCALE_PATTERN = re.compile(r"^(?:\d+(?:,\d*)?|,\d+)$")


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





@dataclass(frozen=True)
class TefasFundDetailPageMetadataResult:
    fund_code: str
    fund_category: str
    category_rank: int | None
    category_fund_count: int | None
    market_share_raw: Decimal | None
    isin: str | None = None
    risk_value: int | None = None
    tefas_status: str | None = None
    transaction_start_time: str | None = None
    transaction_end_time: str | None = None
    entry_commission_raw: Decimal | None = None
    exit_commission_raw: Decimal | None = None
    interest_content: str | None = None
    fund_sale_valor: int | None = None
    fund_redemption_valor: int | None = None
    source_page: str = "fon-detayli-analiz"
    source_field_names: tuple[str, ...] = (
        "fonKodu",
        "fonKategori",
        "kategoriDerece",
        "kategoriFonSay",
        "pazarPayi",
        "isinKodu",
        "riskDegeri",
        "tefasDurum",
        "basIsSaat",
        "sonIsSaat",
        "girisKomisyonu",
        "cikisKomisyonu",
        "faizIcerigi",
        "fonSatisValor",
        "fonGeriAlisValor",
    )


@dataclass(frozen=True)
class TefasFundTypeResult:
    fund_code: str
    fund_type_name: str
    raw_field_name: str = "fonTuru"
    source_endpoint: str = "fonProfilDtyGetir"


@dataclass(frozen=True)
class TefasManagementFeeResult:
    fund_code: str
    management_fee_percentage: Decimal
    fund_kind: str
    raw_field_name: str = "uygulananYu1Y"
    source_endpoint: str = "fonYonetimBazliBilgiGetir"


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

    def get_fund_detail_page_metadata(
        self,
        *,
        fund_code: str,
    ) -> TefasFundDetailPageMetadataResult:
        """Return source-oriented metadata from the TEFAS detail-analysis page."""

        normalized_fund_code = self._normalize_required_string(
            fund_code,
            field_name="fund_code",
            uppercase=True,
        )
        html_text = self.client.fetch_fund_detail_analysis_page(
            fund_code=normalized_fund_code,
        )
        bilgi_data, profil_data = self._extract_detail_page_data_from_html(
            html_text=html_text,
            fund_code=normalized_fund_code,
        )

        source_fund_code = self._normalize_required_string(
            bilgi_data.get("fonKodu"),
            field_name="fund_code",
            uppercase=True,
        )
        if source_fund_code != normalized_fund_code:
            raise TefasServiceError(
                "TEFAS detail-analysis page fund code mismatch: "
                f"requested={normalized_fund_code}, source={source_fund_code}"
            )

        return TefasFundDetailPageMetadataResult(
            fund_code=source_fund_code,
            fund_category=self._normalize_required_string(
                bilgi_data.get("fonKategori"),
                field_name="fund_category",
            ),
            category_rank=self._normalize_optional_integral_int(
                bilgi_data.get("kategoriDerece"),
                field_name="category_rank",
            ),
            category_fund_count=self._normalize_optional_integral_int(
                bilgi_data.get("kategoriFonSay"),
                field_name="category_fund_count",
            ),
            market_share_raw=self._normalize_optional_decimal(
                bilgi_data.get("pazarPayi"),
                field_name="market_share_raw",
            ),
            isin=self._normalize_optional_isin(
                profil_data.get("isinKodu"),
                field_name="isin",
            ),
            risk_value=self._normalize_optional_risk_value(
                profil_data.get("riskDegeri"),
                field_name="risk_value",
            ),
            tefas_status=self._normalize_optional_trimmed_string(
                profil_data.get("tefasDurum"),
                field_name="tefas_status",
            ),
            transaction_start_time=self._normalize_optional_trimmed_string(
                profil_data.get("basIsSaat"),
                field_name="transaction_start_time",
            ),
            transaction_end_time=self._normalize_optional_trimmed_string(
                profil_data.get("sonIsSaat"),
                field_name="transaction_end_time",
            ),
            entry_commission_raw=self._normalize_optional_finite_decimal(
                profil_data.get("girisKomisyonu"),
                field_name="entry_commission_raw",
            ),
            exit_commission_raw=self._normalize_optional_finite_decimal(
                profil_data.get("cikisKomisyonu"),
                field_name="exit_commission_raw",
            ),
            interest_content=self._normalize_optional_trimmed_string(
                profil_data.get("faizIcerigi"),
                field_name="interest_content",
            ),
            fund_sale_valor=self._normalize_optional_integral_int(
                profil_data.get("fonSatisValor"),
                field_name="fund_sale_valor",
            ),
            fund_redemption_valor=self._normalize_optional_integral_int(
                profil_data.get("fonGeriAlisValor"),
                field_name="fund_redemption_valor",
            ),
        )

    def fetch_management_fees(
        self,
        *,
        fund_kind: FundKind = "YAT",
    ) -> list[TefasManagementFeeResult]:
        """Fetch applied annual management fees for supported TEFAS fund kinds."""

        normalized_fund_kind = self._normalize_required_string(
            fund_kind,
            field_name="fund_kind",
            uppercase=True,
        )
        if normalized_fund_kind not in SUPPORTED_MANAGEMENT_FEE_FUND_KINDS:
            raise ValueError(
                "management-fee extraction currently supports only YAT and EMK."
            )

        response = self.client.fetch_management_fee_info(
            fund_kind=normalized_fund_kind,
        )
        rows = self._extract_result_list(response)
        results = [
            self._normalize_management_fee_row(
                row=row,
                fund_kind=normalized_fund_kind,
            )
            for row in rows
        ]

        return self._deduplicate_and_sort_management_fee_results(results)

    def get_fund_type(self, *, fund_code: str) -> TefasFundTypeResult:
        """Return the selected fund's source-oriented fonTuru value."""

        normalized_fund_code = self._normalize_required_string(
            fund_code,
            field_name="fund_code",
            uppercase=True,
        )
        response = self.client.fetch_fund_profile_detail(
            fund_code=normalized_fund_code,
        )
        rows = self._extract_result_list(response)
        matching_rows = [
            row
            for row in rows
            if isinstance(row.get("fonKodu"), str)
            and row["fonKodu"].strip().casefold() == normalized_fund_code.casefold()
        ]

        if not matching_rows:
            raise TefasServiceError(
                f"TEFAS fund profile row not found: fund_code={normalized_fund_code}"
            )

        if len(matching_rows) > 1:
            raise TefasServiceError(
                f"Duplicate TEFAS fund profile rows: fund_code={normalized_fund_code}"
            )

        row = matching_rows[0]
        return TefasFundTypeResult(
            fund_code=self._normalize_required_string(
                row.get("fonKodu"),
                field_name="fund_code",
                uppercase=True,
            ),
            fund_type_name=self._normalize_required_string(
                row.get("fonTuru"),
                field_name="fund_type_name",
            ),
        )

    @staticmethod
    def _deduplicate_and_sort_management_fee_results(
        results: list[TefasManagementFeeResult],
    ) -> list[TefasManagementFeeResult]:
        results_by_fund_code: dict[str, TefasManagementFeeResult] = {}
        for result in results:
            existing_result = results_by_fund_code.get(result.fund_code)
            if existing_result is None:
                results_by_fund_code[result.fund_code] = result
                continue

            if existing_result != result:
                raise TefasServiceError(
                    "Conflicting duplicate TEFAS management-fee row: "
                    f"fund_code={result.fund_code}"
                )

        return sorted(
            results_by_fund_code.values(),
            key=lambda result: result.fund_code,
        )

    @staticmethod
    def _normalize_management_fee_row(
        *,
        row: dict[str, Any],
        fund_kind: str,
    ) -> TefasManagementFeeResult:
        return TefasManagementFeeResult(
            fund_code=TefasService._normalize_required_string(
                row.get("fonKodu"),
                field_name="fund_code",
                uppercase=True,
            ),
            management_fee_percentage=TefasService._normalize_management_fee_percentage(
                row.get("uygulananYu1Y"),
                field_name="management_fee_percentage",
            ),
            fund_kind=fund_kind,
        )

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
    def _extract_detail_page_data_from_html(
        *,
        html_text: str,
        fund_code: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        if not isinstance(html_text, str) or not html_text:
            raise TefasServiceError("TEFAS detail-analysis page HTML is empty.")

        bilgi_data_objects: list[dict[str, Any]] = []
        profil_data_objects: list[dict[str, Any]] = []
        for candidate_text in TefasService._iter_detail_page_candidate_texts(html_text):
            bilgi_data_objects.extend(
                TefasService._find_detail_page_data_objects(
                    candidate_text,
                    marker_name="bilgiData",
                )
            )
            profil_data_objects.extend(
                TefasService._find_detail_page_data_objects(
                    candidate_text,
                    marker_name="profilData",
                )
            )

        if not bilgi_data_objects:
            raise TefasServiceError("TEFAS detail-analysis bilgiData not found.")

        exact_matches: list[dict[str, Any]] = []
        for bilgi_data in bilgi_data_objects:
            try:
                source_fund_code = TefasService._normalize_required_string(
                    bilgi_data.get("fonKodu"),
                    field_name="fund_code",
                    uppercase=True,
                )
            except TefasServiceError:
                continue

            if source_fund_code == fund_code:
                exact_matches.append(bilgi_data)

        if not exact_matches:
            raise TefasServiceError(
                f"TEFAS detail-analysis bilgiData exact match not found: fund_code={fund_code}"
            )

        first_match_key = TefasService._build_detail_page_data_comparison_key(exact_matches[0])
        if any(
            TefasService._build_detail_page_data_comparison_key(match) != first_match_key
            for match in exact_matches[1:]
        ):
            raise TefasServiceError(
                f"Conflicting TEFAS detail-analysis bilgiData exact matches: fund_code={fund_code}"
            )

        profil_data = TefasService._select_matching_profil_data(
            profil_data_objects=profil_data_objects,
            fund_code=fund_code,
        )
        return exact_matches[0], profil_data

    @staticmethod
    def _select_matching_profil_data(
        *,
        profil_data_objects: list[dict[str, Any]],
        fund_code: str,
    ) -> dict[str, Any]:
        if not profil_data_objects:
            return {}

        exact_matches: list[dict[str, Any]] = []
        for profil_data in profil_data_objects:
            try:
                source_fund_code = TefasService._normalize_required_string(
                    profil_data.get("fonKodu"),
                    field_name="fund_code",
                    uppercase=True,
                )
            except TefasServiceError:
                continue

            if source_fund_code == fund_code:
                exact_matches.append(profil_data)

        if not exact_matches:
            return {}

        first_match_key = TefasService._build_detail_page_data_comparison_key(exact_matches[0])
        if any(
            TefasService._build_detail_page_data_comparison_key(match) != first_match_key
            for match in exact_matches[1:]
        ):
            raise TefasServiceError(
                f"Conflicting TEFAS detail-analysis profilData exact matches: fund_code={fund_code}"
            )

        return exact_matches[0]

    @staticmethod
    def _iter_detail_page_candidate_texts(html_text: str) -> list[str]:
        candidate_texts = [html_text]
        unescaped_html_text = html_module.unescape(html_text)
        if unescaped_html_text != html_text:
            candidate_texts.append(unescaped_html_text)

        for candidate_text in list(candidate_texts):
            for payload_text in TefasService._extract_next_f_push_strings(candidate_text):
                candidate_texts.append(payload_text)
                unescaped_payload_text = html_module.unescape(payload_text)
                if unescaped_payload_text != payload_text:
                    candidate_texts.append(unescaped_payload_text)

        return candidate_texts

    @staticmethod
    def _extract_next_f_push_strings(candidate_text: str) -> list[str]:
        marker = "self.__next_f.push("
        decoder = json.JSONDecoder(parse_float=Decimal)
        payload_strings: list[str] = []
        search_start = 0

        while True:
            marker_index = candidate_text.find(marker, search_start)
            if marker_index == -1:
                return payload_strings

            json_start_index = marker_index + len(marker)
            while (
                json_start_index < len(candidate_text)
                and candidate_text[json_start_index].isspace()
            ):
                json_start_index += 1

            search_start = json_start_index + 1
            try:
                parsed_value, decoded_length = decoder.raw_decode(
                    candidate_text[json_start_index:]
                )
            except json.JSONDecodeError:
                continue

            payload_strings.extend(TefasService._iter_strings(parsed_value))
            search_start = json_start_index + decoded_length

    @staticmethod
    def _iter_strings(value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]

        if isinstance(value, list):
            strings: list[str] = []
            for item in value:
                strings.extend(TefasService._iter_strings(item))
            return strings

        if isinstance(value, dict):
            strings = []
            for item in value.values():
                strings.extend(TefasService._iter_strings(item))
            return strings

        return []

    @staticmethod
    def _build_detail_page_data_comparison_key(value: Any) -> Any:
        if isinstance(value, Decimal):
            return ("Decimal", str(value))

        if isinstance(value, dict):
            return (
                "dict",
                tuple(
                    sorted(
                        (key, TefasService._build_detail_page_data_comparison_key(item))
                        for key, item in value.items()
                    )
                ),
            )

        if isinstance(value, list):
            return (
                "list",
                tuple(TefasService._build_detail_page_data_comparison_key(item) for item in value),
            )

        return value

    @staticmethod
    def _find_detail_page_data_objects(
        candidate_text: str,
        *,
        marker_name: str,
    ) -> list[dict[str, Any]]:
        marker = json.dumps(marker_name)
        decoder = json.JSONDecoder(parse_float=Decimal)
        objects: list[dict[str, Any]] = []
        search_start = 0

        while True:
            marker_index = candidate_text.find(marker, search_start)
            if marker_index == -1:
                return objects

            search_start = marker_index + len(marker)
            colon_index = candidate_text.find(":", search_start)
            if colon_index == -1:
                continue

            json_start_index = colon_index + 1
            while (
                json_start_index < len(candidate_text)
                and candidate_text[json_start_index].isspace()
            ):
                json_start_index += 1

            try:
                parsed_value, decoded_length = decoder.raw_decode(
                    candidate_text[json_start_index:]
                )
            except json.JSONDecodeError:
                continue

            if not isinstance(parsed_value, dict):
                if TefasService._is_next_reference_marker_value(
                    parsed_value,
                    marker_name=marker_name,
                ):
                    search_start = json_start_index + decoded_length
                    continue

                raise TefasServiceError(
                    f"TEFAS detail-analysis {marker_name} must be an object."
                )

            objects.append(parsed_value)
            search_start = json_start_index + decoded_length

    @staticmethod
    def _is_next_reference_marker_value(value: Any, *, marker_name: str) -> bool:
        return (
            isinstance(value, str)
            and value.startswith("$")
            and value.endswith(f":{marker_name}")
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
            "investor_count": TefasService._normalize_general_info_investor_count(
                row.get("kisiSayisi"),
                fund_kind=fund_kind,
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
    def _normalize_optional_trimmed_string(value: Any, *, field_name: str) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        normalized_value = value.strip()
        if not normalized_value:
            return None

        return normalized_value

    @staticmethod
    def _normalize_optional_isin(value: Any, *, field_name: str) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        normalized_value = value.strip().upper()
        if not normalized_value:
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

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
    def _normalize_optional_finite_decimal(value: Any, *, field_name: str) -> Decimal | None:
        if value is None:
            return None

        if isinstance(value, bool):
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        try:
            normalized_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc

        if not normalized_value.is_finite():
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        return normalized_value

    @staticmethod
    def _normalize_optional_int(value: Any, *, field_name: str) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (ValueError, TypeError) as exc:
            raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc

    @staticmethod
    def _normalize_general_info_investor_count(
        value: Any,
        *,
        fund_kind: FundKind,
    ) -> int | None:
        normalized_value = TefasService._normalize_optional_int(
            value,
            field_name="investor_count",
        )
        normalized_fund_kind = TefasService._normalize_required_string(
            fund_kind,
            field_name="fund_kind",
            uppercase=True,
        )
        if normalized_fund_kind == "BYF" and normalized_value == 0:
            return None

        return normalized_value

    @staticmethod
    def _normalize_optional_integral_int(value: Any, *, field_name: str) -> int | None:
        if value is None:
            return None

        if isinstance(value, bool):
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc

        if not decimal_value.is_finite() or decimal_value != decimal_value.to_integral_value():
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        return int(decimal_value)

    @staticmethod
    def _normalize_optional_risk_value(value: Any, *, field_name: str) -> int | None:
        normalized_value = TefasService._normalize_optional_integral_int(
            value,
            field_name=field_name,
        )
        if normalized_value is None:
            return None

        if normalized_value < 1 or normalized_value > 7:
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        return normalized_value

    @staticmethod
    def _normalize_management_fee_percentage(
        value: Any,
        *,
        field_name: str,
    ) -> Decimal:
        if isinstance(value, bool) or value is None:
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        if not isinstance(value, str):
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        normalized_text = value.strip()
        if (
            not normalized_text
            or not TEFAS_MANAGEMENT_FEE_LOCALE_PATTERN.fullmatch(normalized_text)
        ):
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        decimal_text = normalized_text.replace(",", ".")
        if decimal_text.startswith("."):
            decimal_text = "0" + decimal_text
        if decimal_text.endswith("."):
            decimal_text = decimal_text[:-1]

        try:
            decimal_value = Decimal(decimal_text)
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise TefasServiceError(f"Invalid normalized field: {field_name}") from exc

        if not decimal_value.is_finite() or decimal_value < 0:
            raise TefasServiceError(f"Invalid normalized field: {field_name}")

        return decimal_value

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
