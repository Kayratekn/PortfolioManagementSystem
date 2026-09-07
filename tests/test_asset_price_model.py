from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.model as model_package
from src.model.asset import Asset
from src.model.asset_price import AssetPrice
from src.model.base import Base


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0021 = PROJECT_ROOT / "alembic" / "versions" / "20260907_0021_create_asset_prices.py"
ALEMBIC_ENV = PROJECT_ROOT / "alembic" / "env.py"


def _add_asset(
    db_session: Session,
    *,
    asset_code: str = "XAU_GR",
    data_source: str = "MANUAL",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Asset",
        asset_type="PRECIOUS_METAL",
        fund_kind=None,
        currency="TRY",
        data_source=data_source,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _asset_price(
    *,
    asset_id: int,
    price_date: date = date(2026, 9, 7),
    price: Decimal = Decimal("1234.56789012"),
    source: str = "TEST_SOURCE",
) -> AssetPrice:
    return AssetPrice(
        asset_id=asset_id,
        price_date=price_date,
        price=price,
        source=source,
    )


def test_asset_price_model_defines_required_fields_constraints_unique_and_index() -> None:
    constraints = AssetPrice.__table__.constraints
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
        index.name: tuple(index.columns.keys())
        for index in AssetPrice.__table__.indexes
        if isinstance(index, Index)
    }
    foreign_keys = AssetPrice.__table__.c.asset_id.foreign_keys

    assert AssetPrice.__table__.c.id.primary_key is True
    assert AssetPrice.__table__.c.asset_id.nullable is False
    assert AssetPrice.__table__.c.price_date.nullable is False
    assert AssetPrice.__table__.c.price.nullable is False
    assert AssetPrice.__table__.c.source.nullable is False
    assert AssetPrice.__table__.c.price.type.precision == 20
    assert AssetPrice.__table__.c.price.type.scale == 8
    assert AssetPrice.__table__.c.source.type.length == 50
    assert unique_constraints[("asset_id", "price_date", "source")] == (
        "uq_asset_prices_asset_date_source"
    )
    assert "ck_asset_prices_price_positive" in check_constraints
    assert "ck_asset_prices_source_nonblank" in check_constraints
    assert indexes["ix_asset_prices_asset_date_id"] == ("asset_id", "price_date", "id")
    assert len(foreign_keys) == 1
    assert next(iter(foreign_keys)).target_fullname == "assets.id"
    assert "created_at" in AssetPrice.__table__.c
    assert "updated_at" in AssetPrice.__table__.c


def test_asset_price_migration_revision_table_constraints_and_index() -> None:
    migration_text = MIGRATION_0021.read_text(encoding="utf-8")

    assert 'revision = "20260907_0021"' in migration_text
    assert 'down_revision = "20260907_0020"' in migration_text
    assert '"asset_prices"' in migration_text
    assert '"asset_id"' in migration_text
    assert '"price_date"' in migration_text
    assert "sa.Numeric(precision=20, scale=8)" in migration_text
    assert "sa.String(length=50)" in migration_text
    assert 'sa.ForeignKeyConstraint(["asset_id"], ["assets.id"])' in migration_text
    assert 'name="ck_asset_prices_price_positive"' in migration_text
    assert '"length(trim(source)) > 0"' in migration_text
    assert 'name="ck_asset_prices_source_nonblank"' in migration_text
    assert 'name="uq_asset_prices_asset_date_source"' in migration_text
    assert '"ix_asset_prices_asset_date_id"' in migration_text
    assert '["asset_id", "price_date", "id"]' in migration_text
    assert "op.drop_table(\"asset_prices\")" in migration_text


def test_asset_price_model_is_registered_in_metadata_and_alembic_env() -> None:
    alembic_env_text = ALEMBIC_ENV.read_text(encoding="utf-8")

    assert "asset_prices" in Base.metadata.tables
    assert "asset_price" in model_package.__all__
    assert "from src.model import asset_price" in alembic_env_text


def test_asset_price_preserves_decimal_value(db_session: Session) -> None:
    asset = _add_asset(db_session)
    asset_price = _asset_price(asset_id=asset.id, price=Decimal("1234.56789012"))

    db_session.add(asset_price)
    db_session.flush()
    db_session.refresh(asset_price)

    assert asset_price.id is not None
    assert asset_price.price == Decimal("1234.56789012")
    assert isinstance(asset_price.price, Decimal)


@pytest.mark.parametrize("price", [Decimal("0"), Decimal("-0.00000001")])
def test_asset_price_db_constraint_rejects_non_positive_price(
    db_session: Session,
    price: Decimal,
) -> None:
    asset = _add_asset(db_session)
    db_session.add(_asset_price(asset_id=asset.id, price=price))

    with pytest.raises(IntegrityError):
        db_session.flush()


@pytest.mark.parametrize("source", ["", "   "])
def test_asset_price_db_constraint_rejects_blank_or_whitespace_source(
    db_session: Session,
    source: str,
) -> None:
    asset = _add_asset(db_session)
    db_session.add(_asset_price(asset_id=asset.id, source=source))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_asset_price_unique_asset_date_source_rejects_duplicate(db_session: Session) -> None:
    asset = _add_asset(db_session)
    db_session.add(_asset_price(asset_id=asset.id))
    db_session.flush()
    db_session.add(_asset_price(asset_id=asset.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_asset_price_allows_same_asset_date_with_different_source(db_session: Session) -> None:
    asset = _add_asset(db_session)
    db_session.add(_asset_price(asset_id=asset.id, source="SOURCE_A"))
    db_session.add(_asset_price(asset_id=asset.id, source="SOURCE_B"))

    db_session.flush()

    assert db_session.query(AssetPrice).count() == 2


def test_asset_price_allows_same_date_source_across_different_assets(db_session: Session) -> None:
    first_asset = _add_asset(db_session, asset_code="XAU_GR", data_source="MANUAL_A")
    second_asset = _add_asset(db_session, asset_code="XAG_GR", data_source="MANUAL_A")
    db_session.add(_asset_price(asset_id=first_asset.id))
    db_session.add(_asset_price(asset_id=second_asset.id))

    db_session.flush()

    assert db_session.query(AssetPrice).count() == 2


def test_asset_price_foreign_key_rejects_missing_asset(db_session: Session) -> None:
    db_session.execute(text("PRAGMA foreign_keys=ON"))
    db_session.add(_asset_price(asset_id=999999))

    with pytest.raises(IntegrityError):
        db_session.flush()