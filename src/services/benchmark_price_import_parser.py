from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any


BENCHMARK_CLOSE_SCALE = Decimal("0.00000001")


@dataclass(frozen=True)
class BenchmarkPriceObservation:
    price_date: date
    close_value: Decimal


def parse_benchmark_price_rows(rows: list[dict[str, Any]]) -> list[BenchmarkPriceObservation]:
    observations_by_date: dict[date, BenchmarkPriceObservation] = {}

    for row in rows:
        observation = parse_benchmark_price_row(row)
        existing_observation = observations_by_date.get(observation.price_date)
        if existing_observation is None:
            observations_by_date[observation.price_date] = observation
            continue
        if existing_observation.close_value != observation.close_value:
            raise ValueError(
                "Conflicting benchmark close values for "
                f"date={observation.price_date.isoformat()}."
            )

    return [observations_by_date[price_date] for price_date in sorted(observations_by_date)]


def parse_benchmark_price_row(row: dict[str, Any]) -> BenchmarkPriceObservation:
    return BenchmarkPriceObservation(
        price_date=_parse_date(row.get("date")),
        close_value=_parse_close(row.get("close")),
    )


def _parse_date(value: Any) -> date:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Benchmark price date must be a nonblank ISO date string.")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"Invalid benchmark price date: {value}") from exc


def _parse_close(value: Any) -> Decimal:
    if isinstance(value, float):
        raise ValueError("Benchmark close value must not be supplied as a float.")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Benchmark close value must be a nonblank Decimal string.")
    try:
        close_value = Decimal(value.strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid benchmark close value: {value}") from exc
    if not close_value.is_finite() or close_value <= Decimal("0"):
        raise ValueError("Benchmark close value must be greater than zero.")
    if close_value.quantize(BENCHMARK_CLOSE_SCALE) != close_value:
        raise ValueError("Benchmark close value must fit NUMERIC(20,8) without rounding.")
    return close_value