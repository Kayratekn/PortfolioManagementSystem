from __future__ import annotations

import inspect
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
from src.services import realized_pl_service
from src.services.realized_pl_service import (
    REALIZED_PL_ITEM_STATUS_COMPLETE,
    REALIZED_PL_ITEM_STATUS_UNAVAILABLE,
    REALIZED_PL_RESULT_STATUS_COMPLETE,
    REALIZED_PL_RESULT_STATUS_INCOMPLETE,
    REALIZED_PL_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE,
    RealizedPlService,
)

AS_OF_DATE = date(2026, 8, 25)


def _create_user(db_session: Session, email: str = "realized@example.com") -> User:
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password="hashed-password",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _create_portfolio(db_session: Session, user_id: int) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, name="Realized P/L", base_currency="TRY")
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _create_asset(
    db_session: Session,
    code: str = "AAL",
    currency: str | None = "TRY",
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=code,
        asset_name=f"{code} Example Asset",
        asset_type=asset_type,
        fund_kind=fund_kind,
        currency=currency,
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_tx(
    db_session: Session,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str = "BUY",
    quantity: str = "10.00000000",
    unit_price: str = "20.00000000",
    transaction_date: date = AS_OF_DATE,
) -> Transaction:
    tx = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        transaction_date=transaction_date,
    )
    db_session.add(tx)
    db_session.flush()
    return tx


def _service(db_session: Session) -> RealizedPlService:
    return RealizedPlService(PortfolioRepository(db_session), TransactionRepository(db_session))


def _owned(db_session: Session) -> tuple[User, Portfolio]:
    user = _create_user(db_session)
    return user, _create_portfolio(db_session, user.id)


def _run_single(
    db_session: Session,
    txs: list[dict[str, object]],
    currency: str | None = "TRY",
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    data_source: str = "TEFAS",
):
    user, portfolio = _owned(db_session)
    asset = _create_asset(db_session, currency=currency, asset_type=asset_type, fund_kind=fund_kind, data_source=data_source)
    for tx in txs:
        _add_tx(db_session, portfolio.id, asset.id, **tx)
    result = _service(db_session).get_realized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF_DATE)
    return result, result.items[0], asset


def test_portfolio_ownership_violation_returns_404(db_session: Session) -> None:
    owner = _create_user(db_session, "realized-owner@example.com")
    other = _create_user(db_session, "realized-other@example.com")
    portfolio = _create_portfolio(db_session, owner.id)

    with pytest.raises(HTTPException) as exc_info:
        _service(db_session).get_realized_pl(portfolio_id=portfolio.id, current_user=other, as_of_date=AS_OF_DATE)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_no_sells_returns_complete_empty_items(db_session: Session) -> None:
    user, portfolio = _owned(db_session)
    asset = _create_asset(db_session)
    _add_tx(db_session, portfolio.id, asset.id)

    result = _service(db_session).get_realized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF_DATE)

    assert result.portfolio_id == portfolio.id
    assert result.as_of_date == AS_OF_DATE
    assert result.status == REALIZED_PL_RESULT_STATUS_COMPLETE
    assert result.items == ()


@pytest.mark.parametrize(
    ("sell_price", "expected_pl"),
    [("30.00000000", "40.0000000000000000"), ("20.00000000", "0E-16"), ("15.00000000", "-20.0000000000000000")],
)
def test_single_buy_sell_positive_zero_and_negative_pl(db_session: Session, sell_price: str, expected_pl: str) -> None:
    _result, item, asset = _run_single(db_session, [{}, {"transaction_type": "SELL", "quantity": "4.00000000", "unit_price": sell_price}])

    assert item.asset_id == asset.id
    assert item.asset_code == "AAL"
    assert item.asset_name == "AAL Example Asset"
    assert item.asset_currency == "TRY"
    assert item.status == REALIZED_PL_ITEM_STATUS_COMPLETE
    assert item.unavailable_reason is None
    assert item.sold_quantity == Decimal("4.00000000")
    assert item.realized_proceeds == Decimal("4.00000000") * Decimal(sell_price)
    assert item.realized_cost_basis == Decimal("80.0000000000000000")
    assert item.native_realized_pl == Decimal(expected_pl)


def test_multiple_buys_use_mwac_at_sell_point_and_partial_sell(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"quantity": "10.00000000", "unit_price": "20.00000000"},
        {"quantity": "10.00000000", "unit_price": "30.00000000"},
        {"transaction_type": "SELL", "quantity": "4.00000000", "unit_price": "40.00000000"},
    ])

    assert item.sold_quantity == Decimal("4.00000000")
    assert item.realized_proceeds == Decimal("160.0000000000000000")
    assert item.realized_cost_basis == Decimal("100.0000000000000000")
    assert item.native_realized_pl == Decimal("60.0000000000000000")


