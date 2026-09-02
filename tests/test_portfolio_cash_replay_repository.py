from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.portfolio import Portfolio
from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.transaction_repository import TransactionRepository


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
    portfolio = Portfolio(user_id=user_id, name=name, base_currency="TRY")
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _create_asset(db_session: Session, *, asset_code: str = "CFR") -> Asset:
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


def test_transaction_repository_lists_portfolio_transactions_on_or_before_date(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="cash-replay-transaction-repo@example.com",
        username="cash-replay-transaction-repo",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Tx")
    other_portfolio = _create_portfolio(db_session, user_id=user.id, name="Other Tx")
    asset = _create_asset(db_session)
    repository = TransactionRepository(db_session)
    future = Transaction(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("1.00000000"),
        transaction_currency="TRY",
        transaction_date=date(2026, 9, 4),
    )
    first_same_day = Transaction(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("1.00000000"),
        transaction_currency="TRY",
        transaction_date=date(2026, 9, 2),
    )
    second_same_day = Transaction(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("3.00000000"),
        transaction_currency="TRY",
        transaction_date=date(2026, 9, 2),
    )
    other = Transaction(
        portfolio_id=other_portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("9.00000000"),
        unit_price=Decimal("1.00000000"),
        transaction_currency="TRY",
        transaction_date=date(2026, 9, 1),
    )
    db_session.add_all([future, first_same_day, second_same_day, other])
    db_session.flush()

    result = repository.list_by_portfolio_on_or_before(
        portfolio_id=portfolio.id,
        transaction_date=date(2026, 9, 2),
    )

    assert [transaction.id for transaction in result] == [
        first_same_day.id,
        second_same_day.id,
    ]


def test_cash_flow_repository_lists_portfolio_cash_flows_on_or_before_date(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="cash-replay-flow-repo@example.com",
        username="cash-replay-flow-repo",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Flow")
    other_portfolio = _create_portfolio(db_session, user_id=user.id, name="Other Flow")
    repository = PortfolioCashFlowRepository(db_session)
    future = PortfolioCashFlow(
        portfolio_id=portfolio.id,
        flow_type="DEPOSIT",
        amount=Decimal("1.00000000"),
        currency="TRY",
        flow_date=date(2026, 9, 4),
    )
    first_same_day = PortfolioCashFlow(
        portfolio_id=portfolio.id,
        flow_type="DEPOSIT",
        amount=Decimal("2.00000000"),
        currency="TRY",
        flow_date=date(2026, 9, 2),
    )
    second_same_day = PortfolioCashFlow(
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("1.00000000"),
        currency="TRY",
        flow_date=date(2026, 9, 2),
    )
    other = PortfolioCashFlow(
        portfolio_id=other_portfolio.id,
        flow_type="DEPOSIT",
        amount=Decimal("9.00000000"),
        currency="TRY",
        flow_date=date(2026, 9, 1),
    )
    db_session.add_all([future, first_same_day, second_same_day, other])
    db_session.flush()

    result = repository.list_by_portfolio_on_or_before(
        portfolio_id=portfolio.id,
        flow_date=date(2026, 9, 2),
    )

    assert [cash_flow.id for cash_flow in result] == [
        first_same_day.id,
        second_same_day.id,
    ]
