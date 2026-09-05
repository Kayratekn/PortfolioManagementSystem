from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status

from src.model.benchmark_price import BenchmarkPrice
from src.model.user import User
from src.repositories.benchmark_price_repository import BenchmarkPriceRepository
from src.repositories.benchmark_repository import BenchmarkRepository
from src.services.fx_conversion_service import FxConversionRate, FxConversionService
from src.services.portfolio_performance_service import (
    PERFORMANCE_STATUS_COMPLETE,
    PERFORMANCE_STATUS_INCOMPLETE,
    PERFORMANCE_STATUS_NOT_APPLICABLE,
    PortfolioPerformanceService,
)


COMPARISON_STATUS_COMPLETE = "COMPLETE"
COMPARISON_STATUS_INCOMPLETE = "INCOMPLETE"
BENCHMARK_STATUS_COMPLETE = "COMPLETE"
BENCHMARK_STATUS_INCOMPLETE = "INCOMPLETE"
BENCHMARK_POINT_STATUS_COMPLETE = "COMPLETE"
BENCHMARK_POINT_STATUS_INCOMPLETE = "INCOMPLETE"

REASON_BENCHMARK_BASELINE_UNAVAILABLE = "BENCHMARK_BASELINE_UNAVAILABLE"
REASON_BENCHMARK_OBSERVATIONS_UNAVAILABLE = "BENCHMARK_OBSERVATIONS_UNAVAILABLE"
REASON_BENCHMARK_BASELINE_FX_UNAVAILABLE = "BENCHMARK_BASELINE_FX_UNAVAILABLE"
REASON_BENCHMARK_FX_UNAVAILABLE = "BENCHMARK_FX_UNAVAILABLE"
REASON_PORTFOLIO_PERFORMANCE_INCOMPLETE = "PORTFOLIO_PERFORMANCE_INCOMPLETE"
REASON_PORTFOLIO_PERFORMANCE_NOT_APPLICABLE = "PORTFOLIO_PERFORMANCE_NOT_APPLICABLE"

DECIMAL_ONE = Decimal("1")
NORMALIZED_BASE_VALUE = Decimal("100")


@dataclass(frozen=True)
class BenchmarkComparisonPortfolioPoint:
    date: date
    cumulative_return: Decimal | None
    normalized_value: Decimal | None
    status: str
    unavailable_reason: str | None


@dataclass(frozen=True)
class BenchmarkComparisonBenchmarkPoint:
    date: date
    close_value: Decimal
    converted_close_value: Decimal | None
    cumulative_return: Decimal | None
    normalized_value: Decimal | None
    fx_rate: Decimal | None
    fx_rate_date: date | None
    status: str
    unavailable_reason: str | None


@dataclass(frozen=True)
class BenchmarkComparisonResult:
    portfolio_id: int
    benchmark_id: int
    benchmark_code: str
    benchmark_name: str
    portfolio_base_currency: str
    benchmark_native_currency: str
    start_date: date
    end_date: date
    status: str
    portfolio_status: str
    benchmark_status: str
    unavailable_reason: str | None
    portfolio_cumulative_return: Decimal | None
    benchmark_cumulative_return: Decimal | None
    excess_return: Decimal | None
    benchmark_baseline_date: date | None
    benchmark_baseline_close_value: Decimal | None
    benchmark_baseline_converted_close_value: Decimal | None
    portfolio_points: tuple[BenchmarkComparisonPortfolioPoint, ...]
    benchmark_points: tuple[BenchmarkComparisonBenchmarkPoint, ...]


@dataclass(frozen=True)
class ConvertedBenchmarkValue:
    converted_close_value: Decimal | None
    fx_rate: Decimal | None
    fx_rate_date: date | None


