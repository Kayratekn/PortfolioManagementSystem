from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.model.exchange_rate import ExchangeRate
from src.repositories.exchange_rate_repository import ExchangeRateRepository
from src.services.fx_conversion_service import FxConversionService


VALUATION_DATE = date(2026, 8, 26)


class TrackingExchangeRateRepository:
    def __init__(self, result: ExchangeRate | None = None) -> None:
        self.result = result
        self.calls: list[dict[str, object]] = []

    def get_latest_on_or_before(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        rate_date: date,
        source: str,
    ) -> ExchangeRate | None:
        self.calls.append(
            {
                "base_currency": base_currency,
                "quote_currency": quote_currency,
                "rate_date": rate_date,
                "source": source,
            }
        )
        return self.result


def _build_exchange_rate(
    *,
    base_currency: str = "USD",
    quote_currency: str = "TRY",
    rate_date: date = date(2026, 8, 25),
    forex_buying: Decimal = Decimal("40.00000000"),
    forex_selling: Decimal = Decimal("42.00000000"),
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


def _add_exchange_rate(
    db_session: Session,
    *,
    base_currency: str = "USD",
    quote_currency: str = "TRY",
    rate_date: date = date(2026, 8, 25),
    forex_buying: Decimal = Decimal("40.00000000"),
    forex_selling: Decimal = Decimal("42.00000000"),
    source: str = "TCMB",
) -> ExchangeRate:
    exchange_rate = _build_exchange_rate(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate_date=rate_date,
        forex_buying=forex_buying,
        forex_selling=forex_selling,
        source=source,
    )
    db_session.add(exchange_rate)
    db_session.flush()
    return exchange_rate


def _create_service(db_session: Session) -> FxConversionService:
    return FxConversionService(ExchangeRateRepository(db_session))


def test_same_currency_returns_decimal_one_and_does_not_query_repository() -> None:
    repository = TrackingExchangeRateRepository()
    service = FxConversionService(repository)  # type: ignore[arg-type]

    result = service.get_rate(
        source_currency="TRY",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.source_currency == "TRY"
    assert result.target_currency == "TRY"
    assert result.rate == Decimal("1")
    assert result.rate_date is None
    assert result.rate_kind == "IDENTITY"
    assert result.source == "IDENTITY"
    assert repository.calls == []


def test_lowercase_and_whitespace_currencies_normalize_correctly(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="USD")
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency=" usd ",
        target_currency=" try ",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.source_currency == "USD"
    assert result.target_currency == "TRY"
    assert result.rate == Decimal("41.00000000")


@pytest.mark.parametrize("source_currency", ["", "   ", "CHF"])
def test_unsupported_or_empty_source_currency_is_rejected(source_currency: str) -> None:
    service = FxConversionService(TrackingExchangeRateRepository())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="source_currency"):
        service.get_rate(
            source_currency=source_currency,
            target_currency="TRY",
            valuation_date=VALUATION_DATE,
        )


@pytest.mark.parametrize("target_currency", ["", "   ", "CHF"])
def test_unsupported_or_empty_target_currency_is_rejected(target_currency: str) -> None:
    service = FxConversionService(TrackingExchangeRateRepository())  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="target_currency"):
        service.get_rate(
            source_currency="USD",
            target_currency=target_currency,
            valuation_date=VALUATION_DATE,
        )


