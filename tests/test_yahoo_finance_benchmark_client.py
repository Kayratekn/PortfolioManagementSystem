from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
import sys

import pytest

from src.integrations.yahoo_finance_benchmark_client import YahooFinanceBenchmarkClient


class FakeSeries:
    def __init__(self, rows: list[tuple[object, object]]) -> None:
        self.rows = rows

    def items(self):
        return iter(self.rows)


class FakeSingleColumnIloc:
    def __init__(self, series: FakeSeries) -> None:
        self.series = series

    def __getitem__(self, key: object) -> FakeSeries:
        if key == (slice(None), 0):
            return self.series
        raise IndexError(key)


class FakeCloseFrame:
    def __init__(self, columns: list[str], series_by_column: dict[str, FakeSeries]) -> None:
        self.columns = columns
        self.series_by_column = series_by_column
        self.iloc = FakeSingleColumnIloc(series_by_column[columns[0]])

    def __getitem__(self, key: str) -> FakeSeries:
        return self.series_by_column[key]


class FakeDataFrame:
    def __init__(self, close_values: object, *, empty: bool = False) -> None:
        self.empty = empty
        self.close_values = close_values

    def __getitem__(self, key: str) -> object:
        if key != "Close":
            raise KeyError(key)
        return self.close_values


class FakeMultiIndexColumns:
    nlevels = 2


class FakeMultiIndexDataFrame:
    def __init__(self, close_values: object) -> None:
        self.empty = False
        self.columns = FakeMultiIndexColumns()
        self.close_values = close_values
        self.xs_calls: list[dict[str, object]] = []

    def __getitem__(self, key: str) -> object:
        raise KeyError(key)

    def xs(self, label: str, *, axis: int, level: int) -> object:
        self.xs_calls.append({"label": label, "axis": axis, "level": level})
        if label == "Close" and axis == 1 and level == 1:
            return self.close_values
        raise KeyError(label)


class FakeYFinance:
    def __init__(self, frame: object) -> None:
        self.frame = frame
        self.calls: list[dict[str, object]] = []

    def download(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return self.frame


class ScalarLike:
    def __init__(self, value: str) -> None:
        self.value = value

    def __str__(self) -> str:
        return self.value


def _install_yfinance(monkeypatch: pytest.MonkeyPatch, frame: object) -> FakeYFinance:
    fake = FakeYFinance(frame)
    monkeypatch.setitem(sys.modules, "yfinance", fake)
    return fake


def _series(rows: list[tuple[object, object]]) -> FakeSeries:
    return FakeSeries(rows)


def test_fetch_daily_close_calls_yfinance_with_locked_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install_yfinance(
        monkeypatch,
        FakeDataFrame(_series([(datetime(2026, 9, 3), "4500.125")])),
    )

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^GSPC",
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 4),
    )

    assert fake.calls == [
        {
            "tickers": "^GSPC",
            "start": date(2026, 9, 3),
            "end": date(2026, 9, 4),
            "interval": "1d",
            "auto_adjust": False,
            "progress": False,
        }
    ]
    assert observations[0].price_date == date(2026, 9, 3)
    assert observations[0].close_value == Decimal("4500.12500000")


def test_fetch_daily_close_uses_start_inclusive_end_exclusive_provider_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _install_yfinance(monkeypatch, FakeDataFrame(_series([])))

    YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="XU100.IS",
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 5),
    )

    assert fake.calls[0]["start"] == date(2026, 1, 2)
    assert fake.calls[0]["end"] == date(2026, 1, 5)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (14050.599609375, Decimal("14050.59960938")),
        (ScalarLike("14050.599609375"), Decimal("14050.59960938")),
        ("1.234567884", Decimal("1.23456788")),
        ("1.234567885", Decimal("1.23456789")),
        ("0.000000005", Decimal("0.00000001")),
    ],
)
def test_fetch_daily_close_canonicalizes_to_8dp_round_half_up(
    monkeypatch: pytest.MonkeyPatch,
    raw: object,
    expected: Decimal,
) -> None:
    _install_yfinance(monkeypatch, FakeDataFrame(_series([(date(2026, 9, 3), raw)])))

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^NDX",
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 4),
    )

    assert observations[0].close_value == expected
    assert observations[0].close_value.as_tuple().exponent == -8


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "   ",
        "NaN",
        "nan",
        "Infinity",
        "inf",
        "1E+100000",
        0,
        "0",
        -1,
        "-1",
        "0.000000004",
    ],
)
def test_fetch_daily_close_rejects_blank_non_finite_or_non_positive_values(
    monkeypatch: pytest.MonkeyPatch,
    raw: object,
) -> None:
    _install_yfinance(monkeypatch, FakeDataFrame(_series([(date(2026, 9, 3), raw)])))

    with pytest.raises(ValueError):
        YahooFinanceBenchmarkClient().fetch_daily_close(
            symbol="^GSPC",
            start_date=date(2026, 9, 3),
            end_date=date(2026, 9, 4),
        )


