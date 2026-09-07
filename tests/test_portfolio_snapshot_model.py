from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.model as model_package
from src.model.base import Base
from src.model.portfolio import Portfolio
from src.model.portfolio_snapshot import PortfolioSnapshot
from src.model.user import User


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0022 = PROJECT_ROOT / "alembic" / "versions" / "20260907_0022_create_portfolio_snapshots.py"
ALEMBIC_ENV = PROJECT_ROOT / "alembic" / "env.py"


def _add_user(db_session: Session, *, email: str = "user@example.com") -> User:
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password="hashed",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _add_portfolio(
    db_session: Session,
    *,
    user_id: int,
    name: str = "Portfolio",
) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, name=name, base_currency="TRY")
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _snapshot(
    *,
    portfolio_id: int,
    snapshot_date: date = date(2026, 9, 7),
    total_value_try: Decimal = Decimal("1000.12345678"),
    total_value_usd: Decimal = Decimal("30.12345678"),
    total_value_eur: Decimal = Decimal("25.12345678"),
    total_value_gbp: Decimal = Decimal("20.12345678"),
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=snapshot_date,
        total_value_try=total_value_try,
        total_value_usd=total_value_usd,
        total_value_eur=total_value_eur,
        total_value_gbp=total_value_gbp,
    )


def test_portfolio_snapshot_model_defines_required_fields_unique_index_and_timestamps() -> None:
    constraints = PortfolioSnapshot.__table__.constraints
    unique_constraints = {
        tuple(constraint.columns.keys()): constraint.name
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {
        index.name: tuple(index.columns.keys())
        for index in PortfolioSnapshot.__table__.indexes
        if isinstance(index, Index)
    }
    foreign_keys = PortfolioSnapshot.__table__.c.portfolio_id.foreign_keys

    assert PortfolioSnapshot.__table__.c.id.primary_key is True
    assert PortfolioSnapshot.__table__.c.portfolio_id.nullable is False
    assert PortfolioSnapshot.__table__.c.snapshot_date.nullable is False
    assert PortfolioSnapshot.__table__.c.total_value_try.nullable is False
    assert PortfolioSnapshot.__table__.c.total_value_usd.nullable is False
    assert PortfolioSnapshot.__table__.c.total_value_eur.nullable is False
    assert PortfolioSnapshot.__table__.c.total_value_gbp.nullable is False
    assert PortfolioSnapshot.__table__.c.total_value_try.type.precision == 20
    assert PortfolioSnapshot.__table__.c.total_value_try.type.scale == 8
    assert PortfolioSnapshot.__table__.c.total_value_usd.type.precision == 20
    assert PortfolioSnapshot.__table__.c.total_value_usd.type.scale == 8
    assert PortfolioSnapshot.__table__.c.total_value_eur.type.precision == 20
    assert PortfolioSnapshot.__table__.c.total_value_eur.type.scale == 8
    assert PortfolioSnapshot.__table__.c.total_value_gbp.type.precision == 20
    assert PortfolioSnapshot.__table__.c.total_value_gbp.type.scale == 8
    assert unique_constraints[("portfolio_id", "snapshot_date")] == (
        "uq_portfolio_snapshots_portfolio_date"
    )
    assert indexes["ix_portfolio_snapshots_portfolio_date_id"] == (
        "portfolio_id",
        "snapshot_date",
        "id",
    )
    assert len(foreign_keys) == 1
    assert next(iter(foreign_keys)).target_fullname == "portfolios.id"
    assert "created_at" in PortfolioSnapshot.__table__.c
    assert "updated_at" in PortfolioSnapshot.__table__.c


def test_portfolio_snapshot_migration_revision_table_constraints_and_index() -> None:
    migration_text = MIGRATION_0022.read_text(encoding="utf-8")

    assert 'revision = "20260907_0022"' in migration_text
    assert 'down_revision = "20260907_0021"' in migration_text
    assert '"portfolio_snapshots"' in migration_text
    assert '"portfolio_id"' in migration_text
    assert '"snapshot_date"' in migration_text
    assert '"total_value_try"' in migration_text
    assert '"total_value_usd"' in migration_text
    assert '"total_value_eur"' in migration_text
    assert '"total_value_gbp"' in migration_text
    assert migration_text.count("sa.Numeric(precision=20, scale=8)") == 4
    assert 'sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"])' in migration_text
    assert 'name="uq_portfolio_snapshots_portfolio_date"' in migration_text
    assert '"ix_portfolio_snapshots_portfolio_date_id"' in migration_text
    assert '["portfolio_id", "snapshot_date", "id"]' in migration_text
    assert "CheckConstraint" not in migration_text
    assert "op.drop_table(\"portfolio_snapshots\")" in migration_text


def test_portfolio_snapshot_model_is_registered_in_metadata_and_alembic_env() -> None:
    alembic_env_text = ALEMBIC_ENV.read_text(encoding="utf-8")

    assert "portfolio_snapshots" in Base.metadata.tables
    assert "portfolio_snapshot" in model_package.__all__
    assert "from src.model import portfolio_snapshot" in alembic_env_text


def test_portfolio_snapshot_preserves_decimal_values_for_all_currencies(
    db_session: Session,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    snapshot = _snapshot(
        portfolio_id=portfolio.id,
        total_value_try=Decimal("1000.12345678"),
        total_value_usd=Decimal("30.87654321"),
        total_value_eur=Decimal("25.11111111"),
        total_value_gbp=Decimal("20.22222222"),
    )

    db_session.add(snapshot)
    db_session.flush()
    db_session.refresh(snapshot)

    assert snapshot.id is not None
    assert snapshot.total_value_try == Decimal("1000.12345678")
    assert snapshot.total_value_usd == Decimal("30.87654321")
    assert snapshot.total_value_eur == Decimal("25.11111111")
    assert snapshot.total_value_gbp == Decimal("20.22222222")
    assert isinstance(snapshot.total_value_try, Decimal)
    assert isinstance(snapshot.total_value_usd, Decimal)
    assert isinstance(snapshot.total_value_eur, Decimal)
    assert isinstance(snapshot.total_value_gbp, Decimal)


def test_portfolio_snapshot_duplicate_same_portfolio_date_rejected(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    db_session.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 7)))
    db_session.flush()
    db_session.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 7)))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_portfolio_snapshot_same_date_allowed_across_different_portfolios(
    db_session: Session,
) -> None:
    user = _add_user(db_session)
    first_portfolio = _add_portfolio(db_session, user_id=user.id, name="First")
    second_portfolio = _add_portfolio(db_session, user_id=user.id, name="Second")
    db_session.add(_snapshot(portfolio_id=first_portfolio.id, snapshot_date=date(2026, 9, 7)))
    db_session.add(_snapshot(portfolio_id=second_portfolio.id, snapshot_date=date(2026, 9, 7)))

    db_session.flush()

    assert db_session.query(PortfolioSnapshot).count() == 2


def test_portfolio_snapshot_allows_zero_and_negative_values(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    snapshot = _snapshot(
        portfolio_id=portfolio.id,
        total_value_try=Decimal("0"),
        total_value_usd=Decimal("-1.00000000"),
        total_value_eur=Decimal("0E-8"),
        total_value_gbp=Decimal("-20.12345678"),
    )

    db_session.add(snapshot)
    db_session.flush()
    db_session.refresh(snapshot)

    assert snapshot.total_value_try == Decimal("0E-8")
    assert snapshot.total_value_usd == Decimal("-1.00000000")
    assert snapshot.total_value_eur == Decimal("0E-8")
    assert snapshot.total_value_gbp == Decimal("-20.12345678")