class BenchmarkComparisonService:
    def __init__(
        self,
        benchmark_repository: BenchmarkRepository,
        benchmark_price_repository: BenchmarkPriceRepository,
        fx_conversion_service: FxConversionService,
        portfolio_performance_service: PortfolioPerformanceService,
    ) -> None:
        self.benchmark_repository = benchmark_repository
        self.benchmark_price_repository = benchmark_price_repository
        self.fx_conversion_service = fx_conversion_service
        self.portfolio_performance_service = portfolio_performance_service

    def get_comparison(
        self,
        *,
        portfolio_id: int,
        benchmark_code: str,
        current_user: User,
        start_date: date,
        end_date: date,
    ) -> BenchmarkComparisonResult:
        performance = self.portfolio_performance_service.get_performance(
            portfolio_id=portfolio_id,
            current_user=current_user,
            start_date=start_date,
            end_date=end_date,
        )

        normalized_code = benchmark_code.strip().upper() if isinstance(benchmark_code, str) else ""
        benchmark = self.benchmark_repository.get_active_by_code(normalized_code)
        if benchmark is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Benchmark not found.",
            )

        portfolio_points = tuple(
            BenchmarkComparisonPortfolioPoint(
                date=point.date,
                cumulative_return=point.cumulative_return,
                normalized_value=self._normalize_return(point.cumulative_return),
                status=point.status,
                unavailable_reason=point.unavailable_reason,
            )
            for point in performance.points
        )

        baseline = self.benchmark_price_repository.get_latest_on_or_before(
            benchmark_id=benchmark.id,
            price_date=start_date - timedelta(days=1),
        )
        observations = self.benchmark_price_repository.list_by_benchmark_between(
            benchmark_id=benchmark.id,
            start_date=start_date,
            end_date=end_date,
        )

        baseline_value: ConvertedBenchmarkValue | None = None
        benchmark_points: tuple[BenchmarkComparisonBenchmarkPoint, ...] = ()
        benchmark_status = BENCHMARK_STATUS_INCOMPLETE
        benchmark_unavailable_reason: str | None = None
        benchmark_cumulative_return: Decimal | None = None

        if baseline is None:
            benchmark_unavailable_reason = REASON_BENCHMARK_BASELINE_UNAVAILABLE
            benchmark_points = tuple(
                self._unusable_benchmark_point(
                    observation,
                    unavailable_reason=REASON_BENCHMARK_BASELINE_UNAVAILABLE,
                )
                for observation in observations
            )
        else:
            baseline_value = self._convert_benchmark_price(
                price=baseline,
                source_currency=benchmark.native_currency,
                target_currency=performance.base_currency,
            )
            if baseline_value.converted_close_value is None:
                benchmark_unavailable_reason = REASON_BENCHMARK_BASELINE_FX_UNAVAILABLE
                benchmark_points = tuple(
                    self._unusable_benchmark_point(
                        observation,
                        unavailable_reason=REASON_BENCHMARK_BASELINE_FX_UNAVAILABLE,
                    )
                    for observation in observations
                )
            elif not observations:
                benchmark_unavailable_reason = REASON_BENCHMARK_OBSERVATIONS_UNAVAILABLE
            else:
                benchmark_points = tuple(
                    self._build_benchmark_point(
                        observation=observation,
                        source_currency=benchmark.native_currency,
                        target_currency=performance.base_currency,
                        converted_baseline=baseline_value.converted_close_value,
                    )
                    for observation in observations
                )
                incomplete_point = next(
                    (
                        point
                        for point in benchmark_points
                        if point.status == BENCHMARK_POINT_STATUS_INCOMPLETE
                    ),
                    None,
                )
                if incomplete_point is None:
                    benchmark_status = BENCHMARK_STATUS_COMPLETE
                    benchmark_cumulative_return = benchmark_points[-1].cumulative_return
                else:
                    benchmark_unavailable_reason = incomplete_point.unavailable_reason

        status_value, unavailable_reason = self._aggregate_status(
            portfolio_status=performance.status,
            benchmark_status=benchmark_status,
            benchmark_unavailable_reason=benchmark_unavailable_reason,
        )
        portfolio_cumulative_return = performance.cumulative_return
        if status_value == COMPARISON_STATUS_COMPLETE:
            excess_return = portfolio_cumulative_return - benchmark_cumulative_return
        else:
            excess_return = None
            if benchmark_status != BENCHMARK_STATUS_COMPLETE:
                benchmark_cumulative_return = None

        return BenchmarkComparisonResult(
            portfolio_id=performance.portfolio_id,
            benchmark_id=benchmark.id,
            benchmark_code=benchmark.code,
            benchmark_name=benchmark.name,
            portfolio_base_currency=performance.base_currency,
            benchmark_native_currency=benchmark.native_currency,
            start_date=start_date,
            end_date=end_date,
            status=status_value,
            portfolio_status=performance.status,
            benchmark_status=benchmark_status,
            unavailable_reason=unavailable_reason,
            portfolio_cumulative_return=portfolio_cumulative_return,
            benchmark_cumulative_return=benchmark_cumulative_return,
            excess_return=excess_return,
            benchmark_baseline_date=baseline.price_date if baseline is not None else None,
            benchmark_baseline_close_value=baseline.close_value if baseline is not None else None,
            benchmark_baseline_converted_close_value=(
                baseline_value.converted_close_value if baseline_value is not None else None
            ),
            portfolio_points=portfolio_points,
            benchmark_points=benchmark_points,
        )

    def _build_benchmark_point(
        self,
        *,
        observation: BenchmarkPrice,
        source_currency: str,
        target_currency: str,
        converted_baseline: Decimal,
    ) -> BenchmarkComparisonBenchmarkPoint:
        converted_value = self._convert_benchmark_price(
            price=observation,
            source_currency=source_currency,
            target_currency=target_currency,
        )
        if converted_value.converted_close_value is None:
            return BenchmarkComparisonBenchmarkPoint(
                date=observation.price_date,
                close_value=observation.close_value,
                converted_close_value=None,
                cumulative_return=None,
                normalized_value=None,
                fx_rate=None,
                fx_rate_date=None,
                status=BENCHMARK_POINT_STATUS_INCOMPLETE,
                unavailable_reason=REASON_BENCHMARK_FX_UNAVAILABLE,
            )

        cumulative_return = converted_value.converted_close_value / converted_baseline - DECIMAL_ONE
        return BenchmarkComparisonBenchmarkPoint(
            date=observation.price_date,
            close_value=observation.close_value,
            converted_close_value=converted_value.converted_close_value,
            cumulative_return=cumulative_return,
            normalized_value=self._normalize_return(cumulative_return),
            fx_rate=converted_value.fx_rate,
            fx_rate_date=converted_value.fx_rate_date,
            status=BENCHMARK_POINT_STATUS_COMPLETE,
            unavailable_reason=None,
        )

    def _convert_benchmark_price(
        self,
        *,
        price: BenchmarkPrice,
        source_currency: str,
        target_currency: str,
    ) -> ConvertedBenchmarkValue:
        if source_currency == target_currency:
            return ConvertedBenchmarkValue(
                converted_close_value=price.close_value,
                fx_rate=None,
                fx_rate_date=None,
            )

        try:
            fx_rate = self.fx_conversion_service.get_rate(
                source_currency=source_currency,
                target_currency=target_currency,
                valuation_date=price.price_date,
            )
        except ValueError:
            return ConvertedBenchmarkValue(
                converted_close_value=None,
                fx_rate=None,
                fx_rate_date=None,
            )
        if fx_rate is None:
            return ConvertedBenchmarkValue(
                converted_close_value=None,
                fx_rate=None,
                fx_rate_date=None,
            )
        self._validate_fx_rate(fx_rate)
        return ConvertedBenchmarkValue(
            converted_close_value=price.close_value * fx_rate.rate,
            fx_rate=fx_rate.rate,
            fx_rate_date=fx_rate.rate_date,
        )

    @staticmethod
    def _validate_fx_rate(fx_rate: FxConversionRate) -> None:
        if not fx_rate.rate.is_finite() or fx_rate.rate <= Decimal("0"):
            raise ValueError("Benchmark FX conversion rate must be finite and greater than 0.")

    @staticmethod
    def _unusable_benchmark_point(
        observation: BenchmarkPrice,
        *,
        unavailable_reason: str,
    ) -> BenchmarkComparisonBenchmarkPoint:
        return BenchmarkComparisonBenchmarkPoint(
            date=observation.price_date,
            close_value=observation.close_value,
            converted_close_value=None,
            cumulative_return=None,
            normalized_value=None,
            fx_rate=None,
            fx_rate_date=None,
            status=BENCHMARK_POINT_STATUS_INCOMPLETE,
            unavailable_reason=unavailable_reason,
        )

    @staticmethod
    def _normalize_return(cumulative_return: Decimal | None) -> Decimal | None:
        if cumulative_return is None:
            return None
        return NORMALIZED_BASE_VALUE * (DECIMAL_ONE + cumulative_return)

    @staticmethod
    def _aggregate_status(
        *,
        portfolio_status: str,
        benchmark_status: str,
        benchmark_unavailable_reason: str | None,
    ) -> tuple[str, str | None]:
        if portfolio_status == PERFORMANCE_STATUS_INCOMPLETE:
            return COMPARISON_STATUS_INCOMPLETE, REASON_PORTFOLIO_PERFORMANCE_INCOMPLETE
        if portfolio_status == PERFORMANCE_STATUS_NOT_APPLICABLE:
            return COMPARISON_STATUS_INCOMPLETE, REASON_PORTFOLIO_PERFORMANCE_NOT_APPLICABLE
        if benchmark_status == BENCHMARK_STATUS_INCOMPLETE:
            return COMPARISON_STATUS_INCOMPLETE, benchmark_unavailable_reason
        if portfolio_status == PERFORMANCE_STATUS_COMPLETE:
            return COMPARISON_STATUS_COMPLETE, None
        return COMPARISON_STATUS_INCOMPLETE, REASON_PORTFOLIO_PERFORMANCE_INCOMPLETE