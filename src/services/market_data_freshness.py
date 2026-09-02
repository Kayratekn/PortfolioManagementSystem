from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class MarketDataFreshnessStatus(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class MarketDataFreshness:
    requested_date: date
    effective_date: date | None
    age_days: int | None
    status: MarketDataFreshnessStatus


def observed_market_data_freshness(
    *,
    requested_date: date,
    effective_date: date | None,
) -> MarketDataFreshness:
    if effective_date is None:
        return unavailable_market_data_freshness(requested_date=requested_date)
    if effective_date > requested_date:
        raise ValueError("Market data effective_date cannot be after requested_date.")
    age_days = (requested_date - effective_date).days
    status = (
        MarketDataFreshnessStatus.CURRENT
        if age_days == 0
        else MarketDataFreshnessStatus.STALE
    )
    return MarketDataFreshness(
        requested_date=requested_date,
        effective_date=effective_date,
        age_days=age_days,
        status=status,
    )


def unavailable_market_data_freshness(*, requested_date: date) -> MarketDataFreshness:
    return MarketDataFreshness(
        requested_date=requested_date,
        effective_date=None,
        age_days=None,
        status=MarketDataFreshnessStatus.UNAVAILABLE,
    )


def not_applicable_market_data_freshness(*, requested_date: date) -> MarketDataFreshness:
    return MarketDataFreshness(
        requested_date=requested_date,
        effective_date=None,
        age_days=None,
        status=MarketDataFreshnessStatus.NOT_APPLICABLE,
    )
