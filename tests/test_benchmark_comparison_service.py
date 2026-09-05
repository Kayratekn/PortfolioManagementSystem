from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.benchmark import Benchmark
from src.model.benchmark_price import BenchmarkPrice
from src.model.user import User
from src.repositories.benchmark_price_repository import BenchmarkPriceRepository
from src.repositories.benchmark_repository import BenchmarkRepository
from src.services.benchmark_comparison_service import (
    REASON_BENCHMARK_BASELINE_FX_UNAVAILABLE,
    REASON_BENCHMARK_BASELINE_UNAVAILABLE,
    REASON_BENCHMARK_FX_UNAVAILABLE,
    REASON_BENCHMARK_OBSERVATIONS_UNAVAILABLE,
    REASON_PORTFOLIO_PERFORMANCE_INCOMPLETE,
    REASON_PORTFOLIO_PERFORMANCE_NOT_APPLICABLE,
    BenchmarkComparisonService,
)
from src.services.fx_conversion_service import FxConversionRate
from src.services.portfolio_performance_service import (
    PERFORMANCE_STATUS_COMPLETE,
    PERFORMANCE_STATUS_INCOMPLETE,
    PERFORMANCE_STATUS_NOT_APPLICABLE,
    PortfolioPerformancePoint,
    PortfolioPerformanceResult,
)


START_DATE = date(2026, 1, 2)
END_DATE = date(2026, 1, 4)


def _user() -> User:
    return User(id=1, email="comparison@example.com", username="comparison")


def _add_benchmark(
    db_session: Session,
    *,
    code: str = "BIST100",
    native_currency: str = "TRY",
    provider_symbol: str = "XU100",
    is_active: bool = True,
) -> Benchmark:
    benchmark = Benchmark(
        code=code,
        name=f"{code} Benchmark",
        benchmark_type="MARKET_INDEX",
        native_currency=native_currency,
        index_owner="VERIFIED_OWNER",
        return_type="PRICE_RETURN",
        provider="VERIFIED_PROVIDER",
        provider_symbol=provider_symbol,
        is_active=is_active,
    )
    db_session.add(benchmark)
    db_session.flush()
    return benchmark


def _add_price(
    db_session: Session,
    *,
    benchmark_id: int,
    price_date: date,
    close_value: Decimal,
) -> BenchmarkPrice:
    price = BenchmarkPrice(
        benchmark_id=benchmark_id,
        price_date=price_date,
        close_value=close_value,
        source="VERIFIED_PROVIDER",
    )
    db_session.add(price)
    db_session.flush()
    return price


def _performance_result(
    *,
    status: str = PERFORMANCE_STATUS_COMPLETE,
    cumulative_return: Decimal | None = Decimal("0.10"),
    base_currency: str = "TRY",
) -> PortfolioPerformanceResult:
    point = PortfolioPerformancePoint(
        date=START_DATE,
        portfolio_value=Decimal("110"),
        external_flow=Decimal("0"),
        daily_return=cumulative_return,
        cumulative_return=cumulative_return,
        status=status,
        unavailable_reason="VALUATION_INCOMPLETE" if status == PERFORMANCE_STATUS_INCOMPLETE else None,
    )
    return PortfolioPerformanceResult(
        portfolio_id=10,
        base_currency=base_currency,
        start_date=START_DATE,
        end_date=END_DATE,
        status=status,
        cumulative_return=cumulative_return if status == PERFORMANCE_STATUS_COMPLETE else None,
        points=(point,),
    )


class FakePortfolioPerformanceService:
    def __init__(self, result: PortfolioPerformanceResult | None = None, exc: Exception | None = None) -> None:
        self.result = result or _performance_result()
        self.exc = exc
        self.calls: list[dict[str, object]] = []

    def get_performance(self, **kwargs) -> PortfolioPerformanceResult:
        self.calls.append(kwargs)
        if self.exc is not None:
            raise self.exc
        return self.result


class FakeFxConversionService:
    def __init__(self, rates: dict[tuple[str, str, date], Decimal]) -> None:
        self.rates = rates
        self.calls: list[tuple[str, str, date]] = []

    def get_rate(
        self,
        *,
        source_currency: str,
        target_currency: str,
        valuation_date: date,
    ) -> FxConversionRate | None:
        self.calls.append((source_currency, target_currency, valuation_date))
        rate = self.rates.get((source_currency, target_currency, valuation_date))
        if rate is None:
            return None
        return FxConversionRate(
            source_currency=source_currency,
            target_currency=target_currency,
            rate=rate,
            rate_date=valuation_date,
            rate_kind="TCMB_MIDPOINT",
            source="TCMB",
        )


def _service(
    db_session: Session,
    *,
    performance: PortfolioPerformanceResult | None = None,
    fx_rates: dict[tuple[str, str, date], Decimal] | None = None,
    performance_exc: Exception | None = None,
) -> tuple[BenchmarkComparisonService, FakePortfolioPerformanceService, FakeFxConversionService]:
    performance_service = FakePortfolioPerformanceService(performance, exc=performance_exc)
    fx_service = FakeFxConversionService(fx_rates or {})
    return (
        BenchmarkComparisonService(
            benchmark_repository=BenchmarkRepository(db_session),
            benchmark_price_repository=BenchmarkPriceRepository(db_session),
            fx_conversion_service=fx_service,  # type: ignore[arg-type]
            portfolio_performance_service=performance_service,  # type: ignore[arg-type]
        ),
        performance_service,
        fx_service,
    )


