from __future__ import annotations

from datetime import date
from typing import Any, Literal

import httpx


FundKind = Literal["YAT", "EMK", "BYF", "GYF", "GSYF"]


class TefasClientError(RuntimeError):
    """Raised when communication with TEFAS fails."""


class CustomTefasClient:
    """HTTP client for direct communication with public TEFAS endpoints."""

    BASE_URL = "https://www.tefas.gov.tr"

    GENERAL_INFO_ENDPOINT = "/api/funds/fonGnlBlgSiraliGetir"
    PORTFOLIO_BREAKDOWN_ENDPOINT = "/api/funds/dagilimSiraliGetirT"

    DEFAULT_HEADERS = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://www.tefas.gov.tr",
        "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
    }

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

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

    def _post_json(
        self,
        *,
        endpoint: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        url = f"{self.BASE_URL}{endpoint}"

        try:
            with httpx.Client(
                timeout=self.timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = client.post(
                    url,
                    headers=self.DEFAULT_HEADERS,
                    json=payload,
                )

            response.raise_for_status()

        except httpx.HTTPError as exc:
            raise TefasClientError(
                f"TEFAS request failed: {exc}"
            ) from exc

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