from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.portfolio import Portfolio
from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.portfolio_cash_replay_service import (
    PORTFOLIO_CASH_REPLAY_REASON_TRANSACTION_CURRENCY_UNAVAILABLE,
    PORTFOLIO_CASH_REPLAY_STATUS_COMPLETE,
    PORTFOLIO_CASH_REPLAY_STATUS_INCOMPLETE,
    PortfolioCashReplayService,
)


AS_OF_DATE = date(2026, 9, 2)


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


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "CRS",
    currency: str | None = "TRY",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency=currency,
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_cash_flow(
    db_session: Session,
    *,
    portfolio_id: int,
    flow_type: str = "DEPOSIT",
    amount: Decimal = Decimal("10.00000000"),
    currency: str = "TRY",
    flow_date: date = AS_OF_DATE,
) -> PortfolioCashFlow:
    cash_flow = PortfolioCashFlow(
        portfolio_id=portfolio_id,
        flow_type=flow_type,
        amount=amount,
        currency=currency,
        flow_date=flow_date,
    )
    db_session.add(cash_flow)
    db_session.flush()
    return cash_flow


def _add_transaction(
    db_session: Session,
    *,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str = "BUY",
    quantity: Decimal = Decimal("2.00000000"),
    unit_price: Decimal = Decimal("3.00000000"),
    transaction_currency: str | None = "TRY",
    transaction_date: date = AS_OF_DATE,
) -> Transaction:
    transaction = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=unit_price,
        transaction_currency=transaction_currency,
        transaction_date=transaction_date,
    )
    db_session.add(transaction)
    db_session.flush()
    return transaction


def _create_service(db_session: Session) -> PortfolioCashReplayService:
    return PortfolioCashReplayService(
        portfolio_repository=PortfolioRepository(db_session),
        cash_flow_repository=PortfolioCashFlowRepository(db_session),
        transaction_repository=TransactionRepository(db_session),
    )


def _balances_by_currency(result) -> dict[str, Decimal]:
    return {balance.currency: balance.amount for balance in result.balances}


def test_empty_portfolio_returns_complete_with_empty_balances(db_session: Session) -> None:
    user = _create_user(db_session, email="cash-replay-empty@example.com", username="cash-replay-empty")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Empty Cash Replay")
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.portfolio_id == portfolio.id
    assert result.as_of_date == AS_OF_DATE
    assert result.status == PORTFOLIO_CASH_REPLAY_STATUS_COMPLETE
    assert result.unavailable_reason is None
    assert result.balances == []


def test_deposit_and_withdrawal_apply_positive_and_negative_signs(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="cash-replay-flows@example.com", username="cash-replay-flows")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Flows")
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="DEPOSIT",
        amount=Decimal("100.00000000"),
        currency="TRY",
    )
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("40.00000000"),
        currency="TRY",
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.status == PORTFOLIO_CASH_REPLAY_STATUS_COMPLETE
    assert _balances_by_currency(result) == {"TRY": Decimal("60.00000000")}


def test_buy_and_sell_apply_transaction_value_signs(db_session: Session) -> None:
    user = _create_user(db_session, email="cash-replay-trades@example.com", username="cash-replay-trades")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Trades")
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("2.50000000"),
        unit_price=Decimal("4.00000000"),
        transaction_currency="USD",
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("7.50000000"),
        transaction_currency="USD",
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert _balances_by_currency(result) == {"USD": Decimal("-2.5000000000000000")}


def test_mixed_events_accumulate_per_currency_with_exact_decimal_arithmetic(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="cash-replay-mixed@example.com", username="cash-replay-mixed")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Mixed")
    asset = _create_asset(db_session)
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("0.30000000"),
        currency="EUR",
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("0.10000000"),
        unit_price=Decimal("2.00000000"),
        transaction_currency="EUR",
    )
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("5.00000000"),
        currency="USD",
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("0.20000000"),
        unit_price=Decimal("10.00000000"),
        transaction_currency="USD",
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert [balance.currency for balance in result.balances] == ["EUR", "USD"]
    assert _balances_by_currency(result) == {
        "EUR": Decimal("0.1000000000000000"),
        "USD": Decimal("7.0000000000000000"),
    }


def test_future_transactions_and_cash_flows_do_not_affect_historical_cash(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="cash-replay-future@example.com", username="cash-replay-future")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Future")
    asset = _create_asset(db_session)
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("50.00000000"),
        currency="TRY",
        flow_date=AS_OF_DATE,
    )
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("500.00000000"),
        currency="TRY",
        flow_date=date(2026, 9, 3),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_currency="TRY",
        transaction_date=AS_OF_DATE,
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("100.00000000"),
        transaction_currency="TRY",
        transaction_date=date(2026, 9, 3),
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert _balances_by_currency(result) == {"TRY": Decimal("40.0000000000000000")}


def test_same_day_events_produce_daily_close_cash_without_cross_source_ordering(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="cash-replay-same-day@example.com", username="cash-replay-same-day")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Same Day")
    asset = _create_asset(db_session)
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="DEPOSIT",
        amount=Decimal("100.00000000"),
        currency="TRY",
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("3.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_currency="TRY",
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("15.00000000"),
        transaction_currency="TRY",
    )
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("5.00000000"),
        currency="TRY",
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert _balances_by_currency(result) == {"TRY": Decimal("80.0000000000000000")}


def test_negative_balances_are_preserved_and_zero_net_balances_are_omitted(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="cash-replay-negative@example.com", username="cash-replay-negative")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Negative")
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("10.00000000"),
        currency="GBP",
    )
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="DEPOSIT",
        amount=Decimal("5.00000000"),
        currency="EUR",
    )
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("5.00000000"),
        currency="EUR",
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert _balances_by_currency(result) == {"GBP": Decimal("-10.00000000")}


def test_legacy_null_transaction_currency_marks_incomplete_but_preserves_known_events(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="cash-replay-legacy@example.com", username="cash-replay-legacy")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Legacy")
    asset = _create_asset(db_session)
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("100.00000000"),
        currency="TRY",
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("999.00000000"),
        transaction_currency=None,
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("25.00000000"),
        transaction_currency="TRY",
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.status == PORTFOLIO_CASH_REPLAY_STATUS_INCOMPLETE
    assert (
        result.unavailable_reason
        == PORTFOLIO_CASH_REPLAY_REASON_TRANSACTION_CURRENCY_UNAVAILABLE
    )
    assert _balances_by_currency(result) == {"TRY": Decimal("125.0000000000000000")}


def test_not_owned_portfolio_returns_canonical_404(db_session: Session) -> None:
    owner = _create_user(db_session, email="cash-replay-owner@example.com", username="cash-replay-owner")
    other = _create_user(db_session, email="cash-replay-other@example.com", username="cash-replay-other")
    portfolio = _create_portfolio(db_session, user_id=owner.id, name="Cash Replay Owner")
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_cash_balances(
            portfolio_id=portfolio.id,
            current_user=other,
            as_of_date=AS_OF_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_asset_currency_is_not_used_or_inferred_for_transaction_cash_currency(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="cash-replay-asset-currency@example.com", username="cash-replay-asset-currency")
    portfolio = _create_portfolio(db_session, user_id=user.id, name="Cash Replay Asset Currency")
    asset = _create_asset(db_session, currency=None)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_currency="USD",
    )
    service = _create_service(db_session)

    result = service.get_cash_balances(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.status == PORTFOLIO_CASH_REPLAY_STATUS_COMPLETE
    assert _balances_by_currency(result) == {"USD": Decimal("-20.0000000000000000")}
