from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.portfolio import Portfolio
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.asset_repository import AssetRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.transaction_service import (
    TRANSACTION_CURRENCY_MISMATCH_DETAIL,
    TransactionService,
)


TRANSACTION_DATE = date(2026, 8, 25)


class FailingAddTransactionRepository(TransactionRepository):
    def add(self, transaction: Transaction) -> Transaction:
        self.db.add(transaction)
        self.db.flush()
        raise RuntimeError("transaction add failed")


class TrackingPortfolioRepository(PortfolioRepository):
    def __init__(self, db: Session) -> None:
        super().__init__(db)
        self.normal_lookup_calls = 0
        self.locking_lookup_calls = 0

    def get_by_id_for_user(self, portfolio_id: int, user_id: int) -> Portfolio | None:
        self.normal_lookup_calls += 1
        return super().get_by_id_for_user(portfolio_id, user_id)

    def get_by_id_for_user_for_update(
        self,
        portfolio_id: int,
        user_id: int,
    ) -> Portfolio | None:
        self.locking_lookup_calls += 1
        return super().get_by_id_for_user_for_update(portfolio_id, user_id)


def _create_user(db_session: Session, *, email: str, username: str) -> User:
    user = User(
        email=email,
        username=username,
        hashed_password="hashed-password",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _create_portfolio(db_session: Session, *, user_id: int, name: str) -> Portfolio:
    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        base_currency="TRY",
    )
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _create_asset(db_session: Session, *, asset_code: str = "AAL") -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _create_parents(db_session: Session) -> tuple[User, Portfolio, Asset]:
    user = _create_user(
        db_session,
        email="transaction-service@example.com",
        username="transaction-service",
    )
    portfolio = _create_portfolio(
        db_session,
        user_id=user.id,
        name="Transaction Portfolio",
    )
    asset = _create_asset(db_session)
    return user, portfolio, asset


def _create_service(
    db_session: Session,
    *,
    portfolio_repository: PortfolioRepository | None = None,
    transaction_repository: TransactionRepository | None = None,
) -> TransactionService:
    return TransactionService(
        db=db_session,
        portfolio_repository=portfolio_repository or PortfolioRepository(db_session),
        asset_repository=AssetRepository(db_session),
        transaction_repository=transaction_repository or TransactionRepository(db_session),
    )


def _create_transaction(
    service: TransactionService,
    *,
    portfolio_id: int,
    asset_id: int,
    current_user: User,
    transaction_type: str = "BUY",
    quantity: Decimal = Decimal("5.00000000"),
    unit_price: Decimal = Decimal("10.00000000"),
    transaction_currency: str = "TRY",
    transaction_date: date = TRANSACTION_DATE,
) -> Transaction:
    return service.create_transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=unit_price,
        transaction_currency=transaction_currency,
        transaction_date=transaction_date,
        current_user=current_user,
    )


def _count_transactions(db_session: Session) -> int:
    return int(db_session.scalar(select(func.count(Transaction.id))) or 0)


def test_valid_buy_succeeds(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)

    result = _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="BUY",
        quantity=Decimal("2.50000000"),
        unit_price=Decimal("12.34567890"),
    )

    assert result.id is not None
    assert result.portfolio_id == portfolio.id
    assert result.asset_id == asset.id
    assert result.transaction_type == "BUY"
    assert result.quantity == Decimal("2.50000000")
    assert result.unit_price == Decimal("12.34567890")
    assert result.transaction_currency == "TRY"


def test_portfolio_not_owned_returns_404_and_writes_nothing(db_session: Session) -> None:
    owner = _create_user(db_session, email="owner@example.com", username="owner")
    other_user = _create_user(db_session, email="other@example.com", username="other")
    portfolio = _create_portfolio(db_session, user_id=owner.id, name="Owner Portfolio")
    asset = _create_asset(db_session)
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _create_transaction(
            service,
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            current_user=other_user,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."
    assert _count_transactions(db_session) == 0


def test_asset_missing_returns_404_and_writes_nothing(db_session: Session) -> None:
    user = _create_user(db_session, email="asset-missing@example.com", username="asset-missing")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Asset Missing")
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _create_transaction(
            service,
            portfolio_id=portfolio.id,
            asset_id=1,
            current_user=user,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Asset not found."
    assert _count_transactions(db_session) == 0


def test_valid_sell_succeeds(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="BUY",
        quantity=Decimal("5.00000000"),
    )

    result = _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="SELL",
        quantity=Decimal("2.00000000"),
    )

    assert result.id is not None
    assert result.transaction_type == "SELL"
    assert result.quantity == Decimal("2.00000000")
    assert _count_transactions(db_session) == 2


def test_sell_greater_than_available_returns_422_and_writes_nothing(
    db_session: Session,
) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="BUY",
        quantity=Decimal("3.00000000"),
    )

    with pytest.raises(HTTPException) as exc_info:
        _create_transaction(
            service,
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            current_user=user,
            transaction_type="SELL",
            quantity=Decimal("4.00000000"),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Insufficient quantity for SELL."
    assert _count_transactions(db_session) == 1


def test_backdated_sell_that_makes_later_balance_negative_returns_422_and_writes_nothing(
    db_session: Session,
) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="BUY",
        quantity=Decimal("5.00000000"),
        transaction_date=date(2026, 8, 20),
    )
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        transaction_date=date(2026, 8, 30),
    )

    with pytest.raises(HTTPException) as exc_info:
        _create_transaction(
            service,
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            current_user=user,
            transaction_type="SELL",
            quantity=Decimal("2.00000000"),
            transaction_date=date(2026, 8, 25),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Insufficient quantity for SELL."
    assert _count_transactions(db_session) == 2


def test_successful_operation_commits_once_at_service_boundary(
    db_session: Session,
    monkeypatch,
) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
    )

    assert commit_calls == 1


