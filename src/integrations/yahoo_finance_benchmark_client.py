from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from src.services.benchmark_price_import_parser import BenchmarkPriceObservation


BENCHMARK_CLOSE_SCALE = Decimal("0.00000001")


class YahooFinanceBenchmarkClient:
    def fetch_daily_close(
        self,
        *,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[BenchmarkPriceObservation]:
        import yfinance as yf

        data = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_date,
            interval="1d",
            auto_adjust=False,
            progress=False,
        )
        if getattr(data, "empty", False):
            return []

        close_values = self._close_values(data, symbol=symbol)
        observations: list[BenchmarkPriceObservation] = []
        for raw_date, raw_close in close_values.items():
            price_date = self._to_date(raw_date)
            close_value = self._canonical_close(raw_close)
            observations.append(BenchmarkPriceObservation(price_date, close_value))

        return sorted(observations, key=lambda observation: observation.price_date)

    def _close_values(self, data: Any, *, symbol: str) -> Any:
        try:
            close_values = data["Close"]
        except Exception as exc:
            close_values = self._cross_section(data, "Close")
            if close_values is None:
                raise ValueError("Yahoo Finance response is missing Close values.") from exc

        return self._single_close_series(close_values, symbol=symbol)

    def _cross_section(self, data: Any, label: str) -> Any | None:
        xs = getattr(data, "xs", None)
        columns = getattr(data, "columns", None)
        if not callable(xs) or columns is None:
            return None

        levels = getattr(columns, "nlevels", 1)
        for level in range(levels):
            try:
                return xs(label, axis=1, level=level)
            except Exception:
                continue
        return None

    def _single_close_series(self, close_values: Any, *, symbol: str) -> Any:
        columns = getattr(close_values, "columns", None)
        if columns is None:
            return close_values

        if symbol in columns:
            selected = close_values[symbol]
            if getattr(selected, "columns", None) is None:
                return selected
            return self._only_column(selected)

        column_count = len(columns)
        if column_count == 1:
            return self._only_column(close_values)

        raise ValueError(f"Yahoo Finance response has ambiguous Close columns for symbol={symbol}.")

    def _only_column(self, frame: Any) -> Any:
        iloc = getattr(frame, "iloc", None)
        if iloc is not None:
            return iloc[:, 0]
        columns = getattr(frame, "columns", None)
        if columns is not None and len(columns) == 1:
            return frame[columns[0]]
        raise ValueError("Yahoo Finance Close result must contain exactly one column.")

    def _to_date(self, value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if hasattr(value, "date"):
            converted = value.date()
            if isinstance(converted, datetime):
                return converted.date()
            if isinstance(converted, date):
                return converted
        raise ValueError(f"Invalid Yahoo Finance observation date: {value!r}")

    def _canonical_close(self, value: Any) -> Decimal:
        if value is None:
            raise ValueError("Yahoo Finance close value must not be blank.")
        if isinstance(value, str) and not value.strip():
            raise ValueError("Yahoo Finance close value must not be blank.")
        try:
            close_value = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"Invalid Yahoo Finance close value: {value!r}") from exc
        if not close_value.is_finite() or close_value <= Decimal("0"):
            raise ValueError("Yahoo Finance close value must be greater than zero.")

        try:
            canonical_value = close_value.quantize(BENCHMARK_CLOSE_SCALE, rounding=ROUND_HALF_UP)
        except InvalidOperation as exc:
            raise ValueError(f"Invalid Yahoo Finance close value: {value!r}") from exc
        if canonical_value <= Decimal("0"):
            raise ValueError("Yahoo Finance close value must be greater than zero after 8dp rounding.")
        return canonical_value
