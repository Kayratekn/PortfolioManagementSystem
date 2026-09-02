from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.portfolio import Portfolio
from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.model.user import User
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.services.portfolio_cash_flow_service import PortfolioCashFlowService


FLOW_DATE = date(2026, 9, 2)


class FailingAddCashFlowRepository(PortfolioCashFlowRepository):
    def add(self, cash_flow: PortfolioCashFlow) -> PortfolioCashFlow:
        self.db.add(cash_flow)
        self.db.flush()
        raise RuntimeError("cash flow add failed")


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


def _create_service(
    db_session: Session,
    *,
    cash_flow_repository: PortfolioCashFlowRepository | None = None,
) -> PortfolioCashFlowService:
    return PortfolioCashFlowService(
        db=db_session,
        portfolio_repository=PortfolioRepository(db_session),
        cash_flow_repository=cash_flow_repository or PortfolioCashFlowRepository(db_session),
    )


def _create_cash_flow(
    service: PortfolioCashFlowService,
    *,
    portfolio_id: int,
    current_user: User,
    flow_type: str = "DEPOSIT",
    amount: Decimal = Decimal("10.00000000"),
    currency: str = "TRY",
    flow_date: date = FLOW_DATE,
) -> PortfolioCashFlow:
    return service.create_cash_flow(
        portfolio_id=portfolio_id,
        flow_type=flow_type,
        amount=amount,
        currency=currency,
        flow_date=flow_date,
        current_user=current_user,
    )


def _count_cash_flows(db_session: Session) -> int:
    return int(db_session.scalar(select(func.count(PortfolioCashFlow.id))) or 0)


def test_create_deposit_succeeds(db_session: Session) -> None:
    user = _create_user(db_session, email="cash-flow-create@example.com", username="cash-flow-create")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow Create")
    service = _create_service(db_session)

    result = _create_cash_flow(
        service,
        portfolio_id=portfolio.id,
        current_user=user,
        amount=Decimal("123.45678901"),
        currency="USD",
    )

    assert result.id is not None
    assert result.portfolio_id == portfolio.id
    assert result.flow_type == "DEPOSIT"
    assert result.amount == Decimal("123.45678901")
    assert result.currency == "USD"


def test_create_withdrawal_succeeds(db_session: Session) -> None:
    user = _create_user(
        db_session,
        email="cash-flow-withdrawal@example.com",
        username="cash-flow-withdrawal",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow Withdrawal")
    service = _create_service(db_session)

    result = _create_cash_flow(
        service,
        portfolio_id=portfolio.id,
        current_user=user,
        flow_type="WITHDRAWAL",
    )

    assert result.flow_type == "WITHDRAWAL"
    assert _count_cash_flows(db_session) == 1


def test_create_for_not_owned_portfolio_returns_404_and_writes_nothing(
    db_session: Session,
) -> None:
    owner = _create_user(db_session, email="cash-flow-owner@example.com", username="cash-flow-owner")
    other = _create_user(db_session, email="cash-flow-other@example.com", username="cash-flow-other")
    portfolio = _create_portfolio(db_session, user_id=owner.id, name="Owner Cash Flow")
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _create_cash_flow(service, portfolio_id=portfolio.id, current_user=other)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."
    assert _count_cash_flows(db_session) == 0


def test_persistence_failure_rolls_back_and_writes_nothing(db_session: Session) -> None:
    user = _create_user(db_session, email="cash-flow-fail@example.com", username="cash-flow-fail")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow Fail")
    service = _create_service(
        db_session,
        cash_flow_repository=FailingAddCashFlowRepository(db_session),
    )

    with pytest.raises(RuntimeError, match="cash flow add failed"):
        _create_cash_flow(service, portfolio_id=portfolio.id, current_user=user)

    assert _count_cash_flows(db_session) == 0


def test_list_cash_flows_returns_owned_portfolio_history(db_session: Session) -> None:
    user = _create_user(db_session, email="cash-flow-list@example.com", username="cash-flow-list")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Flow List")
    service = _create_service(db_session)
    first = _create_cash_flow(
        service,
        portfolio_id=portfolio.id,
        current_user=user,
        flow_date=date(2026, 9, 3),
    )
    second = _create_cash_flow(
        service,
        portfolio_id=portfolio.id,
        current_user=user,
        flow_date=date(2026, 9, 2),
    )
    third = _create_cash_flow(
        service,
        portfolio_id=portfolio.id,
        current_user=user,
        flow_type="WITHDRAWAL",
        flow_date=date(2026, 9, 2),
    )

    result = service.list_cash_flows(
        portfolio_id=portfolio.id,
        current_user=user,
        skip=1,
        limit=2,
    )

    assert result.total == 3
    assert result.skip == 1
    assert result.limit == 2
    assert [item.id for item in result.items] == [third.id, first.id]
    assert second.id < third.id


def test_list_for_not_owned_portfolio_returns_404(db_session: Session) -> None:
    owner = _create_user(
        db_session,
        email="cash-flow-list-owner@example.com",
        username="cash-flow-list-owner",
    )
    other = _create_user(
        db_session,
        email="cash-flow-list-other@example.com",
        username="cash-flow-list-other",
    )
    portfolio = _create_portfolio(db_session, user_id=owner.id, name="Owner Cash Flow")
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.list_cash_flows(
            portfolio_id=portfolio.id,
            current_user=other,
            skip=0,
            limit=50,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."