def test_persistence_failure_rolls_back_and_leaves_no_new_transaction_row(
    db_session: Session,
    monkeypatch,
) -> None:
    user, portfolio, asset = _create_parents(db_session)
    rollback_calls = 0
    original_rollback = db_session.rollback

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(db_session, "rollback", counting_rollback)
    service = _create_service(
        db_session,
        transaction_repository=FailingAddTransactionRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="transaction add failed"):
        _create_transaction(
            service,
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            current_user=user,
        )

    assert rollback_calls == 1
    assert _count_transactions(db_session) == 0

def test_buy_uses_locking_portfolio_lookup(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    portfolio_repository = TrackingPortfolioRepository(db_session)
    service = _create_service(
        db_session,
        portfolio_repository=portfolio_repository,
    )

    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="BUY",
    )

    assert portfolio_repository.normal_lookup_calls == 0
    assert portfolio_repository.locking_lookup_calls == 1


def test_sell_uses_locking_portfolio_lookup(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    _create_transaction(
        _create_service(db_session),
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="BUY",
        quantity=Decimal("5.00000000"),
    )
    portfolio_repository = TrackingPortfolioRepository(db_session)
    service = _create_service(
        db_session,
        portfolio_repository=portfolio_repository,
    )

    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_type="SELL",
        quantity=Decimal("2.00000000"),
    )

    assert portfolio_repository.normal_lookup_calls == 0
    assert portfolio_repository.locking_lookup_calls == 1


def test_list_transactions_returns_owned_portfolio_history(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)
    first = _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_date=date(2026, 8, 24),
    )
    second = _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_date=date(2026, 8, 25),
    )

    result = service.list_transactions(
        portfolio_id=portfolio.id,
        current_user=user,
        skip=1,
        limit=1,
    )

    assert result.total == 2
    assert result.skip == 1
    assert result.limit == 1
    assert [item.id for item in result.items] == [second.id]
    assert result.items[0].quantity == first.quantity


def test_list_transactions_returns_empty_history(db_session: Session) -> None:
    user, portfolio, _asset = _create_parents(db_session)
    service = _create_service(db_session)

    result = service.list_transactions(
        portfolio_id=portfolio.id,
        current_user=user,
        skip=0,
        limit=50,
    )

    assert result.items == []
    assert result.total == 0
    assert result.skip == 0
    assert result.limit == 50


def test_list_transactions_for_non_owned_portfolio_returns_404(
    db_session: Session,
) -> None:
    owner = _create_user(
        db_session,
        email="list-owner@example.com",
        username="list-owner",
    )
    other_user = _create_user(
        db_session,
        email="list-other@example.com",
        username="list-other",
    )
    portfolio = _create_portfolio(db_session, user_id=owner.id, name="Owner Portfolio")
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.list_transactions(
            portfolio_id=portfolio.id,
            current_user=other_user,
            skip=0,
            limit=50,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_same_portfolio_asset_same_currency_is_accepted(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_currency="USD",
    )

    result = _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_currency="USD",
    )

    assert result.transaction_currency == "USD"


def test_same_portfolio_asset_different_non_null_currency_returns_422(
    db_session: Session,
) -> None:
    user, portfolio, asset = _create_parents(db_session)
    service = _create_service(db_session)
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_currency="TRY",
    )

    with pytest.raises(HTTPException) as exc_info:
        _create_transaction(
            service,
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            current_user=user,
            transaction_currency="USD",
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == TRANSACTION_CURRENCY_MISMATCH_DETAIL


def test_different_portfolio_may_use_different_currency(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    other_portfolio = _create_portfolio(
        db_session,
        user_id=user.id,
        name="Other Currency Portfolio",
    )
    service = _create_service(db_session)
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_currency="TRY",
    )

    result = _create_transaction(
        service,
        portfolio_id=other_portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_currency="USD",
    )

    assert result.transaction_currency == "USD"


def test_different_asset_may_use_different_currency(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    other_asset = _create_asset(db_session, asset_code="BBL")
    service = _create_service(db_session)
    _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_currency="TRY",
    )

    result = _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=other_asset.id,
        current_user=user,
        transaction_currency="USD",
    )

    assert result.transaction_currency == "USD"


def test_legacy_null_currency_does_not_block_new_currency(db_session: Session) -> None:
    user, portfolio, asset = _create_parents(db_session)
    db_session.add(
        Transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("1.00000000"),
            unit_price=Decimal("1.00000000"),
            transaction_currency=None,
            transaction_date=TRANSACTION_DATE,
        )
    )
    db_session.flush()
    service = _create_service(db_session)

    result = _create_transaction(
        service,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        current_user=user,
        transaction_currency="EUR",
    )

    assert result.transaction_currency == "EUR"
