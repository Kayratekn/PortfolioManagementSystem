from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.portfolio import Portfolio
from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.model.user import User
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository


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


def _build_cash_flow(
    *,
    portfolio_id: int,
    flow_type: str = "DEPOSIT",
    amount: Decimal = Decimal("10.00000000"),
    currency: str = "TRY",
    flow_date: date = date(2026, 9, 2),
) -> PortfolioCashFlow:
    return PortfolioCashFlow(
        portfolio_id=portfolio_id,
        flow_type=flow_type,
        amount=amount,
        currency=currency,
        flow_date=flow_date,
    )


def test_add_persists_cash_flow(db_session: Session) -> None:
    user = _create_user(db_session, email="cash-flow-repo@example.com", username="cash-flow-repo")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow Repo")
    repository = PortfolioCashFlowRepository(db_session)

    result = repository.add(_build_cash_flow(portfolio_id=portfolio.id))

    assert result.id is not None
    assert result.amount == Decimal("10.00000000")


def test_list_by_portfolio_orders_by_flow_date_then_id_and_paginates(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="cash-flow-order@example.com",
        username="cash-flow-order",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow Order")
    repository = PortfolioCashFlowRepository(db_session)
    first = repository.add(
        _build_cash_flow(portfolio_id=portfolio.id, flow_date=date(2026, 9, 3))
    )
    second = repository.add(
        _build_cash_flow(portfolio_id=portfolio.id, flow_date=date(2026, 9, 2))
    )
    third = repository.add(
        _build_cash_flow(
            portfolio_id=portfolio.id,
            flow_type="WITHDRAWAL",
            flow_date=date(2026, 9, 2),
        )
    )

    result = repository.list_by_portfolio(portfolio_id=portfolio.id, skip=1, limit=2)

    assert [cash_flow.id for cash_flow in result] == [third.id, first.id]
    assert second.id < third.id


def test_count_by_portfolio_isolates_portfolios(db_session: Session) -> None:
    user = _create_user(
        db_session,
        email="cash-flow-count@example.com",
        username="cash-flow-count",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow Count")
    other_portfolio = _create_portfolio(db_session, user_id=user.id, name="Other Count")
    repository = PortfolioCashFlowRepository(db_session)
    repository.add(_build_cash_flow(portfolio_id=portfolio.id))
    repository.add(_build_cash_flow(portfolio_id=portfolio.id, flow_type="WITHDRAWAL"))
    repository.add(_build_cash_flow(portfolio_id=other_portfolio.id))

    assert repository.count_by_portfolio(portfolio_id=portfolio.id) == 2

def test_list_by_portfolio_between_filters_inclusive_range_and_orders(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="cash-flow-between@example.com",
        username="cash-flow-between",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow Between")
    other_portfolio = _create_portfolio(db_session, user_id=user.id, name="Other Between")
    repository = PortfolioCashFlowRepository(db_session)
    before = repository.add(_build_cash_flow(portfolio_id=portfolio.id, flow_date=date(2026, 9, 1)))
    start = repository.add(_build_cash_flow(portfolio_id=portfolio.id, flow_date=date(2026, 9, 2)))
    end_first = repository.add(_build_cash_flow(portfolio_id=portfolio.id, flow_date=date(2026, 9, 3)))
    end_second = repository.add(_build_cash_flow(portfolio_id=portfolio.id, flow_type="WITHDRAWAL", flow_date=date(2026, 9, 3)))
    after = repository.add(_build_cash_flow(portfolio_id=portfolio.id, flow_date=date(2026, 9, 4)))
    other = repository.add(_build_cash_flow(portfolio_id=other_portfolio.id, flow_date=date(2026, 9, 2)))

    result = repository.list_by_portfolio_between(
        portfolio_id=portfolio.id,
        start_date=date(2026, 9, 2),
        end_date=date(2026, 9, 3),
    )

    result_ids = [cash_flow.id for cash_flow in result]
    assert result_ids == [start.id, end_first.id, end_second.id]
    assert before.id not in result_ids
    assert after.id not in result_ids
    assert other.id not in result_ids
