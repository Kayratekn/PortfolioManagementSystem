from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.benchmark import Benchmark
from src.model.benchmark_price import BenchmarkPrice
from src.repositories.benchmark_price_repository import BenchmarkPriceRepository
from src.repositories.benchmark_repository import BenchmarkRepository


def _build_benchmark(
    *,
    code: str = "BIST100",
    name: str = "BIST 100",
    benchmark_type: str = "MARKET_INDEX",
    native_currency: str = "TRY",
    provider: str = "VERIFIED_PROVIDER",
    provider_symbol: str = "XU100",
    is_active: bool = True,
) -> Benchmark:
    return Benchmark(
        code=code,
        name=name,
        benchmark_type=benchmark_type,
        native_currency=native_currency,
        provider=provider,
        provider_symbol=provider_symbol,
        is_active=is_active,
    )


def _build_benchmark_price(
    *,
    benchmark_id: int,
    price_date: date = date(2026, 1, 2),
    close_value: Decimal = Decimal("12345.67891234"),
    source: str = "VERIFIED_PROVIDER",
) -> BenchmarkPrice:
    return BenchmarkPrice(
        benchmark_id=benchmark_id,
        price_date=price_date,
        close_value=close_value,
        source=source,
    )


def test_benchmark_repository_add_get_by_id_and_get_by_code(db_session: Session) -> None:
    repository = BenchmarkRepository(db_session)
    benchmark = _build_benchmark()

    result = repository.add(benchmark)

    assert result is benchmark
    assert benchmark.id is not None
    assert repository.get_by_id(benchmark.id) is benchmark
    assert repository.get_by_code("BIST100") is benchmark
    assert repository.get_by_code("UNKNOWN") is None


def test_benchmark_repository_list_active_is_deterministic_and_excludes_inactive(
    db_session: Session,
) -> None:
    repository = BenchmarkRepository(db_session)
    repository.add(
        _build_benchmark(
            code="Z_INDEX",
            name="Z Index",
            provider_symbol="Z",
        )
    )
    repository.add(
        _build_benchmark(
            code="A_INDEX",
            name="A Index",
            provider_symbol="A",
        )
    )
    repository.add(
        _build_benchmark(
            code="M_INACTIVE",
            name="Inactive Index",
            provider_symbol="M",
            is_active=False,
        )
    )

    result = repository.list_active()

    assert [benchmark.code for benchmark in result] == ["A_INDEX", "Z_INDEX"]


def test_benchmark_price_repository_add_preserves_decimal_value(db_session: Session) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    repository = BenchmarkPriceRepository(db_session)
    benchmark_price = _build_benchmark_price(
        benchmark_id=benchmark.id,
        close_value=Decimal("12345.67891234"),
    )

    result = repository.add(benchmark_price)

    assert result is benchmark_price
    assert benchmark_price.id is not None
    assert benchmark_price.close_value == Decimal("12345.67891234")
    assert isinstance(benchmark_price.close_value, Decimal)


def test_benchmark_price_unique_benchmark_date_ignores_source(db_session: Session) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    repository = BenchmarkPriceRepository(db_session)
    repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 2),
            source="SOURCE_A",
        )
    )

    with pytest.raises(IntegrityError):
        repository.add(
            _build_benchmark_price(
                benchmark_id=benchmark.id,
                price_date=date(2026, 1, 2),
                source="SOURCE_B",
            )
        )


def test_benchmark_price_foreign_key_rejects_missing_benchmark(db_session: Session) -> None:
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    repository = BenchmarkPriceRepository(db_session)

    with pytest.raises(IntegrityError):
        repository.add(_build_benchmark_price(benchmark_id=999999))


def test_benchmark_price_repository_get_exact_date(db_session: Session) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    repository = BenchmarkPriceRepository(db_session)
    matching_price = repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 2),
        )
    )
    repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 3),
        )
    )

    result = repository.get_by_benchmark_and_date(
        benchmark_id=benchmark.id,
        price_date=date(2026, 1, 2),
    )

    assert result is matching_price
    assert repository.get_by_benchmark_and_date(
        benchmark_id=benchmark.id,
        price_date=date(2026, 1, 4),
    ) is None


