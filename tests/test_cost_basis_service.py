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
from src.services.cost_basis_service import (
    COST_BASIS_ITEM_STATUS_COMPLETE,
    COST_BASIS_ITEM_STATUS_UNAVAILABLE,
    COST_BASIS_PORTFOLIO_STATUS_COMPLETE,
    COST_BASIS_PORTFOLIO_STATUS_INCOMPLETE,
    COST_BASIS_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE,
    CostBasisService,
)

AS_OF_DATE = date(2026, 8, 25)


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


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_name: str | None = None,
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name or f"{asset_code} Example Asset",
        asset_type=asset_type,
        fund_kind=fund_kind,
        currency=currency,
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_transaction(
    db_session: Session,
    *,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str = "BUY",
    quantity: Decimal = Decimal("10.00000000"),
    unit_price: Decimal = Decimal("20.00000000"),
    transaction_currency: str | None = None,
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


def _create_service(db_session: Session) -> CostBasisService:
    return CostBasisService(
        portfolio_repository=PortfolioRepository(db_session),
        transaction_repository=TransactionRepository(db_session),
    )


def _owned_portfolio(db_session: Session) -> tuple[User, Portfolio]:
    user = _create_user(
        db_session,
        email="cost-basis-owner@example.com",
        username="cost-basis-owner",
    )
    portfolio = _create_portfolio(
        db_session,
        user_id=user.id,
        name="Cost Basis Portfolio",
    )
    return user, portfolio


def test_portfolio_ownership_violation_returns_404(db_session: Session) -> None:
    owner = _create_user(
        db_session,
        email="cost-basis-owned@example.com",
        username="cost-basis-owned",
    )
    other_user = _create_user(
        db_session,
        email="cost-basis-other@example.com",
        username="cost-basis-other",
    )
    portfolio = _create_portfolio(db_session, user_id=owner.id, name="Owned")
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_cost_basis(
            portfolio_id=portfolio.id,
            current_user=other_user,
            as_of_date=AS_OF_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_empty_portfolio_returns_complete_empty_items(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.portfolio_id == portfolio.id
    assert result.as_of_date == AS_OF_DATE
    assert result.status == COST_BASIS_PORTFOLIO_STATUS_COMPLETE
    assert result.items == ()


def test_single_buy_calculates_total_and_average_cost(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("20.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.status == COST_BASIS_PORTFOLIO_STATUS_COMPLETE
    item = result.items[0]
    assert item.asset_id == asset.id
    assert item.asset_code == "AAL"
    assert item.asset_name == "AAL Example Asset"
    assert item.asset_currency == "TRY"
    assert item.status == COST_BASIS_ITEM_STATUS_COMPLETE
    assert item.unavailable_reason is None
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis == Decimal("200.0000000000000000")
    assert item.average_cost_per_unit == Decimal("20.00000000")


def test_multiple_buys_calculate_moving_weighted_average(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("20.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("30.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert item.quantity == Decimal("20.00000000")
    assert item.total_cost_basis == Decimal("500.0000000000000000")
    assert item.average_cost_per_unit == Decimal("25.00000000")


def test_partial_sell_keeps_average_cost_unchanged(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        unit_price=Decimal("30.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("999.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis == Decimal("250.0000000000000000")
    assert item.average_cost_per_unit == Decimal("25.00000000")


def test_full_sell_asset_is_omitted_from_result(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.status == COST_BASIS_PORTFOLIO_STATUS_COMPLETE
    assert result.items == ()


def test_full_sell_followed_by_later_buy_resets_state(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_date=date(2026, 8, 20),
        unit_price=Decimal("20.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        transaction_date=date(2026, 8, 21),
        unit_price=Decimal("999.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        unit_price=Decimal("30.00000000"),
        transaction_date=date(2026, 8, 22),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert item.quantity == Decimal("5.00000000")
    assert item.total_cost_basis == Decimal("150.0000000000000000")
    assert item.average_cost_per_unit == Decimal("30.00000000")


def test_historical_as_of_date_excludes_future_buy(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_date=date(2026, 8, 20),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        unit_price=Decimal("30.00000000"),
        transaction_date=date(2026, 8, 27),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert item.quantity == Decimal("5.00000000")
    assert item.total_cost_basis == Decimal("50.0000000000000000")
    assert item.average_cost_per_unit == Decimal("10.00000000")


def test_historical_as_of_date_excludes_future_sell(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_date=date(2026, 8, 20),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        transaction_date=date(2026, 8, 27),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis == Decimal("200.0000000000000000")
    assert item.average_cost_per_unit == Decimal("20.00000000")


def test_transaction_on_exact_as_of_date_is_included(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_date=date(2026, 8, 20),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("5.00000000"),
        unit_price=Decimal("30.00000000"),
        transaction_date=AS_OF_DATE,
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis == Decimal("200.0000000000000000")
    assert item.average_cost_per_unit == Decimal("20.00000000")


def test_same_date_id_ordering_affects_replay_deterministically(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    first = _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        unit_price=Decimal("20.00000000"),
    )
    second = _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        unit_price=Decimal("999.00000000"),
    )
    third = _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        unit_price=Decimal("30.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert first.id < second.id < third.id
    item = result.items[0]
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis == Decimal("300.0000000000000000")
    assert item.average_cost_per_unit == Decimal("30.00000000")


def test_multiple_assets_are_calculated_independently(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    first_asset = _create_asset(db_session, asset_code="AAA")
    second_asset = _create_asset(db_session, asset_code="BBB", currency="USD")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=first_asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("20.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=second_asset.id,
        quantity=Decimal("3.00000000"),
        unit_price=Decimal("7.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    first_item, second_item = result.items
    assert first_item.asset_id == first_asset.id
    assert first_item.total_cost_basis == Decimal("200.0000000000000000")
    assert second_item.asset_id == second_asset.id
    assert second_item.asset_currency == "USD"
    assert second_item.total_cost_basis == Decimal("21.0000000000000000")


def test_missing_asset_currency_returns_unavailable_item_and_incomplete_result(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, currency=None)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_currency="TRY",
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.status == COST_BASIS_PORTFOLIO_STATUS_INCOMPLETE
    item = result.items[0]
    assert item.status == COST_BASIS_ITEM_STATUS_UNAVAILABLE
    assert item.unavailable_reason == (
        COST_BASIS_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE
    )
    assert item.asset_currency is None
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis is None
    assert item.average_cost_per_unit is None


def test_blank_asset_currency_returns_unavailable_item(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, currency="   ")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert result.status == COST_BASIS_PORTFOLIO_STATUS_INCOMPLETE
    assert item.asset_currency == "   "
    assert item.status == COST_BASIS_ITEM_STATUS_UNAVAILABLE
    assert item.total_cost_basis is None
    assert item.average_cost_per_unit is None


def test_complete_item_remains_complete_when_another_item_is_unavailable(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    complete_asset = _create_asset(db_session, asset_code="CMP")
    unavailable_asset = _create_asset(db_session, asset_code="UNC", currency=None)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=complete_asset.id)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=unavailable_asset.id)
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    complete_item, unavailable_item = result.items
    assert result.status == COST_BASIS_PORTFOLIO_STATUS_INCOMPLETE
    assert complete_item.status == COST_BASIS_ITEM_STATUS_COMPLETE
    assert complete_item.total_cost_basis == Decimal("200.0000000000000000")
    assert unavailable_item.status == COST_BASIS_ITEM_STATUS_UNAVAILABLE


def test_non_tefas_manual_non_fund_asset_with_known_currency_works(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(
        db_session,
        asset_code="MSFT",
        asset_name="Microsoft",
        asset_type="STOCK",
        fund_kind=None,
        currency="USD",
        data_source="MANUAL",
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("100.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert item.asset_code == "MSFT"
    assert item.asset_currency == "USD"
    assert item.total_cost_basis == Decimal("200.0000000000000000")
    assert item.average_cost_per_unit == Decimal("100.00000000")


def test_decimal_precision_is_preserved_without_float_rounding_or_quantize(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("1.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("2.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("1.00000000"),
        unit_price=Decimal("99.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_cost_basis(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = result.items[0]
    assert isinstance(item.total_cost_basis, Decimal)
    assert isinstance(item.average_cost_per_unit, Decimal)
    assert item.average_cost_per_unit == Decimal("1.666666666666666666666666667")
    assert item.total_cost_basis == Decimal("3.333333333333333333333333333")


def test_invalid_historical_oversell_raises_value_error(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("5.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("10.00000000"),
    )
    service = _create_service(db_session)

    with pytest.raises(ValueError, match="SELL exceeding quantity"):
        service.get_cost_basis(
            portfolio_id=portfolio.id,
            current_user=user,
            as_of_date=AS_OF_DATE,
        )


def test_replay_quantity_must_match_holdings_quantity() -> None:
    user = User(
        id=1,
        email="fake-user@example.com",
        username="fake-user",
        hashed_password="hashed-password",
        preferred_currency="TRY",
        is_active=True,
    )
    asset = Asset(
        id=10,
        asset_code="FAK",
        asset_name="Fake Asset",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        is_active=True,
    )
    transaction = Transaction(
        id=1,
        portfolio_id=20,
        asset_id=asset.id,
        transaction_type="BUY",
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("20.00000000"),
        transaction_date=AS_OF_DATE,
    )

    class FakePortfolioRepository:
        def get_by_id_for_user(self, portfolio_id: int, user_id: int) -> object:
            return object()

    class FakeTransactionRepository:
        def list_holdings_by_portfolio_on_or_before(
            self,
            *,
            portfolio_id: int,
            transaction_date: date,
        ) -> list[tuple[Asset, Decimal]]:
            return [(asset, Decimal("9.00000000"))]

        def list_by_portfolio_and_asset_on_or_before(
            self,
            *,
            portfolio_id: int,
            asset_id: int,
            transaction_date: date,
        ) -> list[Transaction]:
            return [transaction]

    service = CostBasisService(
        portfolio_repository=FakePortfolioRepository(),
        transaction_repository=FakeTransactionRepository(),
    )

    with pytest.raises(ValueError, match="replay quantity"):
        service.get_cost_basis(
            portfolio_id=20,
            current_user=user,
            as_of_date=AS_OF_DATE,
        )