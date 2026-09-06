from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from scripts import bootstrap_benchmarks, import_benchmark_prices
from src.config.supported_benchmarks import BIST100_BENCHMARK
from src.model.benchmark import Benchmark
from src.model.benchmark_price import BenchmarkPrice
from src.services.benchmark_price_import_parser import BenchmarkPriceObservation
from src.services.benchmark_price_import_service import BenchmarkPriceImportResult


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


class FakeBootstrapService:
    result_status = "CREATED"
    error: Exception | None = None
    instances: list["FakeBootstrapService"] = []

    def __init__(self, db: FakeSession) -> None:
        self.db = db
        self.calls: list[object] = []
        FakeBootstrapService.instances.append(self)

    def bootstrap(self, metadata: object):
        self.calls.append(metadata)
        if FakeBootstrapService.error is not None:
            raise FakeBootstrapService.error

        @dataclass(frozen=True)
        class Result:
            status: str

        return Result(status=FakeBootstrapService.result_status)


class FakeImportService:
    result = BenchmarkPriceImportResult(fetched_rows=2, rows_created=2, rows_updated=0)
    error: Exception | None = None
    instances: list["FakeImportService"] = []

    def __init__(self, db: FakeSession) -> None:
        self.db = db
        self.calls: list[dict[str, object]] = []
        FakeImportService.instances.append(self)

    def import_observations(self, **kwargs: object) -> BenchmarkPriceImportResult:
        self.calls.append(kwargs)
        if FakeImportService.error is not None:
            raise FakeImportService.error
        return FakeImportService.result


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeBootstrapService.result_status = "CREATED"
    FakeBootstrapService.error = None
    FakeBootstrapService.instances = []
    FakeImportService.result = BenchmarkPriceImportResult(fetched_rows=2, rows_created=2, rows_updated=0)
    FakeImportService.error = None
    FakeImportService.instances = []