def test_usd_to_try_uses_tcmb_midpoint(db_session: Session) -> None:
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        forex_buying=Decimal("40.00000000"),
        forex_selling=Decimal("42.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.rate == Decimal("41.00000000")
    assert result.rate_date == date(2026, 8, 25)
    assert result.rate_kind == "TCMB_MIDPOINT"
    assert result.source == "TCMB"


def test_eur_to_try_uses_midpoint(db_session: Session) -> None:
    _add_exchange_rate(
        db_session,
        base_currency="EUR",
        forex_buying=Decimal("47.11111111"),
        forex_selling=Decimal("47.22222222"),
    )
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="EUR",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.rate == Decimal("47.166666665")


def test_try_to_usd_uses_inverse_midpoint(db_session: Session) -> None:
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        forex_buying=Decimal("40.00000000"),
        forex_selling=Decimal("42.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="TRY",
        target_currency="USD",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.rate == Decimal("1") / Decimal("41.00000000")
    assert result.rate_date == date(2026, 8, 25)
    assert result.rate_kind == "TCMB_MIDPOINT"
    assert result.source == "TCMB"


def test_foreign_to_try_uses_latest_on_or_before_valuation_date(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="USD", rate_date=date(2026, 8, 20), forex_buying=Decimal("38"), forex_selling=Decimal("40"))
    _add_exchange_rate(db_session, base_currency="USD", rate_date=date(2026, 8, 25), forex_buying=Decimal("40"), forex_selling=Decimal("42"))
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.rate == Decimal("41.00000000")
    assert result.rate_date == date(2026, 8, 25)


def test_future_rate_is_not_used(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="USD", rate_date=date(2026, 8, 27))
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is None


def test_missing_direct_rate_returns_none(db_session: Session) -> None:
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is None


def test_usd_to_eur_cross_conversion_uses_source_midpoint_over_target_midpoint(
    db_session: Session,
) -> None:
    _add_exchange_rate(db_session, base_currency="USD", forex_buying=Decimal("40"), forex_selling=Decimal("42"))
    _add_exchange_rate(db_session, base_currency="EUR", forex_buying=Decimal("50"), forex_selling=Decimal("52"))
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="EUR",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.rate == Decimal("41") / Decimal("51")
    assert result.rate_date == date(2026, 8, 25)
    assert result.rate_kind == "TCMB_MIDPOINT"
    assert result.source == "TCMB"


def test_eur_to_gbp_cross_conversion_works(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="EUR", forex_buying=Decimal("48"), forex_selling=Decimal("50"))
    _add_exchange_rate(db_session, base_currency="GBP", forex_buying=Decimal("56"), forex_selling=Decimal("58"))
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="EUR",
        target_currency="GBP",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.rate == Decimal("49") / Decimal("57")
    assert result.rate_date == date(2026, 8, 25)


def test_cross_conversion_requires_matching_effective_dates(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="USD", rate_date=date(2026, 8, 25))
    _add_exchange_rate(db_session, base_currency="EUR", rate_date=date(2026, 8, 24))
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="EUR",
        valuation_date=VALUATION_DATE,
    )

    assert result is None


def test_missing_source_cross_leg_returns_none(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="EUR")
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="EUR",
        valuation_date=VALUATION_DATE,
    )

    assert result is None


def test_missing_target_cross_leg_returns_none(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="USD")
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="EUR",
        valuation_date=VALUATION_DATE,
    )

    assert result is None


def test_source_isolation_non_tcmb_data_is_not_used(db_session: Session) -> None:
    _add_exchange_rate(db_session, base_currency="USD", source="MANUAL")
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is None


def test_decimal_arithmetic_is_preserved_without_float_or_rounding(db_session: Session) -> None:
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        forex_buying=Decimal("40.12345678"),
        forex_selling=Decimal("40.87654321"),
    )
    service = _create_service(db_session)

    result = service.get_rate(
        source_currency="USD",
        target_currency="TRY",
        valuation_date=VALUATION_DATE,
    )

    assert result is not None
    assert result.rate == (Decimal("40.12345678") + Decimal("40.87654321")) / Decimal("2")
    assert isinstance(result.rate, Decimal)


@pytest.mark.parametrize(
    "exchange_rate",
    [
        _build_exchange_rate(forex_buying=Decimal("0"), forex_selling=Decimal("0")),
        _build_exchange_rate(forex_buying=Decimal("-2"), forex_selling=Decimal("1")),
        _build_exchange_rate(forex_buying=Decimal("NaN"), forex_selling=Decimal("1")),
    ],
)
def test_non_positive_or_invalid_stored_midpoint_is_rejected(exchange_rate: ExchangeRate) -> None:
    repository = TrackingExchangeRateRepository(result=exchange_rate)
    service = FxConversionService(repository)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="midpoint"):
        service.get_rate(
            source_currency="USD",
            target_currency="TRY",
            valuation_date=VALUATION_DATE,
        )