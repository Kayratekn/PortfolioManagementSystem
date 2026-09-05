from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BenchmarkComparisonPortfolioPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    cumulative_return: Decimal | None
    normalized_value: Decimal | None
    status: str
    unavailable_reason: str | None


class BenchmarkComparisonBenchmarkPointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    close_value: Decimal
    converted_close_value: Decimal | None
    cumulative_return: Decimal | None
    normalized_value: Decimal | None
    fx_rate: Decimal | None
    fx_rate_date: date | None
    status: str
    unavailable_reason: str | None


class BenchmarkComparisonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    portfolio_points: list[BenchmarkComparisonPortfolioPointResponse]
    benchmark_points: list[BenchmarkComparisonBenchmarkPointResponse]