from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.portfolio import Portfolio
from src.model.portfolio_snapshot import PortfolioSnapshot
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.portfolio_snapshot_repository import PortfolioSnapshotRepository
from src.services.portfolio_snapshot_service import PortfolioSnapshotService


SNAPSHOT_DATE = date(2026, 9, 7)


def _add_user(db_session: Session, *, email: str = "snapshot@example.com") -> User:
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


def _add_portfolio(db_session: Session, *, user_id: int, name: str = "Portfolio") -> Portfolio:
    portfolio = Portfolio(user_id=user_id, name=name, base_currency="TRY")
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _add_snapshot(
    db_session: Session,
    *,
    portfolio_id: int,
    snapshot_date: date = SNAPSHOT_DATE,
) -> PortfolioSnapshot:
    snapshot = PortfolioSnapshot(
        portfolio_id=portfolio_id,
        snapshot_date=snapshot_date,
        total_value_try=Decimal("100.00000000"),
        total_value_usd=Decimal("10.00000000"),
        total_value_eur=Decimal("9.00000000"),
        total_value_gbp=Decimal("8.00000000"),
    )
    db_session.add(snapshot)
    db_session.flush()
    return snapshot


class FakeValuationService:
    def __init__(self, values: dict[str, SimpleNamespace] | None = None) -> None:
        self.values = values or {
            currency: _complete(Decimal("1")) for currency in ("TRY", "USD", "EUR", "GBP")
        }
        self.calls: list[str] = []
        self.call_kwargs: list[dict[str, object]] = []

    def get_valuation_in_currency(self, **kwargs: object) -> SimpleNamespace:
        currency = kwargs["target_currency"]
        assert isinstance(currency, str)
        self.calls.append(currency)
        self.call_kwargs.append(kwargs)
        return self.values[currency]


def _complete(total: Decimal) -> SimpleNamespace:
    return SimpleNamespace(status="COMPLETE", total_portfolio_value=total)


def _incomplete(total: Decimal | None = None) -> SimpleNamespace:
    return SimpleNamespace(status="INCOMPLETE", total_portfolio_value=total)


def _service(
    db_session: Session,
    valuation_service: FakeValuationService | None = None,
    snapshot_repository: PortfolioSnapshotRepository | None = None,
) -> PortfolioSnapshotService:
    return PortfolioSnapshotService(
        db_session,
        PortfolioRepository(db_session),
        snapshot_repository or PortfolioSnapshotRepository(db_session),
        valuation_service or FakeValuationService(),
    )


def _assert_canonical_valuation_call_arguments(
    valuation_service: FakeValuationService,
    *,
    portfolio: Portfolio,
    current_user: User,
    snapshot_date: date,
) -> None:
    assert valuation_service.call_kwargs == [
        {
            "portfolio_id": portfolio.id,
            "current_user": current_user,
            "valuation_date": snapshot_date,
            "target_currency": currency,
        }
        for currency in ("TRY", "USD", "EUR", "GBP")
    ]