def test_same_currency_benchmark_uses_actual_observations_and_latest_top_level_return(
    db_session: Session,
) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 2), close_value=Decimal("110"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 4), close_value=Decimal("121"))
    service, _performance_service, fx_service = _service(db_session)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=END_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.portfolio_status == "COMPLETE"
    assert result.benchmark_status == "COMPLETE"
    assert result.benchmark_baseline_date == date(2026, 1, 1)
    assert result.benchmark_baseline_close_value == Decimal("100")
    assert result.benchmark_baseline_converted_close_value == Decimal("100")
    assert [point.date for point in result.benchmark_points] == [date(2026, 1, 2), date(2026, 1, 4)]
    assert result.benchmark_cumulative_return == Decimal("0.21")
    assert result.benchmark_points[-1].normalized_value == Decimal("121.00")
    assert result.portfolio_points[0].normalized_value == Decimal("110.00")
    assert result.excess_return == Decimal("-0.11")
    assert fx_service.calls == []


def test_start_date_market_day_is_not_used_as_hidden_baseline(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=START_DATE, close_value=Decimal("200"))
    service, _performance_service, _fx_service = _service(db_session)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.benchmark_baseline_date == date(2026, 1, 1)
    assert result.benchmark_points[0].cumulative_return == Decimal("1")
    assert result.benchmark_points[0].normalized_value == Decimal("200")


def test_weekend_start_uses_latest_previous_real_baseline_without_synthetic_rows(
    db_session: Session,
) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 2), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 5), close_value=Decimal("105"))
    service, _performance_service, _fx_service = _service(db_session)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=date(2026, 1, 3),
        end_date=date(2026, 1, 5),
    )

    assert result.benchmark_baseline_date == date(2026, 1, 2)
    assert [point.date for point in result.benchmark_points] == [date(2026, 1, 5)]
    assert result.benchmark_points[0].cumulative_return == Decimal("0.05")


def test_foreign_currency_benchmark_converts_baseline_and_observations_with_fx_impact(
    db_session: Session,
) -> None:
    benchmark = _add_benchmark(db_session, native_currency="USD")
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=START_DATE, close_value=Decimal("110"))
    service, _performance_service, fx_service = _service(
        db_session,
        fx_rates={
            ("USD", "TRY", date(2026, 1, 1)): Decimal("10"),
            ("USD", "TRY", START_DATE): Decimal("20"),
        },
    )

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.benchmark_baseline_converted_close_value == Decimal("1000")
    assert result.benchmark_points[0].converted_close_value == Decimal("2200")
    assert result.benchmark_points[0].fx_rate == Decimal("20")
    assert result.benchmark_points[0].fx_rate_date == START_DATE
    assert result.benchmark_cumulative_return == Decimal("1.2")
    assert fx_service.calls == [("USD", "TRY", date(2026, 1, 1)), ("USD", "TRY", START_DATE)]


def test_missing_baseline_makes_benchmark_incomplete(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=START_DATE, close_value=Decimal("110"))
    service, _performance_service, _fx_service = _service(db_session)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.benchmark_status == "INCOMPLETE"
    assert result.unavailable_reason == REASON_BENCHMARK_BASELINE_UNAVAILABLE
    assert result.benchmark_cumulative_return is None
    assert result.excess_return is None
    assert result.benchmark_points[0].unavailable_reason == REASON_BENCHMARK_BASELINE_UNAVAILABLE


def test_no_observations_in_requested_range_makes_benchmark_incomplete(
    db_session: Session,
) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    service, _performance_service, _fx_service = _service(db_session)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.benchmark_status == "INCOMPLETE"
    assert result.unavailable_reason == REASON_BENCHMARK_OBSERVATIONS_UNAVAILABLE
    assert result.benchmark_points == ()


def test_missing_baseline_fx_makes_baseline_unusable(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session, native_currency="USD")
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=START_DATE, close_value=Decimal("110"))
    service, _performance_service, _fx_service = _service(
        db_session,
        fx_rates={("USD", "TRY", START_DATE): Decimal("10")},
    )

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.unavailable_reason == REASON_BENCHMARK_BASELINE_FX_UNAVAILABLE
    assert result.benchmark_baseline_converted_close_value is None
    assert result.benchmark_points[0].status == "INCOMPLETE"


