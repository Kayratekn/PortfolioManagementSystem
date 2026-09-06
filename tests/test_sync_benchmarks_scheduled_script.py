from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from scripts import sync_benchmarks_scheduled
from src.config.supported_benchmarks import SUPPORTED_BENCHMARKS


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class SessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


@dataclass(frozen=True)
class FakeResult:
    benchmark_code: str
    provider_symbol: str
    start_date: date = date(2026, 9, 4)
    end_date: date = date(2026, 9, 5)
    fetched_rows: int = 1
    rows_created: int = 1
    rows_updated: int = 0


class FakeDailySyncService:
    failures: set[str] = set()
    instances: list["FakeDailySyncService"] = []

    def __init__(self, db: FakeSession) -> None:
        self.db = db
        self.calls: list[dict[str, object]] = []
        FakeDailySyncService.instances.append(self)

    def sync(self, **kwargs: object) -> FakeResult:
        self.calls.append(kwargs)
        benchmark_code = str(kwargs["benchmark_code"])
        if benchmark_code in FakeDailySyncService.failures:
            raise RuntimeError(f"{benchmark_code} unavailable")
        return FakeResult(
            benchmark_code=benchmark_code,
            provider_symbol=SUPPORTED_BENCHMARKS[benchmark_code].provider_symbol,
        )


@pytest.fixture(autouse=True)
def reset_fake_service() -> None:
    FakeDailySyncService.failures = set()
    FakeDailySyncService.instances = []


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    operational_today: date = date(2026, 9, 5),
) -> SessionFactory:
    session_factory = SessionFactory()
    monkeypatch.setattr(sync_benchmarks_scheduled, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_benchmarks_scheduled, "current_date", lambda: operational_today)
    monkeypatch.setattr(
        sync_benchmarks_scheduled,
        "BenchmarkDailySyncService",
        FakeDailySyncService,
    )
    return session_factory


def _calls() -> list[dict[str, object]]:
    return [instance.calls[0] for instance in FakeDailySyncService.instances]


def test_current_date_uses_europe_istanbul_calendar_date() -> None:
    assert sync_benchmarks_scheduled.current_date(
        datetime(2026, 9, 5, 20, 59, tzinfo=timezone.utc)
    ) == date(2026, 9, 5)
    assert sync_benchmarks_scheduled.current_date(
        datetime(2026, 9, 5, 21, 0, tzinfo=timezone.utc)
    ) == date(2026, 9, 6)


def test_current_date_rejects_naive_test_clock() -> None:
    with pytest.raises(ValueError, match="aware datetime"):
        sync_benchmarks_scheduled.current_date(datetime(2026, 9, 5, 21, 0))


def test_omitted_code_runs_all_supported_benchmarks_in_registry_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch)

    exit_code = sync_benchmarks_scheduled.main(["--reference-date", "2026-09-05"])

    assert exit_code == 0
    assert [call["benchmark_code"] for call in _calls()] == list(SUPPORTED_BENCHMARKS.keys())
    assert all(call["reference_date"] == date(2026, 9, 5) for call in _calls())


def test_explicit_code_runs_only_that_benchmark(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)

    exit_code = sync_benchmarks_scheduled.main(
        ["--code", "SP500", "--reference-date", "2026-09-05"]
    )

    assert exit_code == 0
    assert [call["benchmark_code"] for call in _calls()] == ["SP500"]


def test_omitted_reference_date_uses_current_istanbul_date(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, operational_today=date(2026, 9, 6))

    sync_benchmarks_scheduled.main(["--code", "NASDAQ100"])

    assert _calls()[0]["reference_date"] == date(2026, 9, 6)


def test_future_reference_date_exits_before_service_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch, operational_today=date(2026, 9, 5))

    with pytest.raises(SystemExit) as exc_info:
        sync_benchmarks_scheduled.main(["--reference-date", "2026-09-06"])

    assert exc_info.value.code == 2
    assert FakeDailySyncService.instances == []


def test_invalid_code_exits_before_service_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        sync_benchmarks_scheduled.main(["--code", "UNKNOWN"])

    assert exc_info.value.code == 2
    assert FakeDailySyncService.instances == []


def test_invalid_reference_date_exits_before_service_call(monkeypatch: pytest.MonkeyPatch) -> None:
    _install(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        sync_benchmarks_scheduled.main(["--reference-date", "2026-02-30"])

    assert exc_info.value.code == 2
    assert FakeDailySyncService.instances == []


def test_continues_remaining_benchmarks_and_returns_nonzero_when_one_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = _install(monkeypatch)
    FakeDailySyncService.failures = {"SP500"}

    exit_code = sync_benchmarks_scheduled.main(["--reference-date", "2026-09-05"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert [call["benchmark_code"] for call in _calls()] == list(SUPPORTED_BENCHMARKS.keys())
    assert "SP500: failed SP500 unavailable" in captured.err
    assert all(session.closed for session in session_factory.sessions)


def test_prints_useful_per_benchmark_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install(monkeypatch)

    sync_benchmarks_scheduled.main(["--code", "BIST100", "--reference-date", "2026-09-05"])

    captured = capsys.readouterr()
    assert "Benchmark scheduled sync" in captured.out
    assert "reference_date: 2026-09-05" in captured.out
    assert "benchmark_codes: BIST100" in captured.out
    assert "BIST100: ok symbol=XU100.IS" in captured.out
    assert "range=[2026-09-04, 2026-09-05)" in captured.out
    assert "rows_created=1" in captured.out