def test_generation_enforces_ownership_isolation(db_session: Session) -> None:
    owner = _add_user(db_session, email="owner@example.com")
    other = _add_user(db_session, email="other@example.com")
    portfolio = _add_portfolio(db_session, user_id=owner.id)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).generate_snapshot(
            portfolio_id=portfolio.id,
            current_user=other,
            snapshot_date=SNAPSHOT_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_generation_locks_owned_portfolio_before_exact_date_lookup(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    repository = PortfolioSnapshotRepository(db_session)
    events: list[str] = []
    portfolio_repository = PortfolioRepository(db_session)
    original_lock = portfolio_repository.get_by_id_for_user_for_update
    original_get = repository.get_by_portfolio_and_date
    monkeypatch.setattr(
        portfolio_repository,
        "get_by_id_for_user_for_update",
        lambda *args: (events.append("lock"), original_lock(*args))[1],
    )
    monkeypatch.setattr(
        repository,
        "get_by_portfolio_and_date",
        lambda **kwargs: (events.append("exact"), original_get(**kwargs))[1],
    )
    service = PortfolioSnapshotService(
        db_session, portfolio_repository, repository, FakeValuationService()
    )

    service.generate_snapshot(
        portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
    )

    assert events[:2] == ["lock", "exact"]


def test_same_date_generation_returns_existing_snapshot_without_overwrite(
    db_session: Session,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    existing = _add_snapshot(db_session, portfolio_id=portfolio.id)
    valuation_service = FakeValuationService()

    result = _service(db_session, valuation_service).generate_snapshot(
        portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
    )

    assert result is existing
    assert valuation_service.calls == []
    assert existing.total_value_try == Decimal("100.00000000")
    assert len(
        PortfolioSnapshotRepository(db_session).list_by_portfolio_between(
            portfolio_id=portfolio.id,
            start_date=SNAPSHOT_DATE,
            end_date=SNAPSHOT_DATE,
        )
    ) == 1


def test_generation_values_all_supported_currencies_in_locked_order_and_persists_them(
    db_session: Session,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    valuation_service = FakeValuationService(
        {
            "TRY": _complete(Decimal("101.12345678")),
            "USD": _complete(Decimal("2.23456789")),
            "EUR": _complete(Decimal("3.34567891")),
            "GBP": _complete(Decimal("4.45678912")),
        }
    )

    snapshot = _service(db_session, valuation_service).generate_snapshot(
        portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
    )

    assert valuation_service.calls == ["TRY", "USD", "EUR", "GBP"]
    _assert_canonical_valuation_call_arguments(
        valuation_service,
        portfolio=portfolio,
        current_user=user,
        snapshot_date=SNAPSHOT_DATE,
    )
    assert snapshot.total_value_try == Decimal("101.12345678")
    assert snapshot.total_value_usd == Decimal("2.23456789")
    assert snapshot.total_value_eur == Decimal("3.34567891")
    assert snapshot.total_value_gbp == Decimal("4.45678912")


def test_generation_rounds_only_at_persistence_boundary_with_round_half_up(
    db_session: Session,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    valuation_service = FakeValuationService(
        {
            "TRY": _complete(Decimal("1.123456785")),
            "USD": _complete(Decimal("-1.123456785")),
            "EUR": _complete(Decimal("0.000000004")),
            "GBP": _complete(Decimal("0.000000005")),
        }
    )

    snapshot = _service(db_session, valuation_service).generate_snapshot(
        portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
    )

    assert snapshot.total_value_try == Decimal("1.12345679")
    assert snapshot.total_value_usd == Decimal("-1.12345679")
    assert snapshot.total_value_eur == Decimal("0.00000000")
    assert snapshot.total_value_gbp == Decimal("0.00000001")


def test_generation_allows_zero_and_negative_totals(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    valuation_service = FakeValuationService(
        {
            "TRY": _complete(Decimal("0")),
            "USD": _complete(Decimal("-1")),
            "EUR": _complete(Decimal("0")),
            "GBP": _complete(Decimal("-2")),
        }
    )

    snapshot = _service(db_session, valuation_service).generate_snapshot(
        portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
    )

    assert snapshot.total_value_try == Decimal("0E-8")
    assert snapshot.total_value_usd == Decimal("-1.00000000")
    assert snapshot.total_value_gbp == Decimal("-2.00000000")


@pytest.mark.parametrize(
    "bad_valuation",
    [_incomplete(Decimal("1")), _complete(None)],
)
def test_incomplete_or_null_valuation_rolls_back_and_creates_no_snapshot(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    bad_valuation: SimpleNamespace,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    db_session.commit()
    valuation_service = FakeValuationService(
        {
            "TRY": _complete(Decimal("1")),
            "USD": bad_valuation,
            "EUR": _complete(Decimal("1")),
            "GBP": _complete(Decimal("1")),
        }
    )
    rollback_calls = 0
    original_rollback = db_session.rollback

    def tracking_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", tracking_rollback)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session, valuation_service).generate_snapshot(
            portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Portfolio snapshot cannot be generated from incomplete valuation."
    assert rollback_calls == 1
    assert valuation_service.calls == ["TRY", "USD", "EUR", "GBP"]
    _assert_canonical_valuation_call_arguments(
        valuation_service,
        portfolio=portfolio,
        current_user=user,
        snapshot_date=SNAPSHOT_DATE,
    )
    assert PortfolioSnapshotRepository(db_session).get_by_portfolio_and_date(
        portfolio_id=portfolio.id, snapshot_date=SNAPSHOT_DATE
    ) is None


@pytest.mark.parametrize("failure_point", ["valuation", "repository", "commit"])
def test_generation_unexpected_failure_rolls_back_and_reraises(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    db_session.commit()
    valuation_service = FakeValuationService()
    snapshot_repository = PortfolioSnapshotRepository(db_session)
    if failure_point == "valuation":
        monkeypatch.setattr(
            valuation_service,
            "get_valuation_in_currency",
            lambda **kwargs: (_ for _ in ()).throw(RuntimeError("valuation failed")),
        )
    elif failure_point == "repository":
        monkeypatch.setattr(
            snapshot_repository,
            "add",
            lambda snapshot: (_ for _ in ()).throw(RuntimeError("add failed")),
        )
    else:
        monkeypatch.setattr(
            db_session,
            "commit",
            lambda: (_ for _ in ()).throw(RuntimeError("commit failed")),
        )
    rollback_calls = 0
    original_rollback = db_session.rollback

    def tracking_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", tracking_rollback)

    with pytest.raises(RuntimeError):
        _service(db_session, valuation_service, snapshot_repository).generate_snapshot(
            portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
        )

    assert rollback_calls == 1
    assert PortfolioSnapshotRepository(db_session).get_by_portfolio_and_date(
        portfolio_id=portfolio.id, snapshot_date=SNAPSHOT_DATE
    ) is None


def test_generation_refresh_failure_rolls_back_before_commit(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    db_session.commit()
    commit_calls = 0
    rollback_calls = 0
    original_rollback = db_session.rollback

    def tracking_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    def tracking_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    def failing_refresh(snapshot: PortfolioSnapshot) -> None:
        raise RuntimeError("refresh failed")

    monkeypatch.setattr(db_session, "commit", tracking_commit)
    monkeypatch.setattr(db_session, "rollback", tracking_rollback)
    monkeypatch.setattr(db_session, "refresh", failing_refresh)

    with pytest.raises(RuntimeError, match="refresh failed"):
        _service(db_session).generate_snapshot(
            portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
        )

    assert commit_calls == 0
    assert rollback_calls == 1
    assert PortfolioSnapshotRepository(db_session).get_by_portfolio_and_date(
        portfolio_id=portfolio.id, snapshot_date=SNAPSHOT_DATE
    ) is None


def test_generation_rolls_back_when_valuation_raises_http_exception(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    db_session.commit()
    valuation_service = FakeValuationService()
    rollback_calls = 0
    original_rollback = db_session.rollback

    def tracking_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", tracking_rollback)
    monkeypatch.setattr(
        valuation_service,
        "get_valuation_in_currency",
        lambda **kwargs: (_ for _ in ()).throw(
            HTTPException(status_code=503, detail="valuation unavailable")
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session, valuation_service).generate_snapshot(
            portfolio_id=portfolio.id, current_user=user, snapshot_date=SNAPSHOT_DATE
        )

    assert exc_info.value.status_code == 503
    assert rollback_calls == 1
    assert PortfolioSnapshotRepository(db_session).get_by_portfolio_and_date(
        portfolio_id=portfolio.id, snapshot_date=SNAPSHOT_DATE
    ) is None


def test_list_enforces_ownership_isolation(db_session: Session) -> None:
    owner = _add_user(db_session, email="owner@example.com")
    other = _add_user(db_session, email="other@example.com")
    portfolio = _add_portfolio(db_session, user_id=owner.id)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).list_snapshots(
            portfolio_id=portfolio.id,
            current_user=other,
            start_date=SNAPSHOT_DATE,
            end_date=SNAPSHOT_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_list_returns_ownership_404_before_rejecting_invalid_range(
    db_session: Session,
) -> None:
    owner = _add_user(db_session, email="owner@example.com")
    other = _add_user(db_session, email="other@example.com")
    portfolio = _add_portfolio(db_session, user_id=owner.id)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).list_snapshots(
            portfolio_id=portfolio.id,
            current_user=other,
            start_date=SNAPSHOT_DATE + timedelta(days=1),
            end_date=SNAPSHOT_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_list_returns_only_inclusive_persisted_history_and_never_values_dynamically(
    db_session: Session,
) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    outside = _add_snapshot(
        db_session, portfolio_id=portfolio.id, snapshot_date=SNAPSHOT_DATE - timedelta(days=1)
    )
    first = _add_snapshot(db_session, portfolio_id=portfolio.id)
    last = _add_snapshot(
        db_session, portfolio_id=portfolio.id, snapshot_date=SNAPSHOT_DATE + timedelta(days=2)
    )
    valuation_service = FakeValuationService()

    snapshots = _service(db_session, valuation_service).list_snapshots(
        portfolio_id=portfolio.id,
        current_user=user,
        start_date=SNAPSHOT_DATE,
        end_date=SNAPSHOT_DATE + timedelta(days=2),
    )

    assert snapshots == [first, last]
    assert outside not in snapshots
    assert valuation_service.calls == []


def test_list_rejects_inverted_date_range(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).list_snapshots(
            portfolio_id=portfolio.id,
            current_user=user,
            start_date=SNAPSHOT_DATE + timedelta(days=1),
            end_date=SNAPSHOT_DATE,
        )

    assert exc_info.value.status_code == 422


def test_list_accepts_366_days_and_rejects_367_days(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    service = _service(db_session)

    assert service.list_snapshots(
        portfolio_id=portfolio.id,
        current_user=user,
        start_date=SNAPSHOT_DATE,
        end_date=SNAPSHOT_DATE + timedelta(days=365),
    ) == []
    with pytest.raises(HTTPException) as exc_info:
        service.list_snapshots(
            portfolio_id=portfolio.id,
            current_user=user,
            start_date=SNAPSHOT_DATE,
            end_date=SNAPSHOT_DATE + timedelta(days=366),
        )

    assert exc_info.value.status_code == 422


def test_list_empty_persisted_history_returns_empty_list(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)

    assert _service(db_session).list_snapshots(
        portfolio_id=portfolio.id,
        current_user=user,
        start_date=SNAPSHOT_DATE,
        end_date=SNAPSHOT_DATE,
    ) == []