def _write_csv(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "benchmark.csv"
    path.write_text(text, encoding="utf-8")
    return path


def _add_bist100(db_session: Session, *, is_active: bool = True) -> Benchmark:
    benchmark = Benchmark(
        code=BIST100_BENCHMARK.code,
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


def test_bootstrap_cli_calls_registry_metadata_and_prints_status(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(bootstrap_benchmarks, "SessionLocal", session_factory)
    monkeypatch.setattr(bootstrap_benchmarks, "BenchmarkBootstrapService", FakeBootstrapService)

    exit_code = bootstrap_benchmarks.main(["--code", "BIST100"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == "CREATED"
    assert FakeBootstrapService.instances[0].db is session_factory.sessions[0]
    assert FakeBootstrapService.instances[0].calls == [BIST100_BENCHMARK]
    assert session_factory.sessions[0].closed is True


def test_bootstrap_cli_unknown_code_fails_before_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(bootstrap_benchmarks, "SessionLocal", session_factory)

    exit_code = bootstrap_benchmarks.main(["--code", "SP500"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Unsupported benchmark code: SP500" in captured.err
    assert session_factory.sessions == []


def test_bootstrap_cli_conflict_returns_nonzero_and_closes_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeBootstrapService.error = ValueError("metadata conflict")
    monkeypatch.setattr(bootstrap_benchmarks, "SessionLocal", session_factory)
    monkeypatch.setattr(bootstrap_benchmarks, "BenchmarkBootstrapService", FakeBootstrapService)

    exit_code = bootstrap_benchmarks.main(["--code", "BIST100"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Benchmark bootstrap failed: metadata conflict" in captured.err
    assert session_factory.sessions[0].closed is True


def test_valid_canonical_csv_succeeds_through_existing_parser_and_importer(
    tmp_path: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    benchmark = _add_bist100(db_session)
    path = _write_csv(tmp_path, "date,close\n2026-01-02,1432.56000000\n")
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    exit_code = import_benchmark_prices.main(
        [
            "--benchmark-code",
            "BIST100",
            "--source",
            "DATA_TEAM_YAHOO_FINANCE_CLOSE",
            "--file",
            str(path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    price = db_session.query(BenchmarkPrice).one()
    assert price.benchmark_id == benchmark.id
    assert price.price_date == date(2026, 1, 2)
    assert price.close_value == Decimal("1432.56000000")
    assert price.source == "DATA_TEAM_YAHOO_FINANCE_CLOSE"
    assert "benchmark_code: BIST100" in captured.out
    assert "canonical_rows_read: 1" in captured.out
    assert "fetched_rows: 1" in captured.out
    assert "rows_created: 1" in captured.out


def test_utf8_bom_header_works_with_real_importer(
    tmp_path: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _add_bist100(db_session)
    path = tmp_path / "benchmark.csv"
    path.write_text("\ufeffdate,close\n2026-01-02,1432.56000000\n", encoding="utf-8")
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    assert import_benchmark_prices.main(
        ["--benchmark-code", "BIST100", "--source", "BOM_SOURCE", "--file", str(path)]
    ) == 0
    assert db_session.query(BenchmarkPrice).one().source == "BOM_SOURCE"


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("close\n100\n", "missing required header(s): date"),
        ("date\n2026-01-02\n", "missing required header(s): close"),
        ("date,close\n2026-01-02,100,extra\n", "row 2 has too many columns"),
    ],
)
def test_malformed_csv_fails_before_session_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    contents: str,
    message: str,
) -> None:
    path = _write_csv(tmp_path, contents)
    session_factory = SessionFactory()
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", session_factory)

    exit_code = import_benchmark_prices.main(
        ["--benchmark-code", "BIST100", "--source", "SRC", "--file", str(path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert message in captured.err
    assert session_factory.sessions == []


@pytest.mark.parametrize(
    ("close_value", "message"),
    [
        ("14050.599609375", "fit NUMERIC(20,8)"),
        ("101", "Conflicting benchmark close values"),
    ],
)
def test_parser_rejections_are_preserved_before_persistence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    close_value: str,
    message: str,
) -> None:
    path = _write_csv(
        tmp_path,
        f"date,close\n2026-01-02,100\n2026-01-02,{close_value}\n",
    )
    session_factory = SessionFactory()
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", session_factory)

    exit_code = import_benchmark_prices.main(
        ["--benchmark-code", "BIST100", "--source", "SRC", "--file", str(path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert message in captured.err
    assert session_factory.sessions == []


def test_identical_duplicate_semantics_remain_existing_parser_behavior(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_csv(tmp_path, "date,close\n2026-01-02,100\n2026-01-02,100.00\n")
    session_factory = SessionFactory()
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", session_factory)
    monkeypatch.setattr(import_benchmark_prices, "BenchmarkPriceImportService", FakeImportService)

    assert import_benchmark_prices.main(
        ["--benchmark-code", "BIST100", "--source", "SRC", "--file", str(path)]
    ) == 0
    observations = FakeImportService.instances[0].calls[0]["observations"]
    assert observations == [BenchmarkPriceObservation(date(2026, 1, 2), Decimal("100"))]


@pytest.mark.parametrize("is_active", [False])
def test_unknown_or_inactive_benchmark_uses_existing_importer_failure(
    tmp_path: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    is_active: bool,
) -> None:
    _add_bist100(db_session, is_active=is_active)
    path = _write_csv(tmp_path, "date,close\n2026-01-02,100\n")
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    exit_code = import_benchmark_prices.main(
        ["--benchmark-code", "BIST100", "--source", "SRC", "--file", str(path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Active benchmark not found: BIST100" in captured.err


def test_unknown_benchmark_uses_existing_importer_failure(
    tmp_path: Path,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _write_csv(tmp_path, "date,close\n2026-01-02,100\n")
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", lambda: db_session)
    monkeypatch.setattr(db_session, "close", lambda: None)

    exit_code = import_benchmark_prices.main(
        ["--benchmark-code", "UNKNOWN", "--source", "SRC", "--file", str(path)]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Active benchmark not found: UNKNOWN" in captured.err


def test_allow_revisions_flag_source_and_string_close_are_passed_exactly(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_rows: list[dict[str, object]] = []

    def fake_parse(rows: list[dict[str, object]]) -> list[BenchmarkPriceObservation]:
        captured_rows.extend(rows)
        return [BenchmarkPriceObservation(date(2026, 1, 2), Decimal("100"))]

    path = _write_csv(tmp_path, "date,close\n2026-01-02,100.12345678\n")
    session_factory = SessionFactory()
    monkeypatch.setattr(import_benchmark_prices, "SessionLocal", session_factory)
    monkeypatch.setattr(import_benchmark_prices, "parse_benchmark_price_rows", fake_parse)
    monkeypatch.setattr(import_benchmark_prices, "BenchmarkPriceImportService", FakeImportService)

    exit_code = import_benchmark_prices.main(
        [
            "--benchmark-code",
            "BIST100",
            "--source",
            "DATA_TEAM_YAHOO_FINANCE_CLOSE",
            "--file",
            str(path),
            "--allow-revisions",
        ]
    )

    call = FakeImportService.instances[0].calls[0]
    assert exit_code == 0
    assert captured_rows == [{"date": "2026-01-02", "close": "100.12345678"}]
    assert isinstance(captured_rows[0]["close"], str)
    assert call["benchmark_code"] == "BIST100"
    assert call["source"] == "DATA_TEAM_YAHOO_FINANCE_CLOSE"
    assert call["allow_revisions"] is True
    assert session_factory.sessions[0].closed is True


def test_import_cli_has_no_provider_dependency() -> None:
    source = Path(import_benchmark_prices.__file__).read_text(encoding="utf-8")

    assert "yfinance" not in source.lower()
    assert "CustomTefasClient" not in source