def test_benchmark_price_repository_lookups_isolate_overlapping_benchmark_dates(
    db_session: Session,
) -> None:
    benchmark_repository = BenchmarkRepository(db_session)
    first_benchmark = benchmark_repository.add(
        _build_benchmark(
            code="FIRST",
            name="First Benchmark",
            provider_symbol="FIRST",
        )
    )
    second_benchmark = benchmark_repository.add(
        _build_benchmark(
            code="SECOND",
            name="Second Benchmark",
            provider_symbol="SECOND",
        )
    )
    repository = BenchmarkPriceRepository(db_session)
    first_early = repository.add(
        _build_benchmark_price(
            benchmark_id=first_benchmark.id,
            price_date=date(2026, 1, 2),
            close_value=Decimal("100"),
        )
    )
    first_later = repository.add(
        _build_benchmark_price(
            benchmark_id=first_benchmark.id,
            price_date=date(2026, 1, 4),
            close_value=Decimal("104"),
        )
    )
    second_same_day = repository.add(
        _build_benchmark_price(
            benchmark_id=second_benchmark.id,
            price_date=date(2026, 1, 2),
            close_value=Decimal("200"),
        )
    )
    second_later = repository.add(
        _build_benchmark_price(
            benchmark_id=second_benchmark.id,
            price_date=date(2026, 1, 3),
            close_value=Decimal("203"),
        )
    )

    exact_result = repository.get_by_benchmark_and_date(
        benchmark_id=first_benchmark.id,
        price_date=date(2026, 1, 2),
    )
    range_result = repository.list_by_benchmark_between(
        benchmark_id=first_benchmark.id,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 4),
    )
    latest_result = repository.get_latest_on_or_before(
        benchmark_id=first_benchmark.id,
        price_date=date(2026, 1, 3),
    )

    assert exact_result is first_early
    assert exact_result is not second_same_day
    assert range_result == [first_early, first_later]
    assert second_same_day not in range_result
    assert second_later not in range_result
    assert latest_result is first_early
    assert latest_result is not second_later


def test_benchmark_price_repository_list_range_is_ordered_by_date_then_id(
    db_session: Session,
) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    repository = BenchmarkPriceRepository(db_session)
    outside_price = repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 1),
        )
    )
    later_price = repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 4),
        )
    )
    earlier_price = repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 2),
        )
    )

    result = repository.list_by_benchmark_between(
        benchmark_id=benchmark.id,
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 4),
    )

    assert result == [earlier_price, later_price]
    assert outside_price not in result


def test_benchmark_price_repository_latest_on_or_before_includes_exact_date(
    db_session: Session,
) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    repository = BenchmarkPriceRepository(db_session)
    repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 1),
        )
    )
    exact_price = repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 2),
        )
    )

    result = repository.get_latest_on_or_before(
        benchmark_id=benchmark.id,
        price_date=date(2026, 1, 2),
    )

    assert result is exact_price


def test_benchmark_price_repository_latest_on_or_before_never_returns_future_price(
    db_session: Session,
) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    repository = BenchmarkPriceRepository(db_session)
    closest_prior_price = repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 2),
        )
    )
    future_price = repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 4),
        )
    )

    result = repository.get_latest_on_or_before(
        benchmark_id=benchmark.id,
        price_date=date(2026, 1, 3),
    )

    assert result is closest_prior_price
    assert result is not future_price


def test_benchmark_price_repository_missing_historical_price_returns_none(
    db_session: Session,
) -> None:
    benchmark = BenchmarkRepository(db_session).add(_build_benchmark())
    repository = BenchmarkPriceRepository(db_session)
    repository.add(
        _build_benchmark_price(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 4),
        )
    )

    result = repository.get_latest_on_or_before(
        benchmark_id=benchmark.id,
        price_date=date(2026, 1, 3),
    )

    assert result is None
