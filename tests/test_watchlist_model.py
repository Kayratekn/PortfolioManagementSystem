from __future__ import annotations

from src.model.asset import Asset
from src.model.user import User
from sqlalchemy.orm import Session


def add_user(db_session: Session, *, email: str = "user@example.com", username: str = "user") -> User:
    user = User(
        email=email,
        username=username,
        hashed_password="hashed",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def add_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_name: str = "Example Fund",
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    isin: str | None = "TRTESTISIN01",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
    is_active: bool = True,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type=asset_type,
        fund_kind=fund_kind,
        isin=isin,
        currency=currency,
        data_source=data_source,
        is_active=is_active,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset

from pathlib import Path

import pytest
from sqlalchemy import Index, UniqueConstraint, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.watchlist_item import WatchlistItem


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0018 = PROJECT_ROOT / "alembic" / "versions" / "20260907_0018_create_watchlist_items.py"


def test_watchlist_item_model_defines_required_fields_constraints_and_index() -> None:
    constraints = WatchlistItem.__table__.constraints
    unique_constraints = {
        tuple(constraint.columns.keys()): constraint.name
        for constraint in constraints
        if isinstance(constraint, UniqueConstraint)
    }
    indexes = {index.name for index in WatchlistItem.__table__.indexes if isinstance(index, Index)}

    assert WatchlistItem.__table__.c.id.primary_key is True
    assert WatchlistItem.__table__.c.user_id.nullable is False
    assert WatchlistItem.__table__.c.asset_id.nullable is False
    assert WatchlistItem.__table__.c.created_at.nullable is False
    assert WatchlistItem.__table__.c.updated_at.nullable is False
    assert unique_constraints[("user_id", "asset_id")] == "uq_watchlist_items_user_asset"
    assert "ix_watchlist_items_user_id_id" in indexes


def test_watchlist_unique_user_asset_constraint(db_session: Session) -> None:
    user = add_user(db_session)
    asset = add_asset(db_session)

    db_session.add(WatchlistItem(user_id=user.id, asset_id=asset.id))
    db_session.add(WatchlistItem(user_id=user.id, asset_id=asset.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_watchlist_allows_same_asset_for_different_users(db_session: Session) -> None:
    first_user = add_user(db_session, email="first@example.com", username="first")
    second_user = add_user(db_session, email="second@example.com", username="second")
    asset = add_asset(db_session)

    db_session.add(WatchlistItem(user_id=first_user.id, asset_id=asset.id))
    db_session.add(WatchlistItem(user_id=second_user.id, asset_id=asset.id))
    db_session.flush()

    rows = db_session.query(WatchlistItem).all()
    assert len(rows) == 2


def test_watchlist_migration_uses_expected_revision_and_names() -> None:
    migration_text = MIGRATION_0018.read_text(encoding="utf-8")

    assert 'revision = "20260907_0018"' in migration_text
    assert 'down_revision = "20260903_0017"' in migration_text
    assert 'op.create_table(' in migration_text
    assert '"watchlist_items"' in migration_text
    assert "uq_watchlist_items_user_asset" in migration_text
    assert "ix_watchlist_items_user_id_id" in migration_text
    assert "op.drop_index" in migration_text
    assert 'op.drop_table("watchlist_items")' in migration_text
    assert "PROJECT_STATUS" not in migration_text


def test_watchlist_table_is_registered_in_metadata() -> None:
    assert "watchlist_items" in WatchlistItem.metadata.tables
