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

from sqlalchemy.orm import Session

from src.model.note import Note
from src.repositories.note_repository import NoteRepository


def add_note(
    db_session: Session,
    *,
    user_id: int,
    portfolio_id: int,
    note_text: str,
    created_at: datetime,
) -> Note:
    note = Note(user_id=user_id, portfolio_id=portfolio_id, note_text=note_text, created_at=created_at)
    db_session.add(note)
    db_session.commit()
    db_session.refresh(note)
    return note


def test_repository_user_isolation_pagination_order_and_count(db_session: Session) -> None:
    user = add_user(db_session)
    other_user = add_user(db_session, email="other@example.com", username="other")
    portfolio = add_portfolio(db_session, user_id=user.id)
    other_portfolio = add_portfolio(db_session, user_id=other_user.id)
    old = add_note(db_session, user_id=user.id, portfolio_id=portfolio.id, note_text="old", created_at=datetime(2026, 9, 7, 8, 0, tzinfo=timezone.utc))
    first_same_time = add_note(db_session, user_id=user.id, portfolio_id=portfolio.id, note_text="first", created_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc))
    second_same_time = add_note(db_session, user_id=user.id, portfolio_id=portfolio.id, note_text="second", created_at=datetime(2026, 9, 7, 9, 0, tzinfo=timezone.utc))
    add_note(db_session, user_id=other_user.id, portfolio_id=other_portfolio.id, note_text="other", created_at=datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc))
    repository = NoteRepository(db_session)

    rows = repository.list_by_user(user_id=user.id, skip=1, limit=2)

    assert repository.count_by_user(user_id=user.id) == 3
    assert [row.id for row in rows] == [first_same_time.id, old.id]
    assert second_same_time.id > first_same_time.id


def test_repository_add_flushes_but_does_not_commit(db_session: Session, monkeypatch) -> None:
    user = add_user(db_session)
    portfolio = add_portfolio(db_session, user_id=user.id)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    note = Note(user_id=user.id, portfolio_id=portfolio.id, note_text="hello")

    created = NoteRepository(db_session).add(note)

    assert created.id is not None
    assert commit_calls == 0


def test_repository_get_by_owner_update_flushes_without_commit(db_session: Session, monkeypatch) -> None:
    user = add_user(db_session)
    other = add_user(db_session, email="other@example.com", username="other")
    portfolio = add_portfolio(db_session, user_id=user.id)
    note = add_note(
        db_session,
        user_id=user.id,
        portfolio_id=portfolio.id,
        note_text="before",
        created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    repository = NoteRepository(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    assert repository.get_by_id_for_user(note_id=note.id, user_id=user.id) is note
    assert repository.get_by_id_for_user(note_id=note.id, user_id=other.id) is None
    note.note_text = "after"
    assert repository.update(note) is note
    db_session.expire(note)

    assert commit_calls == 0
    assert note.note_text == "after"


def test_repository_delete_flushes_without_commit(db_session: Session, monkeypatch) -> None:
    user = add_user(db_session)
    portfolio = add_portfolio(db_session, user_id=user.id)
    note = add_note(
        db_session,
        user_id=user.id,
        portfolio_id=portfolio.id,
        note_text="before",
        created_at=datetime(2026, 9, 7, tzinfo=timezone.utc),
    )
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    NoteRepository(db_session).delete(note)

    assert commit_calls == 0
    assert db_session.get(Note, note.id) is None
