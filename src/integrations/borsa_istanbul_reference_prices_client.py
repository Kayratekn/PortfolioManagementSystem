from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
import re
import time
from typing import Any

import httpx


class BorsaIstanbulReferencePricesClientError(RuntimeError):
    """Raised when the Borsa Istanbul historical reference-price API is unusable."""


@dataclass(frozen=True)
class BorsaIstanbulHistoricalObservation:
    provider_metal_code: str
    price_date: date
    raw_try_per_kg: Decimal | int


class BorsaIstanbulReferencePricesClient:
    """Read-only client for BIST's documented historical reference-price JSON API."""

    ENDPOINT = "https://www.borsaistanbul.com/referans-fiyatlari.php"
    OPERATION = "fetchReferansFiyatlari"
    SUPPORTED_PROVIDER_METAL_CODES = frozenset({"AU", "AG", "PT"})

    def __init__(
        self,
        *,
        endpoint: str = ENDPOINT,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_wait_seconds: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must not be blank.")
        if timeout_seconds <= 0 or max_retries < 0 or retry_wait_seconds < 0:
            raise ValueError("Invalid BIST HTTP retry/timeout configuration.")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_wait_seconds = retry_wait_seconds
        self.transport = transport
        self.sleep = sleep

    @property
    def headers(self) -> dict[str, str]:
        return {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}

    def fetch_historical(
        self,
        *,
        start_date: date,
        end_date: date,
        provider_metal_code: str,
    ) -> list[BorsaIstanbulHistoricalObservation]:
        self._validate_request(start_date, end_date, provider_metal_code)
        response_text = self._get(
            params={
                "op": self.OPERATION,
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "priceType": provider_metal_code,
            }
        )
        return self._parse_response(
            response_text=response_text,
            requested_start_date=start_date,
            requested_end_date=end_date,
            requested_provider_metal_code=provider_metal_code,
        )

    def _get(self, *, params: dict[str, str]) -> str:
        total_attempts = self.max_retries + 1
        for attempt_index in range(total_attempts):
            try:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                    transport=self.transport,
                ) as client:
                    response = client.get(self.endpoint, params=params, headers=self.headers)
            except httpx.RequestError as exc:
                if attempt_index < total_attempts - 1:
                    self.sleep(self.retry_wait_seconds)
                    continue
                raise BorsaIstanbulReferencePricesClientError(
                    f"BIST historical reference-price request failed: {exc}"
                ) from exc

            if response.status_code == 429 or response.status_code >= 500:
                if attempt_index < total_attempts - 1:
                    self.sleep(self.retry_wait_seconds)
                    continue
                raise BorsaIstanbulReferencePricesClientError(
                    f"BIST historical reference-price request returned HTTP {response.status_code}."
                )
            if not 200 <= response.status_code < 300:
                raise BorsaIstanbulReferencePricesClientError(
                    f"BIST historical reference-price request returned HTTP {response.status_code}."
                )
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type.lower():
                raise BorsaIstanbulReferencePricesClientError(
                    "BIST historical reference-price response did not declare application/json."
                )
            return response.text
        raise BorsaIstanbulReferencePricesClientError("BIST request failed unexpectedly.")

    @classmethod
    def _parse_response(
        cls,
        *,
        response_text: str,
        requested_start_date: date,
        requested_end_date: date,
        requested_provider_metal_code: str,
    ) -> list[BorsaIstanbulHistoricalObservation]:
        try:
            payload = json.loads(response_text, parse_float=Decimal)
        except (json.JSONDecodeError, TypeError) as exc:
            raise BorsaIstanbulReferencePricesClientError(
                "BIST historical reference-price response is not valid JSON."
            ) from exc
        if not isinstance(payload, dict):
            raise BorsaIstanbulReferencePricesClientError("BIST response must be a JSON object.")
        if payload.get("status") != "success":
            raise BorsaIstanbulReferencePricesClientError("BIST response status is not success.")
        data = payload.get("data")
        if not isinstance(data, list):
            raise BorsaIstanbulReferencePricesClientError("BIST response data must be a list.")

        observations: list[BorsaIstanbulHistoricalObservation] = []
        for row in data:
            observations.append(
                cls._parse_observation(
                    row=row,
                    requested_start_date=requested_start_date,
                    requested_end_date=requested_end_date,
                    requested_provider_metal_code=requested_provider_metal_code,
                )
            )
        return observations

    @staticmethod
    def _parse_observation(
        *,
        row: Any,
        requested_start_date: date,
        requested_end_date: date,
        requested_provider_metal_code: str,
    ) -> BorsaIstanbulHistoricalObservation:
        if not isinstance(row, dict):
            raise BorsaIstanbulReferencePricesClientError("BIST observation must be an object.")
        raw_date = row.get("priceDate")
        try:
            if not isinstance(raw_date, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date) is None:
                raise ValueError("not an ISO calendar date")
            price_date = date.fromisoformat(raw_date)
        except (TypeError, ValueError) as exc:
            raise BorsaIstanbulReferencePricesClientError("BIST observation has an invalid priceDate.") from exc
        if not requested_start_date <= price_date <= requested_end_date:
            raise BorsaIstanbulReferencePricesClientError("BIST observation priceDate is outside the requested range.")
        if row.get("priceRef") != "REF":
            raise BorsaIstanbulReferencePricesClientError("BIST observation priceRef must be REF.")
        if row.get("priceType") != requested_provider_metal_code:
            raise BorsaIstanbulReferencePricesClientError("BIST observation priceType differs from the requested metal.")
        if row.get("priceCurrency") != "TRY":
            raise BorsaIstanbulReferencePricesClientError("BIST observation priceCurrency must be TRY.")
        if row.get("priceWeight") != "KG":
            raise BorsaIstanbulReferencePricesClientError("BIST observation priceWeight must be KG.")
        raw_value = row.get("priceValue")
        if isinstance(raw_value, bool) or isinstance(raw_value, float) or not isinstance(raw_value, (Decimal, int)):
            raise BorsaIstanbulReferencePricesClientError("BIST observation priceValue must be an exact JSON number.")
        if isinstance(raw_value, Decimal) and not raw_value.is_finite() or raw_value <= 0:
            raise BorsaIstanbulReferencePricesClientError("BIST observation priceValue must be finite and greater than zero.")
        return BorsaIstanbulHistoricalObservation(
            provider_metal_code=requested_provider_metal_code,
            price_date=price_date,
            raw_try_per_kg=raw_value,
        )

    @classmethod
    def _validate_request(cls, start_date: date, end_date: date, provider_metal_code: str) -> None:
        if not isinstance(start_date, date) or not isinstance(end_date, date):
            raise ValueError("BIST historical dates must be date instances.")
        if start_date > end_date:
            raise ValueError("start_date cannot be later than end_date.")
        if provider_metal_code not in cls.SUPPORTED_PROVIDER_METAL_CODES:
            raise ValueError("Unsupported BIST provider metal code.")
