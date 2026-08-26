from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.model.exchange_rate import ExchangeRate
from src.repositories.exchange_rate_repository import ExchangeRateRepository


SUPPORTED_CURRENCIES = {"TRY", "USD", "EUR", "GBP"}
TCMB_SOURCE = "TCMB"
MIDPOINT_DIVISOR = Decimal("2")


@dataclass(frozen=True)
class FxConversionRate:
    source_currency: str
    target_currency: str
    rate: Decimal
    rate_date: date | None
    rate_kind: str
    source: str


class FxConversionService:
    def __init__(self, exchange_rate_repository: ExchangeRateRepository) -> None:
        self.exchange_rate_repository = exchange_rate_repository

    def get_rate(
        self,
        *,
        source_currency: str,
        target_currency: str,
        valuation_date: date,
    ) -> FxConversionRate | None:
        normalized_source = self._normalize_currency(source_currency, field_name="source_currency")
        normalized_target = self._normalize_currency(target_currency, field_name="target_currency")

        if normalized_source == normalized_target:
            return FxConversionRate(
                source_currency=normalized_source,
                target_currency=normalized_target,
                rate=Decimal("1"),
                rate_date=None,
                rate_kind="IDENTITY",
                source="IDENTITY",
            )

        if normalized_target == "TRY":
            source_rate = self._get_tcmb_try_rate(
                base_currency=normalized_source,
                valuation_date=valuation_date,
            )
            if source_rate is None:
                return None
            midpoint = self._calculate_midpoint(source_rate)
            return self._build_tcmb_result(
                source_currency=normalized_source,
                target_currency=normalized_target,
                rate=midpoint,
                rate_date=source_rate.rate_date,
            )

        if normalized_source == "TRY":
            target_rate = self._get_tcmb_try_rate(
                base_currency=normalized_target,
                valuation_date=valuation_date,
            )
            if target_rate is None:
                return None
            midpoint = self._calculate_midpoint(target_rate)
            return self._build_tcmb_result(
                source_currency=normalized_source,
                target_currency=normalized_target,
                rate=Decimal("1") / midpoint,
                rate_date=target_rate.rate_date,
            )

        source_rate = self._get_tcmb_try_rate(
            base_currency=normalized_source,
            valuation_date=valuation_date,
        )
        target_rate = self._get_tcmb_try_rate(
            base_currency=normalized_target,
            valuation_date=valuation_date,
        )
        if source_rate is None or target_rate is None:
            return None
        if source_rate.rate_date != target_rate.rate_date:
            return None

        source_midpoint = self._calculate_midpoint(source_rate)
        target_midpoint = self._calculate_midpoint(target_rate)
        return self._build_tcmb_result(
            source_currency=normalized_source,
            target_currency=normalized_target,
            rate=source_midpoint / target_midpoint,
            rate_date=source_rate.rate_date,
        )

    @staticmethod
    def _normalize_currency(value: str, *, field_name: str) -> str:
        normalized_value = value.strip().upper() if isinstance(value, str) else ""
        if not normalized_value:
            raise ValueError(f"{field_name} must not be empty.")
        if normalized_value not in SUPPORTED_CURRENCIES:
            raise ValueError(f"Unsupported currency for {field_name}: {normalized_value}")
        return normalized_value

    def _get_tcmb_try_rate(
        self,
        *,
        base_currency: str,
        valuation_date: date,
    ) -> ExchangeRate | None:
        return self.exchange_rate_repository.get_latest_on_or_before(
            base_currency=base_currency,
            quote_currency="TRY",
            rate_date=valuation_date,
            source=TCMB_SOURCE,
        )

    @staticmethod
    def _calculate_midpoint(exchange_rate: ExchangeRate) -> Decimal:
        midpoint = (exchange_rate.forex_buying + exchange_rate.forex_selling) / MIDPOINT_DIVISOR
        if not midpoint.is_finite() or midpoint <= 0:
            raise ValueError("TCMB midpoint conversion rate must be finite and greater than 0.")
        return midpoint

    @staticmethod
    def _build_tcmb_result(
        *,
        source_currency: str,
        target_currency: str,
        rate: Decimal,
        rate_date: date,
    ) -> FxConversionRate:
        if not rate.is_finite() or rate <= 0:
            raise ValueError("FX conversion rate must be finite and greater than 0.")
        return FxConversionRate(
            source_currency=source_currency,
            target_currency=target_currency,
            rate=rate,
            rate_date=rate_date,
            rate_kind="TCMB_MIDPOINT",
            source=TCMB_SOURCE,
        )