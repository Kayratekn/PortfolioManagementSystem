from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from src.config.supported_benchmarks import BIST100_BENCHMARK
from src.model.benchmark import Benchmark
from src.model.benchmark_price import BenchmarkPrice
import src.services.benchmark_daily_sync_service as daily_sync_module
from src.services.benchmark_daily_sync_service import (
    YAHOO_FINANCE_DAILY_CLOSE_SOURCE,
    BenchmarkDailySyncService,
)
from src.services.benchmark_price_import_parser import BenchmarkPriceObservation
from src.services.benchmark_price_import_service import BenchmarkPriceImportResult


class FakeYahooClient:
    def __init__(self, observations: list[BenchmarkPriceObservation] | None = None) -> None:
        self.observations = observations or []
        self.calls: list[dict[str, object]] = []

    def fetch_daily_close(self, **kwargs: object) -> list[BenchmarkPriceObservation]:
        self.calls.append(kwargs)
        return self.observations


def _add_benchmark(db_session: Session, *, code: str = "BIST100", is_active: bool = True) -> Benchmark:
    benchmark = Benchmark(
        code=code,
        name=BIST100_BENCHMARK.name,
        benchmark_type=BIST100_BENCHMARK.benchmark_type,
        native_currency=BIST100_BENCHMARK.native_currency,
        index_owner=BIST100_BENCHMARK.index_owner,
        return_type=BIST100_BENCHMARK.return_type,
        provider=BIST100_BENCHMARK.provider,
        provider_symbol=BIST100_BENCHMARK.provider_symbol,
        is_active=is_active,
    )
    db_session.add(benchmark)
    db_session.commit()
    return benchmark


def _add_price(
    db_session: Session,
    *,
    benchmark_id: int,
    price_date: date,
    close_value: Decimal = Decimal("100.00000000"),
    source: str = "BOOTSTRAP",
) -> BenchmarkPrice:
    price = BenchmarkPrice(
        benchmark_id=benchmark_id,
        price_date=price_date,
        close_value=close_value,
        source=source,
    )
    db_session.add(price)
    db_session.commit()
    return price


def _prices(db_session: Session) -> list[BenchmarkPrice]:
    return db_session.query(BenchmarkPrice).order_by(BenchmarkPrice.price_date).all()


def test_sync_fetches_from_latest_persisted_date_plus_one(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 1))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    client = FakeYahooClient(
        [BenchmarkPriceObservation(date(2026, 9, 4), Decimal("104.00000000"))]
    )

    result = BenchmarkDailySyncService(db_session, client=client).sync(
        benchmark_code="BIST100",
        reference_date=date(2026, 9, 5),
    )

    assert client.calls == [
        {
            "symbol": "XU100.IS",
            "start_date": date(2026, 9, 4),
            "end_date": date(2026, 9, 5),
        }
    ]
    assert result.start_date == date(2026, 9, 4)
    assert result.end_date == date(2026, 9, 5)
    assert result.rows_created == 1
    assert _prices(db_session)[-1].source == YAHOO_FINANCE_DAILY_CLOSE_SOURCE


@pytest.mark.parametrize("reference_date", [date(2026, 9, 4), date(2026, 9, 3)])
def test_sync_noops_when_start_date_is_on_or_after_reference_date(
    db_session: Session,
    reference_date: date,
) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    client = FakeYahooClient()

    result = BenchmarkDailySyncService(db_session, client=client).sync(
        benchmark_code="BIST100",
        reference_date=reference_date,
    )

    assert client.calls == []
    assert result.fetched_rows == 0
    assert result.rows_created == 0
    assert len(_prices(db_session)) == 1


def test_sync_requires_historical_bootstrap_when_no_price_history(db_session: Session) -> None:
    _add_benchmark(db_session)

    with pytest.raises(ValueError, match="historical bootstrap is required"):
        BenchmarkDailySyncService(db_session, client=FakeYahooClient()).sync(
            benchmark_code="BIST100",
            reference_date=date(2026, 9, 5),
        )


def test_sync_empty_provider_result_is_valid_noop(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))

    result = BenchmarkDailySyncService(db_session, client=FakeYahooClient()).sync(
        benchmark_code="BIST100",
        reference_date=date(2026, 9, 5),
    )

    assert result.fetched_rows == 0
    assert result.rows_created == 0
    assert len(_prices(db_session)) == 1


