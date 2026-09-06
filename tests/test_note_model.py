from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.model.portfolio import Portfolio
from src.model.user import User


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


def add_portfolio(
    db_session: Session,
    *,
    user_id: int,
    name: str = "Portfolio",
    deleted_at: datetime | None = None,
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        base_currency="TRY",
        deleted_at=deleted_at,
    )
    db_session.add(portfolio)
    db_session.commit()
    db_session.refresh(portfolio)
    return portfolio

from pathlib import Path

from sqlalchemy import Index, Text
from sqlalchemy.orm import Session

from src.model.note import Note


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0020 = PROJECT_ROOT / "alembic" / "versions" / "20260907_0020_create_notes.py"


def test_note_model_fields_foreign_keys_and_index() -> None:
    indexes = {index.name for index in Note.__table__.indexes if isinstance(index, Index)}

    assert Note.__table__.c.id.primary_key is True
    assert Note.__table__.c.user_id.nullable is False
    assert Note.__table__.c.portfolio_id.nullable is False
    assert Note.__table__.c.note_text.nullable is False
    assert isinstance(Note.__table__.c.note_text.type, Text)
    assert Note.__table__.c.created_at.nullable is False
    assert Note.__table__.c.updated_at.nullable is False
    assert "ix_notes_user_created_id" in indexes
    assert {fk.column.table.name for fk in Note.__table__.c.user_id.foreign_keys} == {"users"}
    assert {fk.column.table.name for fk in Note.__table__.c.portfolio_id.foreign_keys} == {"portfolios"}
    assert "asset_id" not in Note.__table__.c
    assert "title" not in Note.__table__.c
    assert "deleted_at" not in Note.__table__.c


def test_note_can_be_persisted(db_session: Session) -> None:
    user = add_user(db_session)
    portfolio = add_portfolio(db_session, user_id=user.id)
    note = Note(user_id=user.id, portfolio_id=portfolio.id, note_text="hello")

    db_session.add(note)
    db_session.flush()

    assert note.id is not None


def test_note_migration_revision_table_fk_and_index() -> None:
    migration_text = MIGRATION_0020.read_text(encoding="utf-8")

    assert 'revision = "20260907_0020"' in migration_text
    assert 'down_revision = "20260907_0019"' in migration_text
    assert '"notes"' in migration_text
    assert '"note_text"' in migration_text
    assert 'sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"])' in migration_text
    assert 'sa.ForeignKeyConstraint(["user_id"], ["users.id"])' in migration_text
    assert "ix_notes_user_created_id" in migration_text
    assert "asset_id" not in migration_text
    assert "deleted_at" not in migration_text
    assert 'op.drop_table("notes")' in migration_text


def test_note_model_registered_in_metadata() -> None:
    assert "notes" in Note.metadata.tables