def test_multiple_sells_accumulate_all_realized_fields(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"quantity": "10.00000000", "unit_price": "20.00000000"},
        {"transaction_type": "SELL", "quantity": "2.00000000", "unit_price": "30.00000000"},
        {"transaction_type": "SELL", "quantity": "3.00000000", "unit_price": "10.00000000"},
    ])

    assert item.sold_quantity == Decimal("5.00000000")
    assert item.realized_proceeds == Decimal("90.0000000000000000")
    assert item.realized_cost_basis == Decimal("100.0000000000000000")
    assert item.native_realized_pl == Decimal("-10.0000000000000000")


def test_sell_unit_price_affects_proceeds_pl_not_mwac_cost_removed(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [{}, {"transaction_type": "SELL", "quantity": "5.00000000", "unit_price": "1.00000000"}])

    assert item.realized_proceeds == Decimal("5.0000000000000000")
    assert item.realized_cost_basis == Decimal("100.0000000000000000")
    assert item.native_realized_pl == Decimal("-95.0000000000000000")


def test_full_sell_retained_and_later_buy_starts_new_cycle(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"unit_price": "20.00000000"},
        {"transaction_type": "SELL", "unit_price": "25.00000000"},
        {"quantity": "5.00000000", "unit_price": "30.00000000"},
    ])

    assert item.sold_quantity == Decimal("10.00000000")
    assert item.realized_proceeds == Decimal("250.0000000000000000")
    assert item.realized_cost_basis == Decimal("200.0000000000000000")
    assert item.native_realized_pl == Decimal("50.0000000000000000")


def test_later_sell_after_reentry_uses_new_cycle_average_cost(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"unit_price": "20.00000000"},
        {"transaction_type": "SELL", "unit_price": "25.00000000"},
        {"quantity": "5.00000000", "unit_price": "30.00000000"},
        {"transaction_type": "SELL", "quantity": "2.00000000", "unit_price": "40.00000000"},
    ])

    assert item.sold_quantity == Decimal("12.00000000")
    assert item.realized_cost_basis == Decimal("260.0000000000000000")
    assert item.native_realized_pl == Decimal("70.0000000000000000")


def test_future_buy_and_future_sell_excluded_exact_as_of_included(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"transaction_date": date(2026, 8, 24)},
        {"transaction_type": "SELL", "quantity": "2.00000000", "unit_price": "30.00000000", "transaction_date": AS_OF_DATE},
        {"quantity": "100.00000000", "unit_price": "1.00000000", "transaction_date": date(2026, 8, 26)},
        {"transaction_type": "SELL", "quantity": "3.00000000", "unit_price": "40.00000000", "transaction_date": date(2026, 8, 26)},
    ])

    assert item.sold_quantity == Decimal("2.00000000")
    assert item.realized_proceeds == Decimal("60.0000000000000000")
    assert item.realized_cost_basis == Decimal("40.0000000000000000")


def test_same_date_id_ordering_affects_replay_deterministically(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"quantity": "10.00000000", "unit_price": "20.00000000"},
        {"transaction_type": "SELL", "unit_price": "999.00000000"},
        {"quantity": "10.00000000", "unit_price": "30.00000000"},
        {"transaction_type": "SELL", "quantity": "5.00000000", "unit_price": "40.00000000"},
    ])

    assert item.realized_cost_basis == Decimal("350.0000000000000000")
    assert item.native_realized_pl == Decimal("9840.0000000000000000")


def test_multiple_assets_independent_fully_sold_included_buy_only_omitted(db_session: Session) -> None:
    user, portfolio = _owned(db_session)
    first = _create_asset(db_session, "AAA")
    second = _create_asset(db_session, "BBB", "USD")
    buy_only = _create_asset(db_session, "BUY")
    _add_tx(db_session, portfolio.id, first.id)
    _add_tx(db_session, portfolio.id, first.id, "SELL", "10.00000000", "30.00000000")
    _add_tx(db_session, portfolio.id, second.id, quantity="3.00000000", unit_price="7.00000000")
    _add_tx(db_session, portfolio.id, second.id, "SELL", "1.00000000", "10.00000000")
    _add_tx(db_session, portfolio.id, buy_only.id)

    result = _service(db_session).get_realized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF_DATE)

    first_item, second_item = result.items
    assert [item.asset_id for item in result.items] == [first.id, second.id]
    assert first_item.native_realized_pl == Decimal("100.0000000000000000")
    assert second_item.asset_currency == "USD"
    assert second_item.native_realized_pl == Decimal("3.0000000000000000")