def test_fetch_daily_close_empty_provider_result_is_empty_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_yfinance(monkeypatch, FakeDataFrame(_series([]), empty=True))

    assert YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^GSPC",
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 4),
    ) == []


def test_fetch_daily_close_does_not_fabricate_missing_weekend_or_holiday_dates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_yfinance(
        monkeypatch,
        FakeDataFrame(
            _series(
                [
                    (date(2026, 9, 4), "100"),
                    (date(2026, 9, 8), "104"),
                ]
            )
        ),
    )

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^GSPC",
        start_date=date(2026, 9, 4),
        end_date=date(2026, 9, 9),
    )

    assert [observation.price_date for observation in observations] == [
        date(2026, 9, 4),
        date(2026, 9, 8),
    ]


def test_fetch_daily_close_ignores_stale_pre_start_yahoo_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_yfinance(
        monkeypatch,
        FakeDataFrame(_series([(date(2026, 9, 4), "100")])),
    )

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^GSPC",
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 6),
    )

    assert observations == []


def test_fetch_daily_close_returns_empty_when_all_rows_are_stale_pre_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_yfinance(
        monkeypatch,
        FakeDataFrame(
            _series(
                [
                    (date(2026, 9, 3), "99"),
                    (date(2026, 9, 4), "100"),
                ]
            )
        ),
    )

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="XU100.IS",
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 6),
    )

    assert observations == []


def test_fetch_daily_close_keeps_valid_rows_when_stale_rows_are_also_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_yfinance(
        monkeypatch,
        FakeDataFrame(
            _series(
                [
                    (date(2026, 9, 4), "100"),
                    (date(2026, 9, 8), "104.123456785"),
                ]
            )
        ),
    )

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^NDX",
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 9),
    )

    assert [(item.price_date, item.close_value) for item in observations] == [
        (date(2026, 9, 8), Decimal("104.12345679")),
    ]


def test_fetch_daily_close_raises_for_end_date_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_yfinance(
        monkeypatch,
        FakeDataFrame(_series([(date(2026, 9, 6), "101")])),
    )

    with pytest.raises(ValueError, match="end-exclusive range"):
        YahooFinanceBenchmarkClient().fetch_daily_close(
            symbol="^GSPC",
            start_date=date(2026, 9, 5),
            end_date=date(2026, 9, 6),
        )


def test_fetch_daily_close_ignores_malformed_stale_pre_start_close_before_canonicalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_yfinance(
        monkeypatch,
        FakeDataFrame(
            _series(
                [
                    (date(2026, 9, 4), "not-a-decimal"),
                    (date(2026, 9, 8), "104"),
                ]
            )
        ),
    )

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="XU100.IS",
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 9),
    )

    assert [(item.price_date, item.close_value) for item in observations] == [
        (date(2026, 9, 8), Decimal("104.00000000")),
    ]


def test_fetch_daily_close_accepts_single_ticker_multiindex_close_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_frame = FakeCloseFrame(
        ["^GSPC"],
        {"^GSPC": _series([(date(2026, 9, 3), "4500")])},
    )
    frame = FakeMultiIndexDataFrame(close_frame)
    _install_yfinance(monkeypatch, frame)

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^GSPC",
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 4),
    )

    assert observations[0].close_value == Decimal("4500.00000000")
    assert frame.xs_calls == [
        {"label": "Close", "axis": 1, "level": 0},
        {"label": "Close", "axis": 1, "level": 1},
    ]


def test_fetch_daily_close_accepts_one_column_close_dataframe_without_symbol_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_frame = FakeCloseFrame(
        ["close"],
        {"close": _series([(date(2026, 9, 3), "4500")])},
    )
    _install_yfinance(monkeypatch, FakeDataFrame(close_frame))

    observations = YahooFinanceBenchmarkClient().fetch_daily_close(
        symbol="^GSPC",
        start_date=date(2026, 9, 3),
        end_date=date(2026, 9, 4),
    )

    assert observations[0].close_value == Decimal("4500.00000000")


def test_fetch_daily_close_rejects_ambiguous_close_dataframe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_frame = FakeCloseFrame(
        ["A", "B"],
        {
            "A": _series([(date(2026, 9, 3), "4500")]),
            "B": _series([(date(2026, 9, 3), "4501")]),
        },
    )
    _install_yfinance(monkeypatch, FakeDataFrame(close_frame))

    with pytest.raises(ValueError, match="ambiguous Close columns"):
        YahooFinanceBenchmarkClient().fetch_daily_close(
            symbol="^GSPC",
            start_date=date(2026, 9, 3),
            end_date=date(2026, 9, 4),
        )
