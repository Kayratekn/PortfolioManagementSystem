from __future__ import annotations

from typing import Any

import httpx

from src.config.settings import get_settings


class AiClientError(RuntimeError):
    """Base error for AI service client failures."""


class AiServiceUnavailableError(AiClientError):
    """Raised when the AI service cannot be reached or returns a server error."""


class AiServiceRequestError(AiClientError):
    """Raised when the AI service rejects a request."""

    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


class AiServiceResponseError(AiClientError):
    """Raised when the AI service returns an unexpected response format."""


class AiClient:
    """Synchronous HTTP client for the stateless AI service."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        settings = get_settings() if base_url is None or timeout_seconds is None else None
        resolved_base_url = base_url if base_url is not None else settings.ai_service_url
        resolved_timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.ai_timeout_seconds
        )

        self.base_url = self._validate_base_url(resolved_base_url)
        self.timeout_seconds = self._validate_timeout_seconds(resolved_timeout_seconds)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = self._build_url(endpoint)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=self.headers, json=payload)
        except httpx.RequestError as exc:
            raise AiServiceUnavailableError("AI service request failed.") from exc

        if 500 <= response.status_code <= 599:
            raise AiServiceUnavailableError("AI service returned a server error.")
        if 400 <= response.status_code <= 499:
            raise AiServiceRequestError(
                "AI service rejected the request.",
                status_code=response.status_code,
            )

        try:
            response_data = response.json()
        except ValueError as exc:
            raise AiServiceResponseError("AI service returned invalid JSON.") from exc

        if not isinstance(response_data, dict):
            raise AiServiceResponseError("AI service returned an unexpected JSON response.")

        return response_data

    def _build_url(self, endpoint: str) -> str:
        normalized_endpoint = endpoint.strip()
        if normalized_endpoint.startswith("/"):
            return f"{self.base_url}{normalized_endpoint}"
        return f"{self.base_url}/{normalized_endpoint}"

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