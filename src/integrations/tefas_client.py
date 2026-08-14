from __future__ import annotations

from datetime import date
import time
from typing import Any, Literal

import httpx

from src.config.settings import get_settings


FundKind = Literal["YAT", "EMK", "BYF", "GYF", "GSYF"]


class TefasClientError(RuntimeError):
    """Raised when communication with TEFAS fails."""


class CustomTefasClient:
    """HTTP client for direct communication with public TEFAS endpoints."""

    GENERAL_INFO_ENDPOINT = "/api/funds/fonGnlBlgSiraliGetir"
    PORTFOLIO_BREAKDOWN_ENDPOINT = "/api/funds/dagilimSiraliGetirT"
    FUND_PROFILE_DETAIL_ENDPOINT = "/api/funds/fonProfilDtyGetir"
    FUND_DETAIL_ANALYSIS_PAGE_PATH = "/tr/fon-detayli-analiz"

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    )

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

        resolved_base_url = base_url if base_url is not None else settings.tefas_base_url
        resolved_timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.tefas_timeout_seconds
        )
        resolved_max_retries = max_retries if max_retries is not None else settings.tefas_max_retries
        resolved_retry_wait_seconds = (
            retry_wait_seconds
            if retry_wait_seconds is not None
            else settings.tefas_retry_wait_seconds
        )

        self.base_url = self._validate_base_url(resolved_base_url)
        self.timeout_seconds = self._validate_timeout_seconds(resolved_timeout_seconds)
        self.max_retries = self._validate_max_retries(resolved_max_retries)
        self.retry_wait_seconds = self._validate_retry_wait_seconds(resolved_retry_wait_seconds)
        self.headers = self._build_headers()

    def fetch_general_info(
        self,
        *,
        start_date: date,
        end_date: date,
        fund_kind: FundKind = "YAT",
        fund_code: str | None = None,
    ) -> dict[str, Any]:
        """Fetch price and general fund information from TEFAS."""

        payload = self._build_request_body(
            start_date=start_date,
            end_date=end_date,
            fund_kind=fund_kind,
            fund_code=fund_code,
        )

        return self._post_json(
            endpoint=self.GENERAL_INFO_ENDPOINT,
            payload=payload,
        )

    def fetch_portfolio_breakdown(
        self,
        *,
        start_date: date,
        end_date: date,
        fund_kind: FundKind = "YAT",
        fund_code: str | None = None,
    ) -> dict[str, Any]:
        """Fetch fund asset-allocation information from TEFAS."""

        payload = self._build_request_body(
            start_date=start_date,
            end_date=end_date,
            fund_kind=fund_kind,
            fund_code=fund_code,
        )

        return self._post_json(
            endpoint=self.PORTFOLIO_BREAKDOWN_ENDPOINT,
            payload=payload,
        )

    def fetch_fund_profile_detail(
        self,
        *,
        fund_code: str,
    ) -> dict[str, Any]:
        """Fetch source-oriented fund type/classification details from TEFAS."""

        payload = {
            "dil": "TR",
            "fonKodu": fund_code.strip().upper(),
            "periyod": "12",
        }

        return self._post_json(
            endpoint=self.FUND_PROFILE_DETAIL_ENDPOINT,
            payload=payload,
        )

    def fetch_fund_detail_analysis_page(
        self,
        *,
        fund_code: str,
    ) -> str:
        """Fetch the server-rendered TEFAS fund detail-analysis page."""

        normalized_fund_code = fund_code.strip().upper()
        endpoint = f"{self.FUND_DETAIL_ANALYSIS_PAGE_PATH}/{normalized_fund_code}"
        return self._get_text(endpoint=endpoint)

    @staticmethod
    def _build_request_body(
        *,
        start_date: date,
        end_date: date,
        fund_kind: FundKind,
        fund_code: str | None,
    ) -> dict[str, Any]:
        if start_date > end_date:
            raise ValueError("start_date cannot be later than end_date.")

        normalized_fund_code = (
            fund_code.strip().upper() if fund_code is not None else None
        )

        return {
            "fonTipi": fund_kind,
            "fonKodu": normalized_fund_code,
            "aramaMetni": None,
            "fonTurKod": None,
            "fonGrubu": None,
            "sfonTurKod": None,
            "fonTurAciklama": None,
            "kurucuKod": None,
            "basTarih": start_date.strftime("%Y%m%d"),
            "bitTarih": end_date.strftime("%Y%m%d"),
            "basSira": 1,
            "bitSira": 100000,
            "dil": "TR",
            "sFonTurKod": "",
            "fonKod": "",
            "fonGrup": "",
            "fonUnvanTip": "",
        }

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

    def _build_headers(self) -> dict[str, str]:
        return {
            "Accept": "*/*",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/tr/fon-verileri",
            "User-Agent": self.USER_AGENT,
        }

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

    def _post_json(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        total_attempts = 1 + self.max_retries

        for attempt_index in range(total_attempts):
            try:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                ) as client:
                    response = client.post(
                        url,
                        headers=self.headers,
                        json=payload,
                    )
            except httpx.RequestError as exc:
                if attempt_index < total_attempts - 1:
                    self._sleep_before_retry(attempt_index=attempt_index, total_attempts=total_attempts)
                    continue
                raise TefasClientError(f"TEFAS request failed: {exc}") from exc

            if self._should_retry_status_code(response.status_code):
                status_exc = self._build_status_error(response)
                if attempt_index < total_attempts - 1:
                    self._sleep_before_retry(attempt_index=attempt_index, total_attempts=total_attempts)
                    continue
                raise TefasClientError(f"TEFAS request failed: {status_exc}") from status_exc

            if 400 <= response.status_code <= 499:
                status_exc = self._build_status_error(response)
                raise TefasClientError(f"TEFAS request failed: {status_exc}") from status_exc

            try:
                response_data = response.json()
            except ValueError as exc:
                raise TefasClientError(
                    "TEFAS returned an invalid JSON response."
                ) from exc

            if not isinstance(response_data, dict):
                raise TefasClientError(
                    "Unexpected TEFAS response format."
                )

            return response_data

        raise TefasClientError("TEFAS request failed unexpectedly.")

    def _get_text(
        self,
        *,
        endpoint: str,
    ) -> str:
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
                raise TefasClientError(f"TEFAS request failed: {exc}") from exc

            if self._should_retry_status_code(response.status_code):
                status_exc = self._build_status_error(response)
                if attempt_index < total_attempts - 1:
                    self._sleep_before_retry(attempt_index=attempt_index, total_attempts=total_attempts)
                    continue
                raise TefasClientError(f"TEFAS request failed: {status_exc}") from status_exc

            if 400 <= response.status_code <= 499:
                status_exc = self._build_status_error(response)
                raise TefasClientError(f"TEFAS request failed: {status_exc}") from status_exc

            return response.text

        raise TefasClientError("TEFAS request failed unexpectedly.")
