from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.portfolio import Portfolio
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.cost_basis_service import (
    CostBasisItem,
    CostBasisResult,
    CostBasisService,
)
from src.services.tefas_valuation_price_service import TefasValuationPriceService
from src.services.unrealized_pl_service import (
    ITEM_STATUS_COMPLETE,
    ITEM_STATUS_UNAVAILABLE,
    REASON_ASSET_CURRENCY_UNAVAILABLE,
    REASON_PRICE_UNAVAILABLE,
    REASON_UNSUPPORTED_ASSET,
    RESULT_STATUS_COMPLETE,
    RESULT_STATUS_INCOMPLETE,
    UnrealizedPlService,
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


def _create_portfolio(
    db_session: Session,
    *,
    user_id: int,
    name: str = "Unrealized P/L Portfolio",
    base_currency: str = "TRY",
) -> Portfolio:
    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        base_currency=base_currency,
    )
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "UPL",
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
    transaction_date: date = date(2026, 8, 20),
) -> Transaction:
    transaction = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=unit_price,
        transaction_date=transaction_date,
    )
    db_session.add(transaction)
    db_session.flush()
    return transaction


def _add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date = AS_OF_DATE,
    price: Decimal = Decimal("25.00000000"),
    exchange_bulletin_price: Decimal | None = None,
) -> TefasFundDailyData:
    daily_data = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("25000.0000"),
        exchange_bulletin_price=exchange_bulletin_price,
    )
    db_session.add(daily_data)
    db_session.flush()
    return daily_data


def _create_service(db_session: Session) -> UnrealizedPlService:
    transaction_repository = TransactionRepository(db_session)
    return UnrealizedPlService(
        cost_basis_service=CostBasisService(
            portfolio_repository=PortfolioRepository(db_session),
            transaction_repository=transaction_repository,
        ),
        transaction_repository=transaction_repository,
        tefas_valuation_price_service=TefasValuationPriceService(
            TefasFundDailyDataRepository(db_session),
        ),
    )


def _owned_portfolio(db_session: Session) -> tuple[User, Portfolio]:
    user = _create_user(
        db_session,
        email="unrealized-pl-owner@example.com",
        username="unrealized-pl-owner",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id)
    return user, portfolio


def _only_item(result):
    assert len(result.items) == 1
    return result.items[0]