@pytest.mark.parametrize("price_date", [date(2026, 9, 3), date(2026, 9, 5)])
def test_sync_rejects_provider_observations_outside_requested_range_before_import(
    db_session: Session,
    price_date: date,
) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    client = FakeYahooClient(
        [BenchmarkPriceObservation(price_date, Decimal("105.00000000"))]
    )

    with pytest.raises(ValueError, match="outside requested range"):
        BenchmarkDailySyncService(db_session, client=client).sync(
            benchmark_code="BIST100",
            reference_date=date(2026, 9, 5),
        )

    assert len(_prices(db_session)) == 1


def test_sync_rejects_non_decimal_provider_close_before_import(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    client = FakeYahooClient(
        [BenchmarkPriceObservation(date(2026, 9, 4), 105.0)]  # type: ignore[arg-type]
    )

    with pytest.raises(ValueError, match="must be Decimal before import"):
        BenchmarkDailySyncService(db_session, client=client).sync(
            benchmark_code="BIST100",
            reference_date=date(2026, 9, 5),
        )

    assert len(_prices(db_session)) == 1


def test_sync_validates_complete_provider_batch_before_mutating_history(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    client = FakeYahooClient(
        [
            BenchmarkPriceObservation(date(2026, 9, 4), Decimal("104.00000000")),
            BenchmarkPriceObservation(date(2026, 9, 5), Decimal("105.00000000")),
        ]
    )

    with pytest.raises(ValueError, match="outside requested range"):
        BenchmarkDailySyncService(db_session, client=client).sync(
            benchmark_code="BIST100",
            reference_date=date(2026, 9, 5),
        )

    assert [price.price_date for price in _prices(db_session)] == [date(2026, 9, 3)]


def test_sync_does_not_fabricate_missing_weekend_or_holiday_dates(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    client = FakeYahooClient(
        [
            BenchmarkPriceObservation(date(2026, 9, 4), Decimal("104.00000000")),
            BenchmarkPriceObservation(date(2026, 9, 8), Decimal("108.00000000")),
        ]
    )

    BenchmarkDailySyncService(db_session, client=client).sync(
        benchmark_code="BIST100",
        reference_date=date(2026, 9, 9),
    )

    assert [price.price_date for price in _prices(db_session)] == [
        date(2026, 9, 3),
        date(2026, 9, 4),
        date(2026, 9, 8),
    ]


def test_sync_is_idempotent_and_does_not_auto_revise_existing_history(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    client = FakeYahooClient(
        [BenchmarkPriceObservation(date(2026, 9, 4), Decimal("104.00000000"))]
    )
    service = BenchmarkDailySyncService(db_session, client=client)

    first = service.sync(benchmark_code="BIST100", reference_date=date(2026, 9, 5))
    second = service.sync(benchmark_code="BIST100", reference_date=date(2026, 9, 5))

    assert first.rows_created == 1
    assert second.rows_created == 0
    assert len(_prices(db_session)) == 2


def test_sync_calls_importer_with_reference_date_cutoff_and_revisions_disabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 9, 3))
    observations = [BenchmarkPriceObservation(date(2026, 9, 4), Decimal("104.00000000"))]
    client = FakeYahooClient(observations)
    calls: list[dict[str, object]] = []

    class FakeImportService:
        def __init__(self, db: Session, *, today: date | None = None) -> None:
            calls.append({"db": db, "today": today})

        def import_observations(self, **kwargs: object) -> BenchmarkPriceImportResult:
            calls.append(kwargs)
            return BenchmarkPriceImportResult(fetched_rows=1, rows_created=1, rows_updated=0)

    monkeypatch.setattr(daily_sync_module, "BenchmarkPriceImportService", FakeImportService)

    BenchmarkDailySyncService(db_session, client=client).sync(
        benchmark_code="BIST100",
        reference_date=date(2026, 9, 5),
    )

    assert calls[0] == {"db": db_session, "today": date(2026, 9, 5)}
    assert calls[1]["benchmark_code"] == "BIST100"
    assert calls[1]["source"] == YAHOO_FINANCE_DAILY_CLOSE_SOURCE
    assert calls[1]["observations"] == observations
    assert calls[1]["allow_revisions"] is False


def test_sync_rejects_unsupported_code(db_session: Session) -> None:
    with pytest.raises(ValueError, match="Unsupported benchmark code"):
        BenchmarkDailySyncService(db_session, client=FakeYahooClient()).sync(
            benchmark_code="UNKNOWN",
            reference_date=date(2026, 9, 5),
        )
