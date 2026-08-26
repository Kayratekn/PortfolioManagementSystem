from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.integrations.tcmb_client import TcmbClientError, TcmbExchangeRateObservation
from src.model.exchange_rate import ExchangeRate
from src.repositories.exchange_rate_repository import ExchangeRateRepository
from src.services.tcmb_sync_service import TcmbSyncService


class FakeTcmbClient:
    def __init__(
        self,
        *,
        current_observations: list[TcmbExchangeRateObservation] | None = None,
        historical_observations: list[TcmbExchangeRateObservation] | None = None,
        current_error: Exception | None = None,
    ) -> None:
        self.current_observations = current_observations or []
        self.historical_observations = historical_observations or []
        self.current_error = current_error
        self.current_call_count = 0
        self.historical_rate_dates: list[date] = []

    def fetch_current_rates(self) -> list[TcmbExchangeRateObservation]:
        self.current_call_count += 1
        if self.current_error is not None:
            raise self.current_error
        return list(self.current_observations)

    def fetch_historical_rates(self, *, rate_date: date) -> list[TcmbExchangeRateObservation]:
        self.historical_rate_dates.append(rate_date)
        return list(self.historical_observations)


def _build_observation(
    *,
    base_currency: str = "USD",
    quote_currency: str = "TRY",
    rate_date: date = date(2026, 8, 25),
    forex_buying: Decimal = Decimal("40.12345678"),
    forex_selling: Decimal = Decimal("40.87654321"),
) -> TcmbExchangeRateObservation:
    return TcmbExchangeRateObservation(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate_date=rate_date,
        forex_buying=forex_buying,
        forex_selling=forex_selling,
    )


def _build_observations(
    *,
    rate_date: date = date(2026, 8, 25),
) -> list[TcmbExchangeRateObservation]:
    return [
        _build_observation(
            base_currency="USD",
            rate_date=rate_date,
            forex_buying=Decimal("40.12345678"),
            forex_selling=Decimal("40.87654321"),
        ),
        _build_observation(
            base_currency="EUR",
            rate_date=rate_date,
            forex_buying=Decimal("47.11111111"),
            forex_selling=Decimal("47.22222222"),
        ),
        _build_observation(
            base_currency="GBP",
            rate_date=rate_date,
            forex_buying=Decimal("54.00678900"),
            forex_selling=Decimal("55.00123400"),
        ),
    ]


def _exchange_rate_count(db_session: Session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(ExchangeRate)) or 0)


def _list_exchange_rates(db_session: Session) -> list[ExchangeRate]:
    return list(
        db_session.scalars(
            select(ExchangeRate).order_by(
                ExchangeRate.base_currency.asc(),
                ExchangeRate.rate_date.asc(),
            )
        )
    )


def test_first_current_sync_inserts_all_observations(db_session: Session) -> None:
    service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=_build_observations()),
    )

    result = service.sync_current_rates()

    persisted_rates = _list_exchange_rates(db_session)

    assert _exchange_rate_count(db_session) == 3
    assert {rate.base_currency for rate in persisted_rates} == {"USD", "EUR", "GBP"}
    assert result.fetched_rows == 3
    assert result.rows_created == 3
    assert result.rows_updated == 0


def test_current_sync_persists_source_decimal_values_and_effective_rate_date(
    db_session: Session,
) -> None:
    service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(
            current_observations=[
                _build_observation(
                    base_currency="USD",
                    rate_date=date(2026, 8, 25),
                    forex_buying=Decimal("40.12345678"),
                    forex_selling=Decimal("40.87654321"),
                )
            ]
        ),
    )

    result = service.sync_current_rates()

    exchange_rate = db_session.scalar(select(ExchangeRate))

    assert exchange_rate is not None
    assert exchange_rate.source == "TCMB"
    assert exchange_rate.base_currency == "USD"
    assert exchange_rate.quote_currency == "TRY"
    assert exchange_rate.rate_date == date(2026, 8, 25)
    assert exchange_rate.forex_buying == Decimal("40.12345678")
    assert exchange_rate.forex_selling == Decimal("40.87654321")
    assert result.fetched_rows == 1
    assert result.rows_created == 1
    assert result.rows_updated == 0


