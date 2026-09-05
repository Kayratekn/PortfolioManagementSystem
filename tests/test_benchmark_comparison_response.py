from __future__ import annotations

from datetime import date
from decimal import Decimal

from src.response.benchmark_comparison_response import BenchmarkComparisonResponse
from src.services.benchmark_comparison_service import (
    BenchmarkComparisonBenchmarkPoint,
    BenchmarkComparisonPortfolioPoint,
    BenchmarkComparisonResult,
)


def test_benchmark_comparison_response_serializes_decimal_fields_as_strings() -> None:
    response = BenchmarkComparisonResponse.model_validate(
        BenchmarkComparisonResult(
            portfolio_id=1,
            benchmark_id=2,
            benchmark_code="BIST100",
            benchmark_name="BIST 100",
            portfolio_base_currency="TRY",
            benchmark_native_currency="TRY",
            start_date=date(2026, 1, 2),
            end_date=date(2026, 1, 2),
            status="COMPLETE",
            portfolio_status="COMPLETE",
            benchmark_status="COMPLETE",
            unavailable_reason=None,
            portfolio_cumulative_return=Decimal("0.10"),
            benchmark_cumulative_return=Decimal("0.04"),
            excess_return=Decimal("0.06"),
            benchmark_baseline_date=date(2026, 1, 1),
            benchmark_baseline_close_value=Decimal("100"),
            benchmark_baseline_converted_close_value=Decimal("100"),
            portfolio_points=(
                BenchmarkComparisonPortfolioPoint(
                    date=date(2026, 1, 2),
                    cumulative_return=Decimal("0.10"),
                    normalized_value=Decimal("110.00"),
                    status="COMPLETE",
                    unavailable_reason=None,
                ),
            ),
            benchmark_points=(
                BenchmarkComparisonBenchmarkPoint(
                    date=date(2026, 1, 2),
                    close_value=Decimal("104"),
                    converted_close_value=Decimal("104"),
                    cumulative_return=Decimal("0.04"),
                    normalized_value=Decimal("104.00"),
                    fx_rate=None,
                    fx_rate_date=None,
                    status="COMPLETE",
                    unavailable_reason=None,
                ),
            ),
        )
    )

    body = response.model_dump(mode="json")

    assert body["portfolio_cumulative_return"] == "0.10"
    assert body["benchmark_cumulative_return"] == "0.04"
    assert body["excess_return"] == "0.06"
    assert body["portfolio_points"][0]["normalized_value"] == "110.00"
    assert body["benchmark_points"][0]["close_value"] == "104"
    assert body["benchmark_points"][0]["normalized_value"] == "104.00"