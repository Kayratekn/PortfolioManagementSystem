from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import time
from typing import Any
from xml.etree import ElementTree

import httpx


class BorsaIstanbulCurrentReferencePricesClientError(RuntimeError):
    """Raised when BIST's current reference-price snapshot is unusable."""


@dataclass(frozen=True)
class BorsaIstanbulCurrentReferencePricesSnapshot:
    effective_date: date
    gold_raw_try_per_kg: Decimal
    silver_raw_try_per_kg: Decimal
    platinum_raw_try_per_kg: Decimal


class BorsaIstanbulCurrentReferencePricesClient:
    """Read-only client for BIST's current TRY/kg reference-price XML snapshot."""

    ENDPOINT = "https://www.borsaistanbul.com/referans-fiyatlari.php"
    OPERATION = "generateReferansFiyatlariXML"
    _TURKISH_GROUPED_DECIMAL = re.compile(r"^[0-9]{1,3}(?:\.[0-9]{3})+(?:,[0-9]+)?$")
    _TURKISH_UNGROUPED_DECIMAL = re.compile(r"^[0-9]+(?:,[0-9]+)?$")

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
        return {"Accept": "application/xml"}

    def fetch_current(self) -> BorsaIstanbulCurrentReferencePricesSnapshot:
        return self._parse_response(self._decode_and_validate_xml(self._get()))

    def _get(self) -> bytes:
        total_attempts = self.max_retries + 1
        for attempt_index in range(total_attempts):
            try:
                with httpx.Client(
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                    transport=self.transport,
                ) as client:
                    response = client.get(
                        self.endpoint,
                        params={"op": self.OPERATION},
                        headers=self.headers,
                    )
            except httpx.RequestError as exc:
                if attempt_index < total_attempts - 1:
                    self.sleep(self.retry_wait_seconds)
                    continue
                raise BorsaIstanbulCurrentReferencePricesClientError(
                    f"BIST current reference-price request failed: {exc}"
                ) from exc

            if response.status_code == 429 or response.status_code >= 500:
                if attempt_index < total_attempts - 1:
                    self.sleep(self.retry_wait_seconds)
                    continue
                raise BorsaIstanbulCurrentReferencePricesClientError(
                    "BIST current reference-price request returned "
                    f"HTTP {response.status_code}."
                )
            if not 200 <= response.status_code < 300:
                raise BorsaIstanbulCurrentReferencePricesClientError(
                    "BIST current reference-price request returned "
                    f"HTTP {response.status_code}."
                )
            self._validate_content_type(response.headers.get("content-type", ""))
            return response.content
        raise BorsaIstanbulCurrentReferencePricesClientError("BIST request failed unexpectedly.")

    @classmethod
    def _validate_content_type(cls, raw_content_type: str) -> None:
        if not isinstance(raw_content_type, str):
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price response did not declare XML content."
            )
        components = [component.strip() for component in raw_content_type.split(";")]
        media_type = components[0].lower()
        if media_type not in {"application/xml", "text/xml"} and not media_type.endswith("+xml"):
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price response did not declare XML content."
            )
        for component in components[1:]:
            if "=" not in component:
                continue
            name, value = component.split("=", 1)
            if name.strip().lower() != "charset":
                continue
            if value.strip().strip('"').lower() != "utf-8":
                raise BorsaIstanbulCurrentReferencePricesClientError(
                    "BIST current reference-price response charset must be UTF-8."
                )

    @classmethod
    def _decode_and_validate_xml(cls, response_content: bytes) -> str:
        if not isinstance(response_content, bytes):
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price response must be bytes."
            )
        try:
            response_text = response_content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price response must be valid UTF-8."
            ) from exc
        declaration = re.match(
            r"\s*<\?xml\s+[^>]*\bencoding\s*=\s*(['\"])([^'\"]+)\1",
            response_text,
            re.IGNORECASE,
        )
        if declaration is not None and declaration.group(2).lower() != "utf-8":
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price XML declaration must use UTF-8."
            )
        # ElementTree does not need the stylesheet. Reject DTD/entity declarations
        # in decoded text before ElementTree receives the document.
        upper_text = response_text.upper()
        if "<!DOCTYPE" in upper_text or "<!ENTITY" in upper_text:
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price response must not contain DTD or entity declarations."
            )
        return response_text

    @classmethod
    def _parse_response(cls, response_text: str) -> BorsaIstanbulCurrentReferencePricesSnapshot:
        if not isinstance(response_text, str):
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price response must be decoded text."
            )
        try:
            root = ElementTree.fromstring(response_text)
        except ElementTree.ParseError as exc:
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price response is not valid XML."
            ) from exc
        if root.tag != "IGE":
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price XML root must be IGE."
            )

        effective_date = cls._parse_effective_date(root)
        tl = cls._require_exactly_one_child(root, "TL", "TL")
        return BorsaIstanbulCurrentReferencePricesSnapshot(
            effective_date=effective_date,
            gold_raw_try_per_kg=cls._parse_turkish_decimal(
                cls._require_exactly_one_child(tl, "altindeger", "GOLD value").text
            ),
            silver_raw_try_per_kg=cls._parse_turkish_decimal(
                cls._require_exactly_one_child(tl, "gumusdeger", "SILVER value").text
            ),
            platinum_raw_try_per_kg=cls._parse_turkish_decimal(
                cls._require_exactly_one_child(tl, "platindeger", "PLATINUM value").text
            ),
        )

    @classmethod
    def _parse_effective_date(cls, root: ElementTree.Element) -> date:
        day_container = cls._require_exactly_one_child(root, "IGE_GUN", "IGE_GUN")
        raw_date = cls._require_exactly_one_child(day_container, "gun", "effective date").text
        if not isinstance(raw_date, str):
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price effective date is missing."
            )
        try:
            if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", raw_date.strip()) is None:
                raise ValueError("not DD.MM.YYYY")
            return datetime.strptime(raw_date.strip(), "%d.%m.%Y").date()
        except ValueError as exc:
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price effective date must be DD.MM.YYYY."
            ) from exc

    @staticmethod
    def _require_exactly_one_child(
        parent: ElementTree.Element,
        tag: str,
        label: str,
    ) -> ElementTree.Element:
        matches = [child for child in parent if child.tag == tag]
        if len(matches) != 1:
            raise BorsaIstanbulCurrentReferencePricesClientError(
                f"BIST current reference-price XML must contain exactly one {label}."
            )
        return matches[0]

    @classmethod
    def _parse_turkish_decimal(cls, raw_value: Any) -> Decimal:
        if not isinstance(raw_value, str):
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price value must be text."
            )
        value = raw_value.strip()
        if not value or not (
            cls._TURKISH_GROUPED_DECIMAL.fullmatch(value)
            or cls._TURKISH_UNGROUPED_DECIMAL.fullmatch(value)
        ):
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price value has an invalid Turkish decimal format."
            )
        try:
            parsed = Decimal(value.replace(".", "").replace(",", "."))
        except (InvalidOperation, ValueError) as exc:
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price value is malformed."
            ) from exc
        if not parsed.is_finite() or parsed <= 0:
            raise BorsaIstanbulCurrentReferencePricesClientError(
                "BIST current reference-price value must be finite and greater than zero."
            )
        return parsed