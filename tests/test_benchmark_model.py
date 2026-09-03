from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.benchmark import Benchmark
from src.model.benchmark_price import BenchmarkPrice


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0017 = PROJECT_ROOT / "alembic" / "versions" / "20260903_0017_add_benchmark_metadata.py"


def _build_benchmark(
    *,
    code: str = "BIST100",
    name: str = "BIST 100",
    benchmark_type: str = "MARKET_INDEX",
    native_currency: str = "TRY",
    index_owner: str = "BORSA_ISTANBUL",
    return_type: str = "PRICE_RETURN",
    provider: str = "VERIFIED_PROVIDER",
    provider_symbol: str = "XU100",
    is_active: bool = True,
) -> Benchmark:
    return Benchmark(
        code=code,
        name=name,
        benchmark_type=benchmark_type,
        native_currency=native_currency,
        index_owner=index_owner,
        return_type=return_type,
        provider=provider,
        provider_symbol=provider_symbol,
        is_active=is_active,
    )


def test_benchmark_model_defines_required_fields_constraints_and_uniqueness() -> None:
    constraints = Benchmark.__table__.constraints
    unique_constraints = {
        tuple(constraint.columns.keys()): constraint.name
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_constraints = {
        constraint.name
        for constraint in constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert Benchmark.__table__.c.code.nullable is False
    assert Benchmark.__table__.c.name.nullable is False
    assert Benchmark.__table__.c.benchmark_type.nullable is False
    assert Benchmark.__table__.c.native_currency.nullable is False
    assert Benchmark.__table__.c.index_owner.nullable is False
    assert Benchmark.__table__.c.return_type.nullable is False
    assert Benchmark.__table__.c.provider.nullable is False
    assert Benchmark.__table__.c.provider_symbol.nullable is False
    assert Benchmark.__table__.c.is_active.nullable is False
    assert unique_constraints[("code",)] == "uq_benchmarks_code"
    assert (
        unique_constraints[("provider", "provider_symbol")]
        == "uq_benchmarks_provider_provider_symbol"
    )
    assert "ck_benchmarks_benchmark_type_allowed" in check_constraints
    assert "ck_benchmarks_native_currency_uppercase_3" in check_constraints
    assert "ck_benchmarks_index_owner_required_uppercase" in check_constraints
    assert "ck_benchmarks_return_type_allowed" in check_constraints


def test_benchmark_price_model_defines_required_fields_constraints_uniqueness_and_index() -> None:
    constraints = BenchmarkPrice.__table__.constraints
    unique_constraints = {
        tuple(constraint.columns.keys()): constraint.name
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }
    check_constraints = {
        constraint.name
        for constraint in constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {
        index.name
        for index in BenchmarkPrice.__table__.indexes
        if isinstance(index, Index)
    }

    assert BenchmarkPrice.__table__.c.benchmark_id.nullable is False
    assert BenchmarkPrice.__table__.c.price_date.nullable is False
    assert BenchmarkPrice.__table__.c.close_value.nullable is False
    assert BenchmarkPrice.__table__.c.source.nullable is False
    assert BenchmarkPrice.__table__.c.close_value.type.precision == 20
    assert BenchmarkPrice.__table__.c.close_value.type.scale == 8
    assert unique_constraints[("benchmark_id", "price_date")] == "uq_benchmark_prices_benchmark_date"
    assert "ck_benchmark_prices_close_value_positive" in check_constraints
    assert "ix_benchmark_prices_benchmark_date" in indexes
    assert "currency" not in BenchmarkPrice.__table__.c


def test_benchmark_metadata_migration_precondition_runs_before_schema_mutation() -> None:
    migration_text = MIGRATION_0017.read_text(encoding="utf-8")

    assert 'revision = "20260903_0017"' in migration_text
    assert 'down_revision = "20260903_0016"' in migration_text
    assert "SELECT COUNT(*) FROM benchmarks" in migration_text
    assert "Cannot apply benchmark metadata migration 20260903_0017" in migration_text
    assert migration_text.index("SELECT COUNT(*) FROM benchmarks") < migration_text.index(
        "op.batch_alter_table"
    )


def test_benchmark_native_currency_is_normalized_to_uppercase() -> None:
    benchmark = _build_benchmark(native_currency=" usd ")

    assert benchmark.native_currency == "USD"


@pytest.mark.parametrize("native_currency", ["123", "U1D", "$$$", "US", "USDD", "", "   ", None])
def test_benchmark_native_currency_must_be_three_ascii_letters(native_currency: str | None) -> None:
    with pytest.raises(ValueError):
        _build_benchmark(native_currency=native_currency)  # type: ignore[arg-type]


@pytest.mark.parametrize("native_currency", ["JPY", "CHF"])
def test_benchmark_native_currency_accepts_valid_non_fx_foundation_codes(
    db_session: Session,
    native_currency: str,
) -> None:
    benchmark = _build_benchmark(
        code=f"BENCH_{native_currency}",
        native_currency=native_currency,
        provider_symbol=f"SYM_{native_currency}",
    )
    db_session.add(benchmark)
    db_session.flush()

    assert benchmark.native_currency == native_currency


@pytest.mark.parametrize("native_currency", ["usd", "123", "U1D", "$$$", "US", "USDD"])
def test_benchmark_native_currency_db_constraint_rejects_invalid_direct_persistence(
    db_session: Session,
    native_currency: str,
) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO benchmarks "
                "(code, name, benchmark_type, native_currency, index_owner, return_type, "
                "provider, provider_symbol, is_active) "
                "VALUES (:code, 'Invalid Currency Benchmark', 'MARKET_INDEX', :native_currency, "
                "'BORSA_ISTANBUL', 'PRICE_RETURN', 'DIRECT_SQL', :provider_symbol, 1)"
            ),
            {
                "code": f"BAD_{native_currency}",
                "native_currency": native_currency,
                "provider_symbol": f"BAD_{native_currency}",
            },
        )


def test_benchmark_index_owner_is_normalized_to_uppercase() -> None:
    benchmark = _build_benchmark(index_owner=" borsa_istanbul ")

    assert benchmark.index_owner == "BORSA_ISTANBUL"


@pytest.mark.parametrize("index_owner", ["", "   ", None])
def test_benchmark_index_owner_must_not_be_blank(index_owner: str | None) -> None:
    with pytest.raises(ValueError):
        _build_benchmark(index_owner=index_owner)  # type: ignore[arg-type]


@pytest.mark.parametrize("return_type", ["PRICE_RETURN", "TOTAL_RETURN"])
def test_benchmark_return_type_accepts_allowed_values(return_type: str) -> None:
    benchmark = _build_benchmark(return_type=return_type.lower())

    assert benchmark.return_type == return_type


@pytest.mark.parametrize("return_type", ["", "   ", "NET_TOTAL_RETURN", "PRICE_INDEX", None])
def test_benchmark_return_type_rejects_unknown_values(return_type: str | None) -> None:
    with pytest.raises(ValueError):
        _build_benchmark(return_type=return_type)  # type: ignore[arg-type]


def test_benchmark_metadata_db_constraints_reject_invalid_direct_persistence(
    db_session: Session,
) -> None:
    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO benchmarks "
                "(code, name, benchmark_type, native_currency, index_owner, return_type, "
                "provider, provider_symbol, is_active) "
                "VALUES ('BAD_OWNER', 'Bad Owner', 'MARKET_INDEX', 'TRY', '', "
                "'PRICE_RETURN', 'DIRECT_SQL', 'BAD_OWNER', 1)"
            )
        )
    db_session.rollback()

    with pytest.raises(IntegrityError):
        db_session.execute(
            text(
                "INSERT INTO benchmarks "
                "(code, name, benchmark_type, native_currency, index_owner, return_type, "
                "provider, provider_symbol, is_active) "
                "VALUES ('BAD_RETURN', 'Bad Return', 'MARKET_INDEX', 'TRY', "
                "'BORSA_ISTANBUL', 'NET_RETURN', 'DIRECT_SQL', 'BAD_RETURN', 1)"
            )
        )


def test_benchmark_type_constraint_rejects_unknown_type(db_session: Session) -> None:
    db_session.add(_build_benchmark(benchmark_type="PRICE_INDEX"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_benchmark_unique_code_constraint(db_session: Session) -> None:
    db_session.add(_build_benchmark(code="BIST100", provider_symbol="XU100"))
    db_session.add(_build_benchmark(code="BIST100", provider_symbol="XU100_ALT"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_benchmark_unique_provider_symbol_identity_constraint(db_session: Session) -> None:
    db_session.add(_build_benchmark(code="BIST100", provider="PROVIDER", provider_symbol="XU100"))
    db_session.add(_build_benchmark(code="BIST100_ALT", provider="PROVIDER", provider_symbol="XU100"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_benchmark_price_close_value_must_be_positive(db_session: Session) -> None:
    benchmark = _build_benchmark()
    db_session.add(benchmark)
    db_session.flush()
    db_session.add(
        BenchmarkPrice(
            benchmark_id=benchmark.id,
            price_date=date(2026, 1, 2),
            close_value=Decimal("0"),
            source="VERIFIED_PROVIDER",
        )
    )

    with pytest.raises(IntegrityError):
        db_session.flush()