def test_missing_observation_fx_keeps_later_calculable_point_but_overall_incomplete(
    db_session: Session,
) -> None:
    benchmark = _add_benchmark(db_session, native_currency="USD")
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=START_DATE, close_value=Decimal("110"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 3), close_value=Decimal("120"))
    service, _performance_service, _fx_service = _service(
        db_session,
        fx_rates={
            ("USD", "TRY", date(2026, 1, 1)): Decimal("10"),
            ("USD", "TRY", date(2026, 1, 3)): Decimal("10"),
        },
    )

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=date(2026, 1, 3),
    )

    assert result.status == "INCOMPLETE"
    assert result.benchmark_status == "INCOMPLETE"
    assert result.unavailable_reason == REASON_BENCHMARK_FX_UNAVAILABLE
    assert result.benchmark_cumulative_return is None
    assert result.excess_return is None
    assert result.benchmark_points[0].status == "INCOMPLETE"
    assert result.benchmark_points[0].converted_close_value is None
    assert result.benchmark_points[1].status == "COMPLETE"
    assert result.benchmark_points[1].cumulative_return == Decimal("0.2")


@pytest.mark.parametrize(
    ("portfolio_status", "reason"),
    [
        (PERFORMANCE_STATUS_INCOMPLETE, REASON_PORTFOLIO_PERFORMANCE_INCOMPLETE),
        (PERFORMANCE_STATUS_NOT_APPLICABLE, REASON_PORTFOLIO_PERFORMANCE_NOT_APPLICABLE),
    ],
)
def test_portfolio_non_complete_status_is_isolated_from_benchmark_calculation(
    db_session: Session,
    portfolio_status: str,
    reason: str,
) -> None:
    benchmark = _add_benchmark(db_session)
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=START_DATE, close_value=Decimal("110"))
    performance = _performance_result(status=portfolio_status, cumulative_return=None)
    service, _performance_service, _fx_service = _service(db_session, performance=performance)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.portfolio_status == portfolio_status
    assert result.benchmark_status == "COMPLETE"
    assert result.unavailable_reason == reason
    assert result.portfolio_cumulative_return is None
    assert result.benchmark_cumulative_return == Decimal("0.1")
    assert result.excess_return is None


def test_unknown_and_inactive_benchmarks_return_same_404_after_performance_resolution(
    db_session: Session,
) -> None:
    _add_benchmark(db_session, code="INACTIVE", provider_symbol="INACTIVE", is_active=False)
    service, performance_service, _fx_service = _service(db_session)

    with pytest.raises(HTTPException) as missing_exc:
        service.get_comparison(
            portfolio_id=10,
            benchmark_code="UNKNOWN",
            current_user=_user(),
            start_date=START_DATE,
            end_date=START_DATE,
        )
    with pytest.raises(HTTPException) as inactive_exc:
        service.get_comparison(
            portfolio_id=10,
            benchmark_code="INACTIVE",
            current_user=_user(),
            start_date=START_DATE,
            end_date=START_DATE,
        )

    assert missing_exc.value.status_code == 404
    assert missing_exc.value.detail == "Benchmark not found."
    assert inactive_exc.value.status_code == 404
    assert inactive_exc.value.detail == "Benchmark not found."
    assert len(performance_service.calls) == 2


def test_portfolio_ownership_404_happens_before_benchmark_lookup(db_session: Session) -> None:
    service, performance_service, _fx_service = _service(
        db_session,
        performance_exc=HTTPException(status_code=404, detail="Portfolio not found."),
    )

    with pytest.raises(HTTPException) as exc_info:
        service.get_comparison(
            portfolio_id=999,
            benchmark_code="UNKNOWN",
            current_user=_user(),
            start_date=START_DATE,
            end_date=START_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."
    assert len(performance_service.calls) == 1


def test_benchmark_price_isolation_uses_selected_benchmark_only(db_session: Session) -> None:
    selected = _add_benchmark(db_session, code="BIST100", provider_symbol="XU100")
    other = _add_benchmark(db_session, code="SP500", provider_symbol="SPX")
    _add_price(db_session, benchmark_id=selected.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=selected.id, price_date=START_DATE, close_value=Decimal("110"))
    _add_price(db_session, benchmark_id=other.id, price_date=date(2026, 1, 1), close_value=Decimal("1000"))
    _add_price(db_session, benchmark_id=other.id, price_date=START_DATE, close_value=Decimal("2000"))
    service, _performance_service, _fx_service = _service(db_session)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.benchmark_id == selected.id
    assert result.benchmark_points[0].close_value == Decimal("110")
    assert result.benchmark_cumulative_return == Decimal("0.1")

def test_unsupported_benchmark_currency_is_treated_as_missing_fx(db_session: Session) -> None:
    benchmark = _add_benchmark(db_session, native_currency="JPY")
    _add_price(db_session, benchmark_id=benchmark.id, price_date=date(2026, 1, 1), close_value=Decimal("100"))
    _add_price(db_session, benchmark_id=benchmark.id, price_date=START_DATE, close_value=Decimal("110"))
    service, _performance_service, _fx_service = _service(db_session)

    result = service.get_comparison(
        portfolio_id=10,
        benchmark_code="BIST100",
        current_user=_user(),
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.benchmark_status == "INCOMPLETE"
    assert result.unavailable_reason == REASON_BENCHMARK_BASELINE_FX_UNAVAILABLE
    assert result.benchmark_baseline_converted_close_value is None