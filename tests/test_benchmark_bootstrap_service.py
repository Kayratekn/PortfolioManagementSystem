from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.supported_benchmarks import (
    BIST100_BENCHMARK,
    NASDAQ100_BENCHMARK,
    SP500_BENCHMARK,
    SUPPORTED_BENCHMARKS,
    SupportedBenchmark,
)
from src.model.benchmark import Benchmark
from src.repositories.benchmark_repository import BenchmarkRepository
from src.services.benchmark_bootstrap_service import (
    BENCHMARK_BOOTSTRAP_ALREADY_EXISTS,
    BENCHMARK_BOOTSTRAP_CREATED,
    BenchmarkBootstrapConflictError,
    BenchmarkBootstrapService,
)


EXPECTED_SUPPORTED_BENCHMARKS = {
    "BIST100": BIST100_BENCHMARK,
    "SP500": SP500_BENCHMARK,
    "NASDAQ100": NASDAQ100_BENCHMARK,
}


LOCKED_BENCHMARK_METADATA = [
    (
        BIST100_BENCHMARK,
        {
            "code": "BIST100",
            "name": "BIST 100",
            "benchmark_type": "MARKET_INDEX",
            "native_currency": "TRY",
            "index_owner": "BORSA_ISTANBUL",
            "return_type": "PRICE_RETURN",
            "provider": "YAHOO_FINANCE",
            "provider_symbol": "XU100.IS",
            "is_active": True,
        },
    ),
    (
        SP500_BENCHMARK,
        {
            "code": "SP500",
            "name": "S&P 500",
            "benchmark_type": "MARKET_INDEX",
            "native_currency": "USD",
            "index_owner": "SP_DOW_JONES_INDICES",
            "return_type": "PRICE_RETURN",
            "provider": "YAHOO_FINANCE",
            "provider_symbol": "^GSPC",
            "is_active": True,
        },
    ),
    (
        NASDAQ100_BENCHMARK,
        {
            "code": "NASDAQ100",
            "name": "NASDAQ-100",
            "benchmark_type": "MARKET_INDEX",
            "native_currency": "USD",
            "index_owner": "NASDAQ",
            "return_type": "PRICE_RETURN",
            "provider": "YAHOO_FINANCE",
            "provider_symbol": "^NDX",
            "is_active": True,
        },
    ),
]


def _benchmarks(db_session: Session) -> list[Benchmark]:
    return list(db_session.scalars(select(Benchmark).order_by(Benchmark.id.asc())))


def _add_existing(db_session: Session, **overrides: object) -> Benchmark:
    values = {
        "code": BIST100_BENCHMARK.code,
        "name": BIST100_BENCHMARK.name,
        "benchmark_type": BIST100_BENCHMARK.benchmark_type,
        "native_currency": BIST100_BENCHMARK.native_currency,
        "index_owner": BIST100_BENCHMARK.index_owner,
        "return_type": BIST100_BENCHMARK.return_type,
        "provider": BIST100_BENCHMARK.provider,
        "provider_symbol": BIST100_BENCHMARK.provider_symbol,
        "is_active": BIST100_BENCHMARK.is_active,
    }
    values.update(overrides)
    benchmark = Benchmark(**values)
    db_session.add(benchmark)
    db_session.commit()
    db_session.refresh(benchmark)
    return benchmark


def _assert_benchmark_matches_locked_metadata(
    benchmark: SupportedBenchmark | Benchmark,
    expected: dict[str, object],
) -> None:
    assert benchmark.code == expected["code"]
    assert benchmark.name == expected["name"]
    assert benchmark.benchmark_type == expected["benchmark_type"]
    assert benchmark.native_currency == expected["native_currency"]
    assert benchmark.index_owner == expected["index_owner"]
    assert benchmark.return_type == expected["return_type"]
    assert benchmark.provider == expected["provider"]
    assert benchmark.provider_symbol == expected["provider_symbol"]
    assert benchmark.is_active is expected["is_active"]


def test_supported_registry_contains_all_supported_benchmarks() -> None:
    assert SUPPORTED_BENCHMARKS == EXPECTED_SUPPORTED_BENCHMARKS


@pytest.mark.parametrize(("metadata", "expected"), LOCKED_BENCHMARK_METADATA)
def test_supported_registry_contains_exact_locked_metadata(
    metadata: SupportedBenchmark,
    expected: dict[str, object],
) -> None:
    assert SUPPORTED_BENCHMARKS[metadata.code] is metadata
    _assert_benchmark_matches_locked_metadata(metadata, expected)


