from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.exchange_rate import ExchangeRate
from src.repositories.exchange_rate_repository import ExchangeRateRepository


def _build_exchange_rate(
    *,
    base_currency: str = "USD",
    quote_currency: str = "TRY",
    rate_date: date = date(2026, 8, 26),
    forex_buying: Decimal = Decimal("40.12345678"),
    forex_selling: Decimal = Decimal("40.87654321"),
    source: str = "TCMB",
) -> ExchangeRate:
    return ExchangeRate(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate_date=rate_date,
        forex_buying=forex_buying,
        forex_selling=forex_selling,
        source=source,
    )


def test_exchange_rate_repository_add_preserves_decimal_values(db_session: Session) -> None:
    repository = ExchangeRateRepository(db_session)
    exchange_rate = _build_exchange_rate(
        forex_buying=Decimal("40.12345678"),
        forex_selling=Decimal("40.87654321"),
    )

    result = repository.add(exchange_rate)

    assert result is exchange_rate
    assert exchange_rate.id is not None
    assert exchange_rate.forex_buying == Decimal("40.12345678")
    assert exchange_rate.forex_selling == Decimal("40.87654321")


def test_exchange_rate_repository_get_by_pair_and_date_returns_matching_row(
    db_session: Session,
) -> None:
    repository = ExchangeRateRepository(db_session)
    exchange_rate = _build_exchange_rate()
    repository.add(exchange_rate)

    result = repository.get_by_pair_and_date(
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 26),
        source="TCMB",
    )

    assert result is not None
    assert result.id == exchange_rate.id


def test_exchange_rate_repository_latest_on_or_before_includes_exact_date(
    db_session: Session,
) -> None:
    repository = ExchangeRateRepository(db_session)
    older_rate = _build_exchange_rate(rate_date=date(2026, 8, 25))
    exact_rate = _build_exchange_rate(rate_date=date(2026, 8, 26))
    repository.add(older_rate)
    repository.add(exact_rate)

    result = repository.get_latest_on_or_before(
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 26),
        source="TCMB",
    )

    assert result is not None
    assert result.id == exact_rate.id


def test_exchange_rate_repository_latest_on_or_before_returns_closest_prior_date(
    db_session: Session,
) -> None:
    repository = ExchangeRateRepository(db_session)
    closest_prior_rate = _build_exchange_rate(rate_date=date(2026, 8, 24))
    older_rate = _build_exchange_rate(rate_date=date(2026, 8, 20))
    future_rate = _build_exchange_rate(rate_date=date(2026, 8, 27))
    repository.add(older_rate)
    repository.add(future_rate)
    repository.add(closest_prior_rate)

    result = repository.get_latest_on_or_before(
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 26),
        source="TCMB",
    )

    assert result is not None
    assert result.id == closest_prior_rate.id


def test_exchange_rate_repository_isolates_different_currency_pairs_and_sources(
    db_session: Session,
) -> None:
    repository = ExchangeRateRepository(db_session)
    matching_rate = _build_exchange_rate(
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 25),
        source="TCMB",
    )
    repository.add(_build_exchange_rate(base_currency="EUR", quote_currency="TRY", source="TCMB"))
    repository.add(_build_exchange_rate(base_currency="USD", quote_currency="EUR", source="TCMB"))
    repository.add(_build_exchange_rate(base_currency="USD", quote_currency="TRY", source="MANUAL"))
    repository.add(matching_rate)

    result = repository.get_latest_on_or_before(
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 26),
        source="TCMB",
    )

    assert result is not None
    assert result.id == matching_rate.id


def test_exchange_rate_repository_missing_observation_returns_none(
    db_session: Session,
) -> None:
    repository = ExchangeRateRepository(db_session)
    repository.add(_build_exchange_rate(rate_date=date(2026, 8, 27)))

    result = repository.get_latest_on_or_before(
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 26),
        source="TCMB",
    )

    assert result is None


def test_exchange_rate_repository_duplicate_unique_key_is_rejected(
    db_session: Session,
) -> None:
    repository = ExchangeRateRepository(db_session)
    repository.add(_build_exchange_rate())

    with pytest.raises(IntegrityError):
        repository.add(_build_exchange_rate())


@pytest.mark.parametrize(
    ("forex_buying", "forex_selling"),
    [
        (Decimal("0"), Decimal("40.87654321")),
        (Decimal("-1.00000000"), Decimal("40.87654321")),
        (Decimal("40.12345678"), Decimal("0")),
        (Decimal("40.12345678"), Decimal("-1.00000000")),
    ],
)
def test_exchange_rate_repository_zero_or_negative_buying_or_selling_is_rejected(
    db_session: Session,
    forex_buying: Decimal,
    forex_selling: Decimal,
) -> None:
    repository = ExchangeRateRepository(db_session)

    with pytest.raises(IntegrityError):
        repository.add(
            _build_exchange_rate(
                forex_buying=forex_buying,
                forex_selling=forex_selling,
            )
        )


def test_exchange_rate_repository_same_base_and_quote_currency_is_rejected(
    db_session: Session,
) -> None:
    repository = ExchangeRateRepository(db_session)

    with pytest.raises(IntegrityError):
        repository.add(
            _build_exchange_rate(
                base_currency="USD",
                quote_currency="USD",
            )
        )