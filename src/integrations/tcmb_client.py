from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import time
import xml.etree.ElementTree as ET

import httpx

from src.config.settings import get_settings


SUPPORTED_CURRENCIES = ("USD", "EUR", "GBP")
QUOTE_CURRENCY = "TRY"


class TcmbClientError(RuntimeError):
    """Raised when communication with TCMB fails."""


@dataclass(frozen=True)
class TcmbExchangeRateObservation:
    base_currency: str
    quote_currency: str
    rate_date: date
    forex_buying: Decimal
    forex_selling: Decimal


class TcmbClient:
    """HTTP client for direct communication with public TCMB XML endpoints."""

    CURRENT_RATES_ENDPOINT = "/kurlar/today.xml"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        max_retries: int | None = None,
        retry_wait_seconds: float | None = None,
    ) -> None:
        settings = get_settings() if any(
            value is None
            for value in (base_url, timeout_seconds, max_retries, retry_wait_seconds)
        ) else None

        resolved_base_url = base_url if base_url is not None else settings.tcmb_base_url
        resolved_timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.tcmb_timeout_seconds
        )
        resolved_max_retries = max_retries if max_retries is not None else settings.tcmb_max_retries
        resolved_retry_wait_seconds = (
            retry_wait_seconds
            if retry_wait_seconds is not None
            else settings.tcmb_retry_wait_seconds
        )

        self.base_url = self._validate_base_url(resolved_base_url)
        self.timeout_seconds = self._validate_timeout_seconds(resolved_timeout_seconds)
        self.max_retries = self._validate_max_retries(resolved_max_retries)
        self.retry_wait_seconds = self._validate_retry_wait_seconds(resolved_retry_wait_seconds)

    def fetch_current_rates(self) -> list[TcmbExchangeRateObservation]:
        xml_text = self._get_text(endpoint=self.CURRENT_RATES_ENDPOINT)
        return self._parse_rates(xml_text)

    def fetch_historical_rates(
        self,
        *,
        rate_date: date,
    ) -> list[TcmbExchangeRateObservation]:
        endpoint = f"/kurlar/{rate_date:%Y%m}/{rate_date:%d%m%Y}.xml"
        xml_text = self._get_text(endpoint=endpoint)
        return self._parse_rates(xml_text)

    @staticmethod
    def _validate_base_url(value: str) -> str:
        normalized_value = value.strip().rstrip("/") if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError("base_url must not be empty.")
        return normalized_value

    @staticmethod
    def _validate_timeout_seconds(value: float) -> float:
        if value <= 0:
            raise ValueError("timeout_seconds must be greater than 0.")
        return value

    @staticmethod
    def _validate_max_retries(value: int) -> int:
        if value < 0:
            raise ValueError("max_retries must be greater than or equal to 0.")
        return value

    @staticmethod
    def _validate_retry_wait_seconds(value: float) -> float:
        if value < 0:
            raise ValueError("retry_wait_seconds must be greater than or equal to 0.")
        return value

    @staticmethod
    def _should_retry_status_code(status_code: int) -> bool:
        return status_code == 429 or 500 <= status_code <= 599

    @staticmethod
    def _build_status_error(response: httpx.Response) -> httpx.HTTPStatusError:
        return httpx.HTTPStatusError(
            f"Server returned status code {response.status_code}",
            request=response.request,
            response=response,
        )

    def _sleep_before_retry(self, *, attempt_index: int, total_attempts: int) -> None:
        if attempt_index < total_attempts - 1:
            time.sleep(self.retry_wait_seconds)

    def _get_text(self, *, endpoint: str) -> str:
        url = f"{self.base_url}{endpoint}"
        total_attempts = 1 + self.max_retries

        for attempt_index in range(total_attempts):
            try:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                ) as client:
                    response = client.get(url)
            except httpx.RequestError as exc:
                if attempt_index < total_attempts - 1:
                    self._sleep_before_retry(attempt_index=attempt_index, total_attempts=total_attempts)
                    continue
                raise TcmbClientError(f"TCMB request failed: {exc}") from exc

            if self._should_retry_status_code(response.status_code):
                status_exc = self._build_status_error(response)
                if attempt_index < total_attempts - 1:
                    self._sleep_before_retry(attempt_index=attempt_index, total_attempts=total_attempts)
                    continue
                raise TcmbClientError(f"TCMB request failed: {status_exc}") from status_exc

            if 400 <= response.status_code <= 499:
                status_exc = self._build_status_error(response)
                raise TcmbClientError(f"TCMB request failed: {status_exc}") from status_exc

            return response.text

        raise TcmbClientError("TCMB request failed unexpectedly.")

    def _parse_rates(self, xml_text: str) -> list[TcmbExchangeRateObservation]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            raise TcmbClientError("TCMB returned malformed XML.") from exc

        effective_date = self._parse_effective_date(root)
        rows_by_currency = self._index_currency_rows(root)

        observations: list[TcmbExchangeRateObservation] = []
        for currency_code in SUPPORTED_CURRENCIES:
            row = rows_by_currency.get(currency_code)
            if row is None:
                raise TcmbClientError(f"TCMB XML missing {currency_code} currency row.")

            unit = self._parse_positive_decimal(
                row.findtext("Unit"),
                field_name="Unit",
                currency_code=currency_code,
            )
            forex_buying = self._parse_positive_decimal(
                row.findtext("ForexBuying"),
                field_name="ForexBuying",
                currency_code=currency_code,
            )
            forex_selling = self._parse_positive_decimal(
                row.findtext("ForexSelling"),
                field_name="ForexSelling",
                currency_code=currency_code,
            )

            observations.append(
                TcmbExchangeRateObservation(
                    base_currency=currency_code,
                    quote_currency=QUOTE_CURRENCY,
                    rate_date=effective_date,
                    forex_buying=forex_buying / unit,
                    forex_selling=forex_selling / unit,
                )
            )

        return observations

    @staticmethod
    def _parse_effective_date(root: ET.Element) -> date:
        raw_date = root.attrib.get("Tarih")
        if raw_date is None or not raw_date.strip():
            raise TcmbClientError("TCMB XML missing effective date Tarih attribute.")

        try:
            return datetime.strptime(raw_date.strip(), "%d.%m.%Y").date()
        except ValueError as exc:
            raise TcmbClientError("TCMB XML has invalid effective date Tarih attribute.") from exc

    @staticmethod
    def _index_currency_rows(root: ET.Element) -> dict[str, ET.Element]:
        rows_by_currency: dict[str, ET.Element] = {}
        for row in root.findall("Currency"):
            currency_code = row.attrib.get("CurrencyCode")
            if currency_code in SUPPORTED_CURRENCIES:
                rows_by_currency[currency_code] = row
        return rows_by_currency

    @staticmethod
    def _parse_positive_decimal(
        raw_value: str | None,
        *,
        field_name: str,
        currency_code: str,
    ) -> Decimal:
        if raw_value is None or not raw_value.strip():
            raise TcmbClientError(f"TCMB XML missing {field_name} for {currency_code}.")

        try:
            value = Decimal(raw_value.strip())
        except InvalidOperation as exc:
            raise TcmbClientError(f"TCMB XML has invalid {field_name} for {currency_code}.") from exc

        if not value.is_finite():
            raise TcmbClientError(f"TCMB XML has invalid {field_name} for {currency_code}.")

        if value <= 0:
            raise TcmbClientError(f"TCMB XML has non-positive {field_name} for {currency_code}.")

        return value