def test_ownership_violation_preserves_existing_404(db_session: Session) -> None:
    owner = _create_user(
        db_session,
        email="unrealized-owner@example.com",
        username="unrealized-owner",
    )
    other = _create_user(
        db_session,
        email="unrealized-other@example.com",
        username="unrealized-other",
    )
    portfolio = _create_portfolio(db_session, user_id=owner.id)
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_unrealized_pl(
            portfolio_id=portfolio.id,
            current_user=other,
            as_of_date=AS_OF_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_empty_portfolio_returns_complete_empty_items(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.portfolio_id == portfolio.id
    assert result.as_of_date == AS_OF_DATE
    assert result.status == RESULT_STATUS_COMPLETE
    assert result.items == ()


def test_positive_unrealized_pl(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="POS")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert result.status == RESULT_STATUS_COMPLETE
    assert item.status == ITEM_STATUS_COMPLETE
    assert item.native_market_value == Decimal("250.0000000000000000")
    assert item.native_unrealized_pl == Decimal("50.0000000000000000")


def test_zero_unrealized_pl(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="ZER")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("20.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.native_market_value == Decimal("200.0000000000000000")
    assert item.native_unrealized_pl == Decimal("0E-16")


def test_negative_unrealized_pl(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="NEG")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("15.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.native_market_value == Decimal("150.0000000000000000")
    assert item.native_unrealized_pl == Decimal("-50.0000000000000000")


def test_multiple_buys_use_existing_moving_weighted_average_cost_basis(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="MWA")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        unit_price=Decimal("30.00000000"),
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("40.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.quantity == Decimal("20.00000000")
    assert item.total_cost_basis == Decimal("500.0000000000000000")
    assert item.average_cost_per_unit == Decimal("25.00000000")
    assert item.native_market_value == Decimal("800.0000000000000000")
    assert item.native_unrealized_pl == Decimal("300.0000000000000000")


def test_partial_sell_keeps_cost_basis_and_ignores_sell_unit_price(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="SEL")
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
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("40.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis == Decimal("250.0000000000000000")
    assert item.average_cost_per_unit == Decimal("25.00000000")
    assert item.native_market_value == Decimal("400.0000000000000000")
    assert item.native_unrealized_pl == Decimal("150.0000000000000000")


def test_fully_sold_asset_is_omitted(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="OUT")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
    )
    _add_daily_data(db_session, asset_id=asset.id)
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    assert result.status == RESULT_STATUS_COMPLETE
    assert result.items == ()


def test_future_buy_is_excluded(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="FBU")
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
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("20.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.quantity == Decimal("5.00000000")
    assert item.total_cost_basis == Decimal("50.0000000000000000")
    assert item.native_market_value == Decimal("100.0000000000000000")
    assert item.native_unrealized_pl == Decimal("50.0000000000000000")


def test_future_sell_is_excluded_from_historical_as_of_result(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="FSE")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        transaction_date=date(2026, 8, 27),
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.quantity == Decimal("10.00000000")
    assert item.total_cost_basis == Decimal("200.0000000000000000")
    assert item.native_unrealized_pl == Decimal("50.0000000000000000")


def test_latest_price_on_or_before_as_of_date_is_used(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="LPO")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 22),
        price=Decimal("21.00000000"),
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 24),
        price=Decimal("23.00000000"),
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 27),
        price=Decimal("99.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.price == Decimal("23.00000000")
    assert item.price_date == date(2026, 8, 24)
    assert item.native_unrealized_pl == Decimal("30.0000000000000000")


def test_yat_nav_selection_is_preserved(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="YAT", fund_kind="YAT")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.price == Decimal("25.00000000")
    assert item.price_kind == "NAV"
    assert item.price_source == "TEFAS"


def test_byf_uses_exchange_bulletin_price(db_session: Session) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="BYF", fund_kind="BYF")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=Decimal("30.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.price == Decimal("30.00000000")
    assert item.price_kind == "EXCHANGE_MARKET"
    assert item.native_market_value == Decimal("300.0000000000000000")
    assert item.native_unrealized_pl == Decimal("100.0000000000000000")


def test_byf_missing_exchange_bulletin_price_does_not_fall_back_to_nav(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="BNF", fund_kind="BYF")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=None,
    )
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert result.status == RESULT_STATUS_INCOMPLETE
    assert item.status == ITEM_STATUS_UNAVAILABLE
    assert item.unavailable_reason == REASON_PRICE_UNAVAILABLE
    assert item.price is None
    assert item.native_market_value is None
    assert item.native_unrealized_pl is None


def test_missing_price_returns_price_unavailable_with_cost_basis_inputs(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="NPR")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert result.status == RESULT_STATUS_INCOMPLETE
    assert item.status == ITEM_STATUS_UNAVAILABLE
    assert item.unavailable_reason == REASON_PRICE_UNAVAILABLE
    assert item.total_cost_basis == Decimal("200.0000000000000000")
    assert item.average_cost_per_unit == Decimal("20.00000000")
    assert item.price is None


def test_missing_asset_currency_returns_asset_currency_unavailable(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="NCY", currency=None)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert result.status == RESULT_STATUS_INCOMPLETE
    assert item.status == ITEM_STATUS_UNAVAILABLE
    assert item.unavailable_reason == REASON_ASSET_CURRENCY_UNAVAILABLE
    assert item.price == Decimal("25.00000000")
    assert item.price_kind == "NAV"
    assert item.total_cost_basis is None
    assert item.average_cost_per_unit is None
    assert item.native_market_value is None
    assert item.native_unrealized_pl is None


def test_blank_asset_currency_returns_asset_currency_unavailable(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="BCY", currency="   ")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert item.status == ITEM_STATUS_UNAVAILABLE
    assert item.unavailable_reason == REASON_ASSET_CURRENCY_UNAVAILABLE
    assert item.asset_currency == "   "
    assert item.price == Decimal("25.00000000")


def test_manual_non_tefas_asset_returns_unsupported_asset_with_cost_basis(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(
        db_session,
        asset_code="MAN",
        asset_type="STOCK",
        fund_kind=None,
        currency="USD",
        data_source="MANUAL",
    )
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert result.status == RESULT_STATUS_INCOMPLETE
    assert item.status == ITEM_STATUS_UNAVAILABLE
    assert item.unavailable_reason == REASON_UNSUPPORTED_ASSET
    assert item.total_cost_basis == Decimal("200.0000000000000000")
    assert item.price is None


def test_usd_asset_in_try_portfolio_without_fx_still_calculates_native_pl(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="unrealized-usd-owner@example.com",
        username="unrealized-usd-owner",
    )
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    asset = _create_asset(db_session, asset_code="USD", currency="USD")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("25.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert result.status == RESULT_STATUS_COMPLETE
    assert item.asset_currency == "USD"
    assert item.native_market_value == Decimal("250.0000000000000000")
    assert item.native_unrealized_pl == Decimal("50.0000000000000000")


def test_mixed_complete_and_unavailable_assets_make_result_incomplete(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    complete_asset = _create_asset(db_session, asset_code="CMP")
    unavailable_asset = _create_asset(db_session, asset_code="UNV")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=complete_asset.id)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=unavailable_asset.id)
    _add_daily_data(db_session, asset_id=complete_asset.id, price=Decimal("25.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    complete_item, unavailable_item = result.items
    assert result.status == RESULT_STATUS_INCOMPLETE
    assert complete_item.status == ITEM_STATUS_COMPLETE
    assert complete_item.native_unrealized_pl == Decimal("50.0000000000000000")
    assert unavailable_item.status == ITEM_STATUS_UNAVAILABLE
    assert unavailable_item.unavailable_reason == REASON_PRICE_UNAVAILABLE


def test_decimal_precision_preserved_without_float_round_or_quantize(
    db_session: Session,
) -> None:
    user, portfolio = _owned_portfolio(db_session)
    asset = _create_asset(db_session, asset_code="DEC")
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
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_unrealized_pl(
        portfolio_id=portfolio.id,
        current_user=user,
        as_of_date=AS_OF_DATE,
    )

    item = _only_item(result)
    assert isinstance(item.native_market_value, Decimal)
    assert isinstance(item.native_unrealized_pl, Decimal)
    assert item.total_cost_basis == Decimal("5.0000000000000000")
    assert item.average_cost_per_unit == Decimal("1.666666666666666666666666667")
    assert item.native_market_value == Decimal("6.0000000000000000")
    assert item.native_unrealized_pl == Decimal("1.0000000000000000")


def _cost_basis_item(
    *,
    asset_id: int,
    quantity: Decimal = Decimal("10.00000000"),
    status: str = ITEM_STATUS_COMPLETE,
    unavailable_reason: str | None = None,
) -> CostBasisItem:
    return CostBasisItem(
        asset_id=asset_id,
        asset_code="FAK",
        asset_name="Fake Asset",
        asset_currency="TRY",
        status=status,
        unavailable_reason=unavailable_reason,
        quantity=quantity,
        total_cost_basis=Decimal("200.0000000000000000"),
        average_cost_per_unit=Decimal("20.00000000"),
    )


def _fake_asset(*, asset_id: int = 1) -> Asset:
    return Asset(
        id=asset_id,
        asset_code="FAK",
        asset_name="Fake Asset",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        is_active=True,
    )


class _FakeCostBasisService:
    def __init__(self, result: CostBasisResult) -> None:
        self.result = result

    def get_cost_basis(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        as_of_date: date,
    ) -> CostBasisResult:
        return self.result


class _FakeTransactionRepository:
    def __init__(self, holdings: list[tuple[Asset, Decimal]]) -> None:
        self.holdings = holdings

    def list_holdings_by_portfolio_on_or_before(
        self,
        *,
        portfolio_id: int,
        transaction_date: date,
    ) -> list[tuple[Asset, Decimal]]:
        return self.holdings


class _FakePriceService:
    def get_price(self, *, asset: Asset, valuation_date: date):
        raise AssertionError("Price service should not be needed for invariant failure")


def _fake_user() -> User:
    return User(
        id=1,
        email="fake@example.com",
        username="fake",
        hashed_password="hashed-password",
        preferred_currency="TRY",
        is_active=True,
    )


def test_cost_basis_holding_asset_set_mismatch_raises_value_error() -> None:
    asset = _fake_asset(asset_id=1)
    result = CostBasisResult(
        portfolio_id=10,
        as_of_date=AS_OF_DATE,
        status=RESULT_STATUS_COMPLETE,
        items=(_cost_basis_item(asset_id=2),),
    )
    service = UnrealizedPlService(
        cost_basis_service=_FakeCostBasisService(result),
        transaction_repository=_FakeTransactionRepository(
            [(asset, Decimal("10.00000000"))],
        ),
        tefas_valuation_price_service=_FakePriceService(),
    )

    with pytest.raises(ValueError, match="asset set"):
        service.get_unrealized_pl(
            portfolio_id=10,
            current_user=_fake_user(),
            as_of_date=AS_OF_DATE,
        )


def test_duplicate_cost_basis_asset_id_raises_value_error() -> None:
    asset = _fake_asset(asset_id=1)
    result = CostBasisResult(
        portfolio_id=10,
        as_of_date=AS_OF_DATE,
        status=RESULT_STATUS_COMPLETE,
        items=(
            _cost_basis_item(asset_id=1),
            replace(
                _cost_basis_item(asset_id=1),
                asset_code="DUP",
                asset_name="Duplicate Cost Basis Item",
            ),
        ),
    )
    service = UnrealizedPlService(
        cost_basis_service=_FakeCostBasisService(result),
        transaction_repository=_FakeTransactionRepository(
            [(asset, Decimal("10.00000000"))],
        ),
        tefas_valuation_price_service=_FakePriceService(),
    )

    with pytest.raises(ValueError, match="Duplicate Cost Basis asset IDs"):
        service.get_unrealized_pl(
            portfolio_id=10,
            current_user=_fake_user(),
            as_of_date=AS_OF_DATE,
        )

def test_cost_basis_holding_quantity_mismatch_raises_value_error() -> None:
    asset = _fake_asset(asset_id=1)
    result = CostBasisResult(
        portfolio_id=10,
        as_of_date=AS_OF_DATE,
        status=RESULT_STATUS_COMPLETE,
        items=(_cost_basis_item(asset_id=1, quantity=Decimal("9.00000000")),),
    )
    service = UnrealizedPlService(
        cost_basis_service=_FakeCostBasisService(result),
        transaction_repository=_FakeTransactionRepository(
            [(asset, Decimal("10.00000000"))],
        ),
        tefas_valuation_price_service=_FakePriceService(),
    )

    with pytest.raises(ValueError, match="quantity"):
        service.get_unrealized_pl(
            portfolio_id=10,
            current_user=_fake_user(),
            as_of_date=AS_OF_DATE,
        )


def test_cost_basis_result_portfolio_id_mismatch_raises_value_error() -> None:
    asset = _fake_asset(asset_id=1)
    result = CostBasisResult(
        portfolio_id=11,
        as_of_date=AS_OF_DATE,
        status=RESULT_STATUS_COMPLETE,
        items=(_cost_basis_item(asset_id=1),),
    )
    service = UnrealizedPlService(
        cost_basis_service=_FakeCostBasisService(result),
        transaction_repository=_FakeTransactionRepository(
            [(asset, Decimal("10.00000000"))],
        ),
        tefas_valuation_price_service=_FakePriceService(),
    )

    with pytest.raises(ValueError, match="portfolio"):
        service.get_unrealized_pl(
            portfolio_id=10,
            current_user=_fake_user(),
            as_of_date=AS_OF_DATE,
        )

def test_cost_basis_result_date_mismatch_raises_value_error() -> None:
    asset = _fake_asset(asset_id=1)
    result = CostBasisResult(
        portfolio_id=10,
        as_of_date=date(2026, 8, 24),
        status=RESULT_STATUS_COMPLETE,
        items=(_cost_basis_item(asset_id=1),),
    )
    service = UnrealizedPlService(
        cost_basis_service=_FakeCostBasisService(result),
        transaction_repository=_FakeTransactionRepository(
            [(asset, Decimal("10.00000000"))],
        ),
        tefas_valuation_price_service=_FakePriceService(),
    )

    with pytest.raises(ValueError, match="date"):
        service.get_unrealized_pl(
            portfolio_id=10,
            current_user=_fake_user(),
            as_of_date=AS_OF_DATE,
        )


def test_cost_basis_item_unexpected_status_raises_value_error() -> None:
    asset = _fake_asset(asset_id=1)
    result = CostBasisResult(
        portfolio_id=10,
        as_of_date=AS_OF_DATE,
        status=RESULT_STATUS_COMPLETE,
        items=(_cost_basis_item(asset_id=1, status="STALE"),),
    )
    service = UnrealizedPlService(
        cost_basis_service=_FakeCostBasisService(result),
        transaction_repository=_FakeTransactionRepository(
            [(asset, Decimal("10.00000000"))],
        ),
        tefas_valuation_price_service=_FakePriceService(),
    )

    with pytest.raises(ValueError, match="Unexpected Cost Basis item status"):
        service.get_unrealized_pl(
            portfolio_id=10,
            current_user=_fake_user(),
            as_of_date=AS_OF_DATE,
        )

def test_unavailable_cost_basis_without_reason_raises_value_error() -> None:
    asset = _fake_asset(asset_id=1)
    result = CostBasisResult(
        portfolio_id=10,
        as_of_date=AS_OF_DATE,
        status=RESULT_STATUS_INCOMPLETE,
        items=(
            replace(
                _cost_basis_item(
                    asset_id=1,
                    status=ITEM_STATUS_UNAVAILABLE,
                    unavailable_reason="ASSET_CURRENCY_UNAVAILABLE",
                ),
                unavailable_reason=None,
                total_cost_basis=None,
                average_cost_per_unit=None,
            ),
        ),
    )
    service = UnrealizedPlService(
        cost_basis_service=_FakeCostBasisService(result),
        transaction_repository=_FakeTransactionRepository(
            [(asset, Decimal("10.00000000"))],
        ),
        tefas_valuation_price_service=_FakePriceService(),
    )

    with pytest.raises(ValueError, match="missing a reason"):
        service.get_unrealized_pl(
            portfolio_id=10,
            current_user=_fake_user(),
            as_of_date=AS_OF_DATE,
        )