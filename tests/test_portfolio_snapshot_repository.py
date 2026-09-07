from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.portfolio import Portfolio
from src.model.portfolio_snapshot import PortfolioSnapshot
from src.model.user import User
from src.repositories.portfolio_snapshot_repository import PortfolioSnapshotRepository


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
    snapshot_date: date,
    total_value_try: Decimal = Decimal("100.00000000"),
) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=snapshot_date,
        total_value_try=total_value_try,
        total_value_usd=Decimal("10.00000000"),
        total_value_eur=Decimal("9.00000000"),
        total_value_gbp=Decimal("8.00000000"),
    )


def test_portfolio_snapshot_repository_add_get_exact_and_decimal_persistence(
    db_session: Session,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    repository = PortfolioSnapshotRepository(db_session)
    snapshot = _snapshot(
        portfolio_id=portfolio.id,
        snapshot_date=date(2026, 9, 7),
        total_value_try=Decimal("1234.56789012"),
    )

    result = repository.add(snapshot)

    assert result is snapshot
    assert snapshot.id is not None
    assert snapshot.total_value_try == Decimal("1234.56789012")
    assert isinstance(snapshot.total_value_try, Decimal)
    assert repository.get_by_portfolio_and_date(
        portfolio_id=portfolio.id,
        snapshot_date=date(2026, 9, 7),
    ) is snapshot
    assert repository.get_by_portfolio_and_date(
        portfolio_id=portfolio.id,
        snapshot_date=date(2026, 9, 8),
    ) is None


def test_latest_on_or_before_ignores_future_rows(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    repository = PortfolioSnapshotRepository(db_session)
    closest_prior = repository.add(
        _snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 6))
    )
    future = repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 8)))

    result = repository.get_latest_on_or_before(
        portfolio_id=portfolio.id,
        snapshot_date=date(2026, 9, 7),
    )

    assert result is closest_prior
    assert result is not future


def test_range_is_inclusive_and_portfolio_isolated(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id, name="Selected")
    other_portfolio = _add_portfolio(db_session, user_id=user.id, name="Other")
    repository = PortfolioSnapshotRepository(db_session)
    outside_before = repository.add(
        _snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 4))
    )
    start = repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 5)))
    middle = repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 6)))
    end = repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 7)))
    outside_after = repository.add(
        _snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 8))
    )
    other_portfolio_row = repository.add(
        _snapshot(portfolio_id=other_portfolio.id, snapshot_date=date(2026, 9, 6))
    )

    result = repository.list_by_portfolio_between(
        portfolio_id=portfolio.id,
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 7),
    )

    assert result == [start, middle, end]
    assert outside_before not in result
    assert outside_after not in result
    assert other_portfolio_row not in result


def test_latest_by_portfolio_returns_latest_for_selected_portfolio(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id, name="Selected")
    other_portfolio = _add_portfolio(db_session, user_id=user.id, name="Other")
    repository = PortfolioSnapshotRepository(db_session)
    repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 5)))
    latest = repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 7)))
    other_latest = repository.add(
        _snapshot(portfolio_id=other_portfolio.id, snapshot_date=date(2026, 9, 8))
    )

    result = repository.get_latest_by_portfolio(portfolio_id=portfolio.id)

    assert result is latest
    assert result is not other_latest


def test_repository_ordering_is_deterministic(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    repository = PortfolioSnapshotRepository(db_session)
    older = repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 5)))
    newer = repository.add(_snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 7)))

    latest_on_or_before = repository.get_latest_on_or_before(
        portfolio_id=portfolio.id,
        snapshot_date=date(2026, 9, 7),
    )
    latest_by_portfolio = repository.get_latest_by_portfolio(portfolio_id=portfolio.id)
    range_result = repository.list_by_portfolio_between(
        portfolio_id=portfolio.id,
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 7),
    )

    assert newer.id > older.id
    assert latest_on_or_before is newer
    assert latest_by_portfolio is newer
    assert range_result == [older, newer]


def test_portfolio_snapshot_repository_add_flushes_but_does_not_commit(
    db_session: Session,
    monkeypatch,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    snapshot = _snapshot(portfolio_id=portfolio.id, snapshot_date=date(2026, 9, 7))

    created = PortfolioSnapshotRepository(db_session).add(snapshot)

    assert created.id is not None
    assert commit_calls == 0