@pytest.mark.parametrize(("metadata", "expected"), LOCKED_BENCHMARK_METADATA)
def test_bootstrap_creates_exact_locked_metadata(
    db_session: Session,
    metadata: SupportedBenchmark,
    expected: dict[str, object],
) -> None:
    result = BenchmarkBootstrapService(db_session).bootstrap(metadata)

    assert result.status == BENCHMARK_BOOTSTRAP_CREATED
    _assert_benchmark_matches_locked_metadata(result.benchmark, expected)


def test_exact_rerun_is_idempotent_and_creates_no_duplicate(db_session: Session) -> None:
    service = BenchmarkBootstrapService(db_session)
    first = service.bootstrap(BIST100_BENCHMARK)
    second = service.bootstrap(BIST100_BENCHMARK)

    assert first.status == BENCHMARK_BOOTSTRAP_CREATED
    assert second.status == BENCHMARK_BOOTSTRAP_ALREADY_EXISTS
    assert second.benchmark.id == first.benchmark.id
    assert len(_benchmarks(db_session)) == 1


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("name", "BIST 100 Changed"),
        ("native_currency", "USD"),
        ("provider", "OTHER_PROVIDER"),
        ("provider_symbol", "XU100"),
        ("is_active", False),
    ],
)
def test_existing_metadata_conflict_refuses_and_does_not_mutate(
    db_session: Session,
    field_name: str,
    value: object,
) -> None:
    existing = _add_existing(db_session, **{field_name: value})
    original_values = {
        "name": existing.name,
        "native_currency": existing.native_currency,
        "provider": existing.provider,
        "provider_symbol": existing.provider_symbol,
        "is_active": existing.is_active,
    }

    with pytest.raises(BenchmarkBootstrapConflictError) as exc_info:
        BenchmarkBootstrapService(db_session).bootstrap(BIST100_BENCHMARK)

    assert field_name in str(exc_info.value)
    db_session.refresh(existing)
    assert existing.name == original_values["name"]
    assert existing.native_currency == original_values["native_currency"]
    assert existing.provider == original_values["provider"]
    assert existing.provider_symbol == original_values["provider_symbol"]
    assert existing.is_active == original_values["is_active"]
    assert len(_benchmarks(db_session)) == 1


def test_another_benchmark_owning_provider_symbol_conflicts(db_session: Session) -> None:
    owner = _add_existing(
        db_session,
        code="OTHER",
        name="Other Benchmark",
    )

    with pytest.raises(BenchmarkBootstrapConflictError) as exc_info:
        BenchmarkBootstrapService(db_session).bootstrap(BIST100_BENCHMARK)

    assert "provider identity conflict" in str(exc_info.value)
    assert "existing_code=OTHER" in str(exc_info.value)
    db_session.refresh(owner)
    assert owner.code == "OTHER"
    assert len(_benchmarks(db_session)) == 1


def test_repository_finds_exact_provider_symbol_owner(db_session: Session) -> None:
    benchmark = _add_existing(db_session)
    repository = BenchmarkRepository(db_session)

    assert repository.get_by_provider_symbol(
        provider="YAHOO_FINANCE",
        provider_symbol="XU100.IS",
    ) is benchmark
    assert repository.get_by_provider_symbol(provider="YAHOO_FINANCE", provider_symbol="MISSING") is None


def test_bootstrap_rolls_back_when_commit_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    with pytest.raises(RuntimeError):
        BenchmarkBootstrapService(db_session).bootstrap(BIST100_BENCHMARK)

    assert _benchmarks(db_session) == []


def test_bootstrap_rejects_metadata_that_model_would_normalize(db_session: Session) -> None:
    metadata = replace(BIST100_BENCHMARK, native_currency="try")

    with pytest.raises(ValueError, match="native_currency must be uppercase"):
        BenchmarkBootstrapService(db_session).bootstrap(metadata)

    assert _benchmarks(db_session) == []


def test_bootstrap_module_has_no_provider_dependency() -> None:
    source = Path(__file__).resolve().parents[1].joinpath(
        "src", "services", "benchmark_bootstrap_service.py"
    ).read_text(encoding="utf-8")

    assert "yfinance" not in source.lower()
    assert "CustomTefasClient" not in source
