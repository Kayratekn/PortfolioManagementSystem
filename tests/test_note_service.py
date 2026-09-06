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

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.note import Note
from src.repositories.note_repository import NoteRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.services.note_service import NoteService


def service(db_session: Session) -> NoteService:
    return NoteService(
        db=db_session,
        note_repository=NoteRepository(db_session),
        portfolio_repository=PortfolioRepository(db_session),
    )


def test_service_creates_owned_portfolio_note(db_session: Session) -> None:
    user = add_user(db_session)
    portfolio = add_portfolio(db_session, user_id=user.id)

    created = service(db_session).create_note(portfolio_id=portfolio.id, note_text="hello", current_user=user)

    assert created.portfolio_id == portfolio.id
    assert created.note_text == "hello"
    persisted = db_session.get(Note, created.id)
    assert persisted is not None
    assert persisted.user_id == user.id


def test_service_foreign_missing_and_deleted_portfolio_return_404(db_session: Session) -> None:
    user = add_user(db_session)
    other = add_user(db_session, email="other@example.com", username="other")
    foreign_portfolio = add_portfolio(db_session, user_id=other.id)
    deleted_portfolio = add_portfolio(db_session, user_id=user.id, deleted_at=datetime(2026, 9, 7, tzinfo=timezone.utc))

    for portfolio_id in [foreign_portfolio.id, deleted_portfolio.id, 999999]:
        with pytest.raises(HTTPException) as exc_info:
            service(db_session).create_note(portfolio_id=portfolio_id, note_text="hello", current_user=user)
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Portfolio not found."


def test_same_portfolio_can_have_multiple_identical_notes(db_session: Session) -> None:
    user = add_user(db_session)
    portfolio = add_portfolio(db_session, user_id=user.id)

    first = service(db_session).create_note(portfolio_id=portfolio.id, note_text="same", current_user=user)
    second = service(db_session).create_note(portfolio_id=portfolio.id, note_text="same", current_user=user)

    assert first.id != second.id
    assert service(db_session).list_notes(current_user=user, skip=0, limit=50).total == 2


def test_service_list_user_isolation_and_deleted_portfolio_note_remains_listable(db_session: Session) -> None:
    user = add_user(db_session)
    other = add_user(db_session, email="other@example.com", username="other")
    portfolio = add_portfolio(db_session, user_id=user.id)
    other_portfolio = add_portfolio(db_session, user_id=other.id)
    created = service(db_session).create_note(portfolio_id=portfolio.id, note_text="visible", current_user=user)
    service(db_session).create_note(portfolio_id=other_portfolio.id, note_text="hidden", current_user=other)
    portfolio.deleted_at = datetime(2026, 9, 7, tzinfo=timezone.utc)
    db_session.commit()

    listed = service(db_session).list_notes(current_user=user, skip=0, limit=50)

    assert listed.total == 1
    assert listed.items[0].id == created.id
    assert listed.items[0].note_text == "visible"


def test_service_rolls_back_create_failure(db_session: Session, monkeypatch) -> None:
    user = add_user(db_session)
    portfolio = add_portfolio(db_session, user_id=user.id)
    rollback_calls = 0

    def failing_commit() -> None:
        raise RuntimeError("commit failed")

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1

    monkeypatch.setattr(db_session, "commit", failing_commit)
    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(RuntimeError, match="commit failed"):
        service(db_session).create_note(portfolio_id=portfolio.id, note_text="hello", current_user=user)

    assert rollback_calls == 1
