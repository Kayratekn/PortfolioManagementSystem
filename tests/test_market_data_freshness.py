from __future__ import annotations

from datetime import date

import pytest

from src.services.market_data_freshness import (
    not_applicable_market_data_freshness,
    observed_market_data_freshness,
    unavailable_market_data_freshness,
)


def test_exact_date_observation_is_current() -> None:
    freshness = observed_market_data_freshness(
        requested_date=date(2026, 8, 26),
        effective_date=date(2026, 8, 26),
    )

    assert freshness.requested_date == date(2026, 8, 26)
    assert freshness.effective_date == date(2026, 8, 26)
    assert freshness.age_days == 0
    assert freshness.status == "CURRENT"


def test_older_observation_is_stale_with_age_days() -> None:
    freshness = observed_market_data_freshness(
        requested_date=date(2026, 8, 26),
        effective_date=date(2026, 8, 23),
    )

    assert freshness.effective_date == date(2026, 8, 23)
    assert freshness.age_days == 3
    assert freshness.status == "STALE"


def test_missing_observation_is_unavailable() -> None:
    freshness = unavailable_market_data_freshness(
        requested_date=date(2026, 8, 26),
    )

    assert freshness.requested_date == date(2026, 8, 26)
    assert freshness.effective_date is None
    assert freshness.age_days is None
    assert freshness.status == "UNAVAILABLE"


def test_identity_fx_is_not_applicable() -> None:
    freshness = not_applicable_market_data_freshness(
        requested_date=date(2026, 8, 26),
    )

    assert freshness.requested_date == date(2026, 8, 26)
    assert freshness.effective_date is None
    assert freshness.age_days is None
    assert freshness.status == "NOT_APPLICABLE"


def test_future_effective_date_raises_value_error() -> None:
    with pytest.raises(ValueError, match="effective_date cannot be after requested_date"):
        observed_market_data_freshness(
            requested_date=date(2026, 8, 26),
            effective_date=date(2026, 8, 27),
        )