@pytest.mark.parametrize("currency", [None, "   "])
def test_missing_or_blank_currency_unavailable_keeps_quantity_hides_money(db_session: Session, currency: str | None) -> None:
    result, item, _asset = _run_single(db_session, [{}, {"transaction_type": "SELL", "quantity": "4.00000000", "unit_price": "30.00000000"}], currency=currency)

    assert result.status == REALIZED_PL_RESULT_STATUS_INCOMPLETE
    assert item.status == REALIZED_PL_ITEM_STATUS_UNAVAILABLE
    assert item.unavailable_reason == REALIZED_PL_UNAVAILABLE_REASON_ASSET_CURRENCY_UNAVAILABLE
    assert item.asset_currency == currency
    assert item.sold_quantity == Decimal("4.00000000")
    assert item.realized_proceeds is None
    assert item.realized_cost_basis is None
    assert item.native_realized_pl is None


def test_complete_item_remains_complete_inside_incomplete_result(db_session: Session) -> None:
    user, portfolio = _owned(db_session)
    complete = _create_asset(db_session, "CMP")
    unavailable = _create_asset(db_session, "UNC", None)
    for asset in (complete, unavailable):
        _add_tx(db_session, portfolio.id, asset.id)
        _add_tx(db_session, portfolio.id, asset.id, "SELL", "5.00000000", "30.00000000")

    result = _service(db_session).get_realized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF_DATE)

    complete_item, unavailable_item = result.items
    assert result.status == REALIZED_PL_RESULT_STATUS_INCOMPLETE
    assert complete_item.status == REALIZED_PL_ITEM_STATUS_COMPLETE
    assert complete_item.native_realized_pl == Decimal("50.0000000000000000")
    assert unavailable_item.status == REALIZED_PL_ITEM_STATUS_UNAVAILABLE


def test_manual_non_tefas_asset_with_known_currency_works(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"quantity": "2.00000000", "unit_price": "100.00000000"},
        {"transaction_type": "SELL", "quantity": "1.00000000", "unit_price": "125.00000000"},
    ], currency="USD", asset_type="STOCK", fund_kind=None, data_source="MANUAL")

    assert item.asset_currency == "USD"
    assert item.native_realized_pl == Decimal("25.0000000000000000")


def test_decimal_precision_preserved(db_session: Session) -> None:
    _result, item, _asset = _run_single(db_session, [
        {"quantity": "1.00000000", "unit_price": "1.00000000"},
        {"quantity": "2.00000000", "unit_price": "2.00000000"},
        {"transaction_type": "SELL", "quantity": "1.00000000", "unit_price": "3.00000000"},
    ])

    assert isinstance(item.realized_proceeds, Decimal)
    assert isinstance(item.realized_cost_basis, Decimal)
    assert isinstance(item.native_realized_pl, Decimal)
    assert item.realized_cost_basis == Decimal("1.666666666666666666666666667")
    assert item.native_realized_pl == Decimal("1.333333333333333333333333333")


def test_realized_pl_service_does_not_use_float_round_or_quantize() -> None:
    source = inspect.getsource(realized_pl_service)

    assert "float" not in source
    assert "round(" not in source
    assert "quantize" not in source


def test_invalid_historical_oversell_raises_value_error(db_session: Session) -> None:
    user, portfolio = _owned(db_session)
    asset = _create_asset(db_session)
    _add_tx(db_session, portfolio.id, asset.id, "SELL", "5.00000000")
    _add_tx(db_session, portfolio.id, asset.id, "BUY", "10.00000000")

    with pytest.raises(ValueError, match="SELL exceeding quantity"):
        _service(db_session).get_realized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF_DATE)


def test_internal_sell_asset_without_sold_quantity_fails_loudly() -> None:
    user = User(id=1, email="fake@example.com", username="fake", hashed_password="hashed", preferred_currency="TRY", is_active=True)
    asset = Asset(id=10, asset_code="FAK", asset_name="Fake", asset_type="FUND", fund_kind="YAT", currency="TRY", data_source="TEFAS", is_active=True)
    tx = Transaction(id=1, portfolio_id=20, asset_id=10, transaction_type="BUY", quantity=Decimal("10.00000000"), unit_price=Decimal("20.00000000"), transaction_date=AS_OF_DATE)

    class FakePortfolioRepository:
        def get_by_id_for_user(self, portfolio_id: int, user_id: int) -> object:
            return object()

    class FakeTransactionRepository:
        def list_assets_with_sell_on_or_before(self, *, portfolio_id: int, transaction_date: date) -> list[Asset]:
            return [asset]

        def list_by_portfolio_and_asset_on_or_before(self, *, portfolio_id: int, asset_id: int, transaction_date: date) -> list[Transaction]:
            return [tx]

    service = RealizedPlService(FakePortfolioRepository(), FakeTransactionRepository())

    with pytest.raises(ValueError, match="no sold quantity"):
        service.get_realized_pl(portfolio_id=20, current_user=user, as_of_date=AS_OF_DATE)
