from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.portfolio import Portfolio
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.holding_service import HoldingService


TRANSACTION_DATE = date(2026, 8, 25)


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


def _build_transaction(
    *,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str = "BUY",
    quantity: Decimal = Decimal("5.00000000"),
) -> Transaction:
    return Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=Decimal("10.00000000"),
        transaction_date=TRANSACTION_DATE,
    )


def _create_service(db_session: Session) -> HoldingService:
    return HoldingService(
        portfolio_repository=PortfolioRepository(db_session),
        transaction_repository=TransactionRepository(db_session),
    )


def test_owned_portfolio_with_holdings_returns_asset_metadata_quantity_and_total(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="holdings-owner@example.com", username="holdings-owner")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Holdings Portfolio")
    asset = _create_asset(db_session)
    transaction_repository = TransactionRepository(db_session)
    transaction_repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("10.50000000"),
        )
    )
    transaction_repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("4.00000000"),
        )
    )
    service = _create_service(db_session)

    result = service.list_holdings(portfolio_id=portfolio.id, current_user=user)

    assert result.total == 1
    assert len(result.items) == 1
    item = result.items[0]
    assert item.asset_id == asset.id
    assert item.asset_code == asset.asset_code
    assert item.asset_name == asset.asset_name
    assert item.asset_type == asset.asset_type
    assert item.fund_kind == asset.fund_kind
    assert item.currency == asset.currency
    assert item.data_source == asset.data_source
    assert item.quantity == Decimal("6.50000000")
    assert isinstance(item.quantity, Decimal)


def test_owned_portfolio_with_no_current_holdings_returns_empty_items_and_zero_total(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="no-holdings@example.com", username="no-holdings")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="No Holdings Portfolio")
    service = _create_service(db_session)

    result = service.list_holdings(portfolio_id=portfolio.id, current_user=user)

    assert result.items == []
    assert result.total == 0


def test_portfolio_not_owned_returns_404(db_session: Session) -> None:
    owner = _create_user(db_session, email="holding-owner@example.com", username="holding-owner")
    other_user = _create_user(db_session, email="holding-other@example.com", username="holding-other")
    portfolio = _create_portfolio(db_session, user_id=owner.id, name="Owner Portfolio")
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.list_holdings(portfolio_id=portfolio.id, current_user=other_user)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_another_portfolio_transactions_do_not_appear(db_session: Session) -> None:
    user = _create_user(db_session, email="isolated-holdings@example.com", username="isolated-holdings")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Requested Portfolio")
    other_portfolio = _create_portfolio(db_session, user_id=user.id, name="Other Portfolio")
    asset = _create_asset(db_session)
    transaction_repository = TransactionRepository(db_session)
    transaction_repository.add(
        _build_transaction(
            portfolio_id=other_portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("9.00000000"),
        )
    )
    service = _create_service(db_session)

    result = service.list_holdings(portfolio_id=portfolio.id, current_user=user)

    assert result.items == []
    assert result.total == 0