def test_repeated_identical_sync_creates_no_duplicates(db_session: Session) -> None:
    observations = _build_observations()
    service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=observations),
    )

    service.sync_current_rates()
    second_result = service.sync_current_rates()

    assert _exchange_rate_count(db_session) == 3
    assert second_result.fetched_rows == 3
    assert second_result.rows_created == 0
    assert second_result.rows_updated == 0


def test_changed_rate_values_update_existing_rows_instead_of_inserting_duplicates(
    db_session: Session,
) -> None:
    initial_service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=_build_observations()),
    )
    initial_service.sync_current_rates()

    updated_observations = _build_observations()
    updated_observations[0] = _build_observation(
        base_currency="USD",
        rate_date=date(2026, 8, 25),
        forex_buying=Decimal("41.00000000"),
        forex_selling=Decimal("42.00000000"),
    )
    update_service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=updated_observations),
    )

    result = update_service.sync_current_rates()

    usd_rate = db_session.scalar(
        select(ExchangeRate).where(ExchangeRate.base_currency == "USD")
    )

    assert _exchange_rate_count(db_session) == 3
    assert usd_rate is not None
    assert usd_rate.forex_buying == Decimal("41.00000000")
    assert usd_rate.forex_selling == Decimal("42.00000000")
    assert result.fetched_rows == 3
    assert result.rows_created == 0
    assert result.rows_updated == 1


def test_different_dates_create_new_rows(db_session: Session) -> None:
    first_service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=_build_observations(rate_date=date(2026, 8, 25))),
    )
    first_service.sync_current_rates()
    second_service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=_build_observations(rate_date=date(2026, 8, 26))),
    )

    result = second_service.sync_current_rates()

    assert _exchange_rate_count(db_session) == 6
    assert result.fetched_rows == 3
    assert result.rows_created == 3
    assert result.rows_updated == 0


def test_historical_sync_calls_historical_client_method_with_requested_date(
    db_session: Session,
) -> None:
    fake_client = FakeTcmbClient(
        historical_observations=_build_observations(rate_date=date(2026, 8, 25)),
    )
    service = TcmbSyncService(db_session, tcmb_client=fake_client)

    result = service.sync_historical_rates(rate_date=date(2026, 8, 26))

    assert fake_client.historical_rate_dates == [date(2026, 8, 26)]
    assert fake_client.current_call_count == 0
    assert result.fetched_rows == 3
    assert result.rows_created == 3
    assert result.rows_updated == 0


def test_historical_sync_persists_observation_effective_date_not_requested_date(
    db_session: Session,
) -> None:
    service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(
            historical_observations=[
                _build_observation(
                    base_currency="USD",
                    rate_date=date(2026, 8, 25),
                )
            ]
        ),
    )

    service.sync_historical_rates(rate_date=date(2026, 8, 26))

    exchange_rate = db_session.scalar(select(ExchangeRate))

    assert exchange_rate is not None
    assert exchange_rate.rate_date == date(2026, 8, 25)


def test_empty_observation_list_changes_nothing(db_session: Session) -> None:
    service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=[]),
    )

    result = service.sync_current_rates()

    assert _exchange_rate_count(db_session) == 0
    assert result.fetched_rows == 0
    assert result.rows_created == 0
    assert result.rows_updated == 0


def test_processing_failure_rolls_back_complete_batch(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_add = ExchangeRateRepository.add

    def failing_add(
        self: ExchangeRateRepository,
        exchange_rate: ExchangeRate,
    ) -> ExchangeRate:
        if exchange_rate.base_currency == "GBP":
            raise RuntimeError("exchange rate add failed")
        return original_add(self, exchange_rate)

    monkeypatch.setattr(ExchangeRateRepository, "add", failing_add)
    service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_observations=_build_observations()),
    )

    with pytest.raises(RuntimeError, match="exchange rate add failed"):
        service.sync_current_rates()

    db_session.expire_all()

    assert _exchange_rate_count(db_session) == 0


def test_client_error_is_not_swallowed(db_session: Session) -> None:
    service = TcmbSyncService(
        db_session,
        tcmb_client=FakeTcmbClient(current_error=TcmbClientError("TCMB unavailable")),
    )

    with pytest.raises(TcmbClientError, match="TCMB unavailable"):
        service.sync_current_rates()

    assert _exchange_rate_count(db_session) == 0