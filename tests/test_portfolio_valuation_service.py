from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.exchange_rate import ExchangeRate
from src.model.portfolio import Portfolio
from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.exchange_rate_repository import ExchangeRateRepository
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.fx_conversion_service import FxConversionService
from src.services.portfolio_cash_replay_service import PortfolioCashReplayService
from src.services.portfolio_valuation_service import PortfolioValuationService
from src.services.tefas_valuation_price_service import TefasValuationPriceService


VALUATION_DATE = date(2026, 8, 26)
TRANSACTION_DATE = date(2026, 8, 20)


def _create_user(
    db_session: Session,
    *,
    email: str = "valuation-user@example.com",
    username: str = "valuation-user",
) -> User:
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
    name: str = "Valuation Portfolio",
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
    asset_code: str = "AAL",
    asset_name: str | None = None,
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name or f"{asset_code} Example Fund",
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
    unit_price: Decimal = Decimal("1.00000000"),
    transaction_currency: str | None = "TRY",
    transaction_date: date = TRANSACTION_DATE,
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


def _add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date = VALUATION_DATE,
    price: Decimal = Decimal("12.34567890"),
    exchange_bulletin_price: Decimal | None = None,
) -> TefasFundDailyData:
    daily_data = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=Decimal("1000.0000"),
        investor_count=100,
        portfolio_size=Decimal("12345.6700"),
        exchange_bulletin_price=exchange_bulletin_price,
    )
    db_session.add(daily_data)
    db_session.flush()
    return daily_data


def _add_exchange_rate(
    db_session: Session,
    *,
    base_currency: str = "USD",
    quote_currency: str = "TRY",
    rate_date: date = date(2026, 8, 25),
    forex_buying: Decimal = Decimal("40.00000000"),
    forex_selling: Decimal = Decimal("42.00000000"),
    source: str = "TCMB",
) -> ExchangeRate:
    exchange_rate = ExchangeRate(
        base_currency=base_currency,
        quote_currency=quote_currency,
        rate_date=rate_date,
        forex_buying=forex_buying,
        forex_selling=forex_selling,
        source=source,
    )
    db_session.add(exchange_rate)
    db_session.flush()
    return exchange_rate


def _add_cash_flow(
    db_session: Session,
    *,
    portfolio_id: int,
    flow_type: str = "DEPOSIT",
    amount: Decimal = Decimal("100.00000000"),
    currency: str = "TRY",
    flow_date: date = TRANSACTION_DATE,
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


def _create_service(db_session: Session) -> PortfolioValuationService:
    portfolio_repository = PortfolioRepository(db_session)
    transaction_repository = TransactionRepository(db_session)
    cash_flow_repository = PortfolioCashFlowRepository(db_session)
    return PortfolioValuationService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
        tefas_valuation_price_service=TefasValuationPriceService(
            TefasFundDailyDataRepository(db_session),
        ),
        fx_conversion_service=FxConversionService(
            ExchangeRateRepository(db_session),
        ),
        portfolio_cash_replay_service=PortfolioCashReplayService(
            portfolio_repository=portfolio_repository,
            cash_flow_repository=cash_flow_repository,
            transaction_repository=transaction_repository,
        ),
    )


def _portfolio_with_single_holding(
    db_session: Session,
    *,
    base_currency: str = "TRY",
    asset_code: str = "AAL",
    fund_kind: str | None = "YAT",
    asset_currency: str | None = "TRY",
    asset_type: str = "FUND",
    data_source: str = "TEFAS",
    quantity: Decimal = Decimal("10.00000000"),
) -> tuple[User, Portfolio, Asset]:
    user = _create_user(db_session)
    portfolio = _create_portfolio(
        db_session,
        user_id=user.id,
        base_currency=base_currency,
    )
    asset = _create_asset(
        db_session,
        asset_code=asset_code,
        asset_type=asset_type,
        fund_kind=fund_kind,
        currency=asset_currency,
        data_source=data_source,
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=quantity,
    )
    return user, portfolio, asset


def test_portfolio_ownership_failure_returns_404(db_session: Session) -> None:
    owner = _create_user(db_session, email="owner@example.com", username="owner")
    other_user = _create_user(db_session, email="other@example.com", username="other")
    portfolio = _create_portfolio(db_session, user_id=owner.id)
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_valuation(
            portfolio_id=portfolio.id,
            current_user=other_user,
            valuation_date=VALUATION_DATE,
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."


def test_empty_portfolio_returns_complete_zero_value(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.portfolio_id == portfolio.id
    assert result.base_currency == "TRY"
    assert result.valuation_date == VALUATION_DATE
    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.items == ()


def test_single_try_holding_in_try_portfolio_is_complete(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(db_session)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("3.25000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("32.5000000000000000")
    item = result.items[0]
    assert item.asset_id == asset.id
    assert item.asset_code == "AAL"
    assert item.asset_name == "AAL Example Fund"
    assert item.quantity == Decimal("10.00000000")
    assert item.asset_currency == "TRY"
    assert item.status == "COMPLETE"
    assert item.unavailable_reason is None
    assert item.price == Decimal("3.25000000")
    assert item.price_date == VALUATION_DATE
    assert item.price_kind == "NAV"
    assert item.price_source == "TEFAS"
    assert item.fx_rate == Decimal("1")
    assert item.fx_rate_date is None
    assert item.fx_rate_kind == "IDENTITY"
    assert item.fx_source == "IDENTITY"
    assert item.native_market_value == Decimal("32.5000000000000000")
    assert item.market_value == Decimal("32.5000000000000000")


def test_quantity_times_nav_price_calculation(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        quantity=Decimal("7.50000000"),
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.20000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].native_market_value == Decimal("16.5000000000000000")
    assert result.items[0].market_value == Decimal("16.5000000000000000")
    assert result.total_market_value == Decimal("16.5000000000000000")


def test_yat_valuation_uses_nav_through_real_selector(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        fund_kind="YAT",
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("12.00000000"),
        exchange_bulletin_price=Decimal("99.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].price == Decimal("12.00000000")
    assert result.items[0].price_kind == "NAV"


def test_byf_valuation_uses_exchange_bulletin_through_real_selector(
    db_session: Session,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        fund_kind="BYF",
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=Decimal("11.25000000"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].price == Decimal("11.25000000")
    assert result.items[0].price_kind == "EXCHANGE_MARKET"
    assert result.items[0].market_value == Decimal("112.5000000000000000")


def test_byf_missing_bulletin_price_is_price_unavailable_and_incomplete(
    db_session: Session,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        fund_kind="BYF",
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        price=Decimal("99.00000000"),
        exchange_bulletin_price=None,
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert result.items[0].status == "UNAVAILABLE"
    assert result.items[0].unavailable_reason == "PRICE_UNAVAILABLE"
    assert result.items[0].price is None
    assert result.items[0].market_value is None


def test_latest_price_on_or_before_valuation_date_is_used(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(db_session)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 20),
        price=Decimal("9.00000000"),
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 25),
        price=Decimal("10.00000000"),
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 27),
        price=Decimal("100.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].price == Decimal("10.00000000")
    assert result.items[0].price_date == date(2026, 8, 25)


def test_same_currency_identity_fx_works(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        base_currency="USD",
        asset_currency="USD",
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("4.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].fx_rate == Decimal("1")
    assert result.items[0].fx_rate_kind == "IDENTITY"
    assert result.total_market_value == Decimal("40.0000000000000000")


def test_usd_asset_to_try_portfolio_conversion(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        asset_currency="USD",
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        forex_buying=Decimal("40.00000000"),
        forex_selling=Decimal("42.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].native_market_value == Decimal("20.0000000000000000")
    assert result.items[0].fx_rate == Decimal("41.00000000")
    assert result.items[0].fx_rate_date == date(2026, 8, 25)
    assert result.items[0].fx_rate_kind == "TCMB_MIDPOINT"
    assert result.items[0].fx_source == "TCMB"
    assert result.items[0].market_value == Decimal("820.000000000000000000000000")
    assert result.total_market_value == Decimal("820.000000000000000000000000")


def test_try_asset_to_usd_portfolio_inverse_conversion(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        base_currency="USD",
        asset_currency="TRY",
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("20.00000000"))
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        forex_buying=Decimal("39.00000000"),
        forex_selling=Decimal("41.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].native_market_value == Decimal("200.0000000000000000")
    assert result.items[0].fx_rate == Decimal("1") / Decimal("40.00000000")
    assert result.items[0].market_value == Decimal("200.0000000000000000") / Decimal("40.00000000")


def test_usd_asset_to_eur_portfolio_cross_conversion(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        base_currency="EUR",
        asset_currency="USD",
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        forex_buying=Decimal("40.00000000"),
        forex_selling=Decimal("42.00000000"),
    )
    _add_exchange_rate(
        db_session,
        base_currency="EUR",
        forex_buying=Decimal("50.00000000"),
        forex_selling=Decimal("52.00000000"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.items[0].fx_rate == Decimal("41.00000000") / Decimal("51.00000000")
    assert result.items[0].market_value == Decimal("20.0000000000000000") * (
        Decimal("41.00000000") / Decimal("51.00000000")
    )
    assert result.items[0].fx_rate_date == date(2026, 8, 25)


def test_multiple_complete_holdings_produce_exact_decimal_total(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    first_asset = _create_asset(db_session, asset_code="AAL")
    second_asset = _create_asset(db_session, asset_code="BBL")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=first_asset.id,
        quantity=Decimal("1.10000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=second_asset.id,
        quantity=Decimal("2.20000000"),
    )
    _add_daily_data(
        db_session,
        asset_id=first_asset.id,
        price=Decimal("3.30000000"),
    )
    _add_daily_data(
        db_session,
        asset_id=second_asset.id,
        price=Decimal("4.40000000"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    expected_first = Decimal("1.10000000") * Decimal("3.30000000")
    expected_second = Decimal("2.20000000") * Decimal("4.40000000")
    assert result.status == "COMPLETE"
    assert result.items[0].market_value == expected_first
    assert result.items[1].market_value == expected_second
    assert result.total_market_value == expected_first + expected_second


@pytest.mark.parametrize("asset_currency", [None, "", "   "])
def test_missing_asset_currency_is_unavailable_after_price_selection(
    db_session: Session,
    asset_currency: str | None,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        asset_currency=asset_currency,
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("5.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    item = result.items[0]
    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert item.status == "UNAVAILABLE"
    assert item.unavailable_reason == "ASSET_CURRENCY_UNAVAILABLE"
    assert item.price == Decimal("5.00000000")
    assert item.price_date == VALUATION_DATE
    assert item.price_kind == "NAV"
    assert item.price_source == "TEFAS"
    assert item.fx_rate is None
    assert item.native_market_value is None
    assert item.market_value is None


def test_missing_price_is_price_unavailable(db_session: Session) -> None:
    user, portfolio, _asset = _portfolio_with_single_holding(db_session)
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    item = result.items[0]
    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert item.status == "UNAVAILABLE"
    assert item.unavailable_reason == "PRICE_UNAVAILABLE"
    assert item.price is None
    assert item.native_market_value is None
    assert item.market_value is None


def test_missing_fx_is_fx_unavailable(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        base_currency="TRY",
        asset_currency="USD",
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    item = result.items[0]
    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert item.status == "UNAVAILABLE"
    assert item.unavailable_reason == "FX_UNAVAILABLE"
    assert item.price == Decimal("2.00000000")
    assert item.native_market_value == Decimal("20.0000000000000000")
    assert item.fx_rate is None
    assert item.market_value is None


def test_mismatched_foreign_cross_rate_dates_are_fx_unavailable(
    db_session: Session,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        base_currency="EUR",
        asset_currency="USD",
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    _add_exchange_rate(db_session, base_currency="USD", rate_date=date(2026, 8, 25))
    _add_exchange_rate(db_session, base_currency="EUR", rate_date=date(2026, 8, 24))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    item = result.items[0]
    assert result.status == "INCOMPLETE"
    assert item.unavailable_reason == "FX_UNAVAILABLE"
    assert item.native_market_value == Decimal("20.0000000000000000")
    assert item.fx_rate is None


def test_unsupported_non_tefas_asset_is_unavailable(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        asset_type="STOCK",
        fund_kind=None,
        data_source="MANUAL",
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    item = result.items[0]
    assert item.asset_id == asset.id
    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert item.status == "UNAVAILABLE"
    assert item.unavailable_reason == "UNSUPPORTED_ASSET"
    assert item.price is None
    assert item.fx_rate is None
    assert item.native_market_value is None
    assert item.market_value is None


def test_one_unavailable_holding_makes_portfolio_incomplete_without_total(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    complete_asset = _create_asset(db_session, asset_code="AAL")
    unavailable_asset = _create_asset(db_session, asset_code="MNL", data_source="MANUAL")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=complete_asset.id,
        quantity=Decimal("3.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=unavailable_asset.id,
        quantity=Decimal("4.00000000"),
    )
    _add_daily_data(db_session, asset_id=complete_asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    complete_item = result.items[0]
    unavailable_item = result.items[1]
    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert complete_item.status == "COMPLETE"
    assert complete_item.market_value == Decimal("6.0000000000000000")
    assert unavailable_item.status == "UNAVAILABLE"
    assert unavailable_item.unavailable_reason == "UNSUPPORTED_ASSET"


def test_complete_items_keep_market_value_inside_incomplete_portfolio(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    complete_asset = _create_asset(db_session, asset_code="AAL")
    missing_price_asset = _create_asset(db_session, asset_code="BBL")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=complete_asset.id,
        quantity=Decimal("2.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=missing_price_asset.id,
        quantity=Decimal("3.00000000"),
    )
    _add_daily_data(db_session, asset_id=complete_asset.id, price=Decimal("7.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert result.items[0].status == "COMPLETE"
    assert result.items[0].market_value == Decimal("14.0000000000000000")
    assert result.items[1].status == "UNAVAILABLE"


def test_decimal_arithmetic_is_preserved_with_no_float_or_rounding(
    db_session: Session,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        asset_currency="USD",
        quantity=Decimal("1.23456789"),
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("9.87654321"))
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        forex_buying=Decimal("40.12345678"),
        forex_selling=Decimal("40.87654321"),
    )
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    expected_native = Decimal("1.23456789") * Decimal("9.87654321")
    expected_fx = (Decimal("40.12345678") + Decimal("40.87654321")) / Decimal("2")
    expected_market_value = expected_native * expected_fx
    item = result.items[0]
    assert item.native_market_value == expected_native
    assert item.fx_rate == expected_fx
    assert item.market_value == expected_market_value
    assert result.total_market_value == expected_market_value
    assert isinstance(item.market_value, Decimal)


def test_fully_sold_assets_remain_absent_from_valuation(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        quantity=Decimal("10.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("10.00000000"),
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("3.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.items == ()


def test_buy_after_valuation_date_does_not_appear_in_valuation(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    asset = _create_asset(db_session)
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        transaction_date=date(2026, 8, 27),
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.items == ()


def test_sell_after_valuation_date_does_not_reduce_historical_holding(
    db_session: Session,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        quantity=Decimal("10.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        transaction_date=date(2026, 8, 27),
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert len(result.items) == 1
    assert result.items[0].quantity == Decimal("10.00000000")
    assert result.items[0].market_value == Decimal("20.0000000000000000")
    assert result.total_market_value == Decimal("20.0000000000000000")


def test_sell_on_valuation_date_affects_that_dates_valuation(
    db_session: Session,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        quantity=Decimal("10.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_type="SELL",
        quantity=Decimal("4.00000000"),
        transaction_date=VALUATION_DATE,
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert len(result.items) == 1
    assert result.items[0].quantity == Decimal("6.00000000")
    assert result.items[0].market_value == Decimal("12.0000000000000000")
    assert result.total_market_value == Decimal("12.0000000000000000")

def test_single_complete_holding_has_full_weight(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(db_session)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("3.25000000"))
    service = _create_service(db_session)

    result = service.get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.items[0].weight == Decimal("1")


def test_multiple_complete_holdings_have_exact_25_75_weights(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    first_asset = _create_asset(db_session, asset_code="WAA")
    second_asset = _create_asset(db_session, asset_code="WAB")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=first_asset.id, quantity=Decimal("5.00000000"))
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=second_asset.id, quantity=Decimal("15.00000000"))
    _add_daily_data(db_session, asset_id=first_asset.id, price=Decimal("5.00000000"))
    _add_daily_data(db_session, asset_id=second_asset.id, price=Decimal("5.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=VALUATION_DATE)

    assert result.total_market_value == Decimal("100.0000000000000000")
    assert result.items[0].market_value == Decimal("25.0000000000000000")
    assert result.items[1].market_value == Decimal("75.0000000000000000")
    assert result.items[0].weight == Decimal("0.25")
    assert result.items[1].weight == Decimal("0.75")


def test_weight_uses_portfolio_currency_market_value_after_fx_conversion(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    try_asset = _create_asset(db_session, asset_code="WAC", currency="TRY")
    usd_asset = _create_asset(db_session, asset_code="WAD", currency="USD")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=try_asset.id, quantity=Decimal("50.00000000"))
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=usd_asset.id, quantity=Decimal("1.00000000"))
    _add_daily_data(db_session, asset_id=try_asset.id, price=Decimal("1.00000000"))
    _add_daily_data(db_session, asset_id=usd_asset.id, price=Decimal("5.00000000"))
    _add_exchange_rate(db_session, base_currency="USD", forex_buying=Decimal("9.00000000"), forex_selling=Decimal("11.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=VALUATION_DATE)

    assert result.items[0].native_market_value == Decimal("50.0000000000000000")
    assert result.items[1].native_market_value == Decimal("5.0000000000000000")
    assert result.items[1].market_value == Decimal("50.000000000000000000000000")
    assert result.total_market_value == Decimal("100.000000000000000000000000")
    assert result.items[0].weight == result.items[0].market_value / result.total_market_value
    assert result.items[1].weight == result.items[1].market_value / result.total_market_value
    assert result.items[1].weight == Decimal("0.5")


def test_weight_decimal_arithmetic_is_preserved_without_rounding(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    first_asset = _create_asset(db_session, asset_code="WAE")
    second_asset = _create_asset(db_session, asset_code="WAF")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=first_asset.id, quantity=Decimal("1.00000000"))
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=second_asset.id, quantity=Decimal("2.00000000"))
    _add_daily_data(db_session, asset_id=first_asset.id, price=Decimal("1.00000000"))
    _add_daily_data(db_session, asset_id=second_asset.id, price=Decimal("1.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=VALUATION_DATE)

    expected_weight = result.items[0].market_value / result.total_market_value
    assert expected_weight == Decimal("1.0000000000000000") / Decimal("3.0000000000000000")
    assert result.items[0].weight == expected_weight
    assert isinstance(result.items[0].weight, Decimal)


def test_incomplete_portfolio_has_no_item_weights(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    complete_asset = _create_asset(db_session, asset_code="WAG")
    unavailable_asset = _create_asset(db_session, asset_code="WAH")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=complete_asset.id)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=unavailable_asset.id)
    _add_daily_data(db_session, asset_id=complete_asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=VALUATION_DATE)

    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert all(item.weight is None for item in result.items)


def test_complete_item_inside_incomplete_portfolio_has_no_weight(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    complete_asset = _create_asset(db_session, asset_code="WAI")
    missing_price_asset = _create_asset(db_session, asset_code="WAJ")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=complete_asset.id)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=missing_price_asset.id)
    _add_daily_data(db_session, asset_id=complete_asset.id, price=Decimal("2.00000000"))
    service = _create_service(db_session)

    result = service.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=VALUATION_DATE)

    assert result.items[0].status == "COMPLETE"
    assert result.items[0].market_value == Decimal("20.0000000000000000")
    assert result.items[0].weight is None
    assert result.items[1].status == "UNAVAILABLE"
    assert result.items[1].weight is None


def test_unavailable_item_weight_is_none(db_session: Session) -> None:
    user, portfolio, _asset = _portfolio_with_single_holding(db_session)
    service = _create_service(db_session)

    result = service.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=VALUATION_DATE)

    assert result.items[0].status == "UNAVAILABLE"
    assert result.items[0].weight is None


def test_empty_portfolio_has_no_weight_calculation(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service = _create_service(db_session)

    result = service.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=VALUATION_DATE)

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.items == ()

def test_same_currency_cash_is_added_to_total_portfolio_value(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(db_session)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("50.00000000"),
        currency="TRY",
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("20.0000000000000000")
    assert result.total_cash_value == Decimal("40.0000000000000000")
    assert result.total_portfolio_value == Decimal("60.0000000000000000")
    assert result.items[0].weight == Decimal("1")
    assert result.cash_items[0].currency == "TRY"
    assert result.cash_items[0].amount == Decimal("40.00000000")
    assert result.cash_items[0].market_value == Decimal("40.0000000000000000")
    assert result.cash_items[0].fx_source == "IDENTITY"


def test_foreign_cash_converts_with_latest_on_or_before_fx(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("3.00000000"),
        currency="USD",
    )
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 20),
        forex_buying=Decimal("30.00000000"),
        forex_selling=Decimal("32.00000000"),
    )
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 25),
        forex_buying=Decimal("40.00000000"),
        forex_selling=Decimal("42.00000000"),
    )
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 27),
        forex_buying=Decimal("50.00000000"),
        forex_selling=Decimal("52.00000000"),
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.total_cash_value == Decimal("123.0000000000000000")
    assert result.total_portfolio_value == Decimal("123.0000000000000000")
    assert result.cash_items[0].fx_rate == Decimal("41.00000000")
    assert result.cash_items[0].fx_rate_date == date(2026, 8, 25)
    assert result.cash_items[0].fx_freshness.status == "STALE"


def test_negative_cash_reduces_total_portfolio_value(db_session: Session) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(db_session)
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("5.00000000"))
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("15.00000000"),
        currency="TRY",
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.total_market_value == Decimal("50.0000000000000000")
    assert result.total_cash_value == Decimal("-25.0000000000000000")
    assert result.total_portfolio_value == Decimal("25.0000000000000000")
    assert result.cash_items[0].amount == Decimal("-25.00000000")


def test_future_cash_flow_is_excluded_from_historical_valuation(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("100.00000000"),
        flow_date=date(2026, 8, 27),
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_cash_value == Decimal("0")
    assert result.total_portfolio_value == Decimal("0")
    assert result.cash_items == ()


def test_future_transaction_is_excluded_from_cash_replay_in_valuation(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    asset = _create_asset(db_session, asset_code="FUT", currency="TRY")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("9.00000000"),
        transaction_currency="TRY",
        transaction_date=date(2026, 8, 27),
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.total_cash_value == Decimal("0")
    assert result.total_portfolio_value == Decimal("0")
    assert result.cash_items == ()


def test_legacy_null_transaction_currency_makes_valuation_incomplete_without_total(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    asset = _create_asset(db_session, asset_code="LEG", currency=None)
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
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_currency=None,
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.total_cash_value is None
    assert result.total_portfolio_value is None
    assert result.cash_items[0].currency == "TRY"
    assert result.cash_items[0].amount == Decimal("100.00000000")
    assert result.cash_items[0].market_value == Decimal("100.00000000")


def test_missing_cash_fx_makes_valuation_incomplete_without_total(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("5.00000000"),
        currency="USD",
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.total_cash_value is None
    assert result.total_portfolio_value is None
    assert result.cash_items[0].status == "UNAVAILABLE"
    assert result.cash_items[0].unavailable_reason == "FX_UNAVAILABLE"
    assert result.cash_items[0].market_value is None


def test_asset_currency_is_not_used_for_cash_currency(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    asset = _create_asset(db_session, asset_code="NOCASHFX", currency="TRY")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("2.00000000"),
        unit_price=Decimal("10.00000000"),
        transaction_currency="USD",
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.cash_items[0].currency == "USD"
    assert result.cash_items[0].amount == Decimal("-20.0000000000000000")
    assert result.cash_items[0].unavailable_reason == "FX_UNAVAILABLE"


def test_foreign_currency_negative_cash_converts_and_reduces_totals(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    asset = _create_asset(db_session, asset_code="NEGCASH", currency="TRY")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("1.00000000"),
        transaction_currency="USD",
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("5.00000000"))
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("3.00000000"),
        currency="USD",
    )
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 25),
        forex_buying=Decimal("40.00000000"),
        forex_selling=Decimal("42.00000000"),
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("50.0000000000000000")
    assert result.cash_items[0].currency == "USD"
    assert result.cash_items[0].amount == Decimal("-13.0000000000000000")
    assert result.cash_items[0].fx_rate == Decimal("41.00000000")
    assert result.cash_items[0].market_value == Decimal("-533.000000000000000000000000")
    assert result.total_cash_value == Decimal("-533.000000000000000000000000")
    assert result.total_portfolio_value == Decimal("-483.000000000000000000000000")


def test_multiple_foreign_cash_currencies_keep_available_item_when_one_fx_missing(
    db_session: Session,
) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id, base_currency="TRY")
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("3.00000000"),
        currency="USD",
    )
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("2.00000000"),
        currency="EUR",
    )
    _add_exchange_rate(
        db_session,
        base_currency="USD",
        quote_currency="TRY",
        rate_date=date(2026, 8, 25),
        forex_buying=Decimal("40.00000000"),
        forex_selling=Decimal("42.00000000"),
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.total_cash_value is None
    assert result.total_portfolio_value is None
    assert [item.currency for item in result.cash_items] == ["EUR", "USD"]

    eur_item = result.cash_items[0]
    assert eur_item.status == "UNAVAILABLE"
    assert eur_item.unavailable_reason == "FX_UNAVAILABLE"
    assert eur_item.amount == Decimal("2.00000000")
    assert eur_item.market_value is None

    usd_item = result.cash_items[1]
    assert usd_item.status == "COMPLETE"
    assert usd_item.unavailable_reason is None
    assert usd_item.amount == Decimal("3.00000000")
    assert usd_item.fx_rate == Decimal("41.00000000")
    assert usd_item.market_value == Decimal("123.0000000000000000")


def test_cash_only_portfolio_is_complete_when_cash_is_valued(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("70.00000000"),
        currency="TRY",
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.items == ()
    assert result.total_market_value == Decimal("0")
    assert result.total_cash_value == Decimal("70.00000000")
    assert result.total_portfolio_value == Decimal("70.00000000")


def test_empty_portfolio_includes_zero_cash_and_portfolio_totals(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "COMPLETE"
    assert result.total_market_value == Decimal("0")
    assert result.total_cash_value == Decimal("0")
    assert result.total_portfolio_value == Decimal("0")
    assert result.items == ()
    assert result.cash_items == ()


def test_asset_incomplete_cash_complete_has_no_total_portfolio_value(
    db_session: Session,
) -> None:
    user, portfolio, asset = _portfolio_with_single_holding(
        db_session,
        asset_currency=None,
    )
    _add_daily_data(db_session, asset_id=asset.id, price=Decimal("2.00000000"))
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("50.00000000"),
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.status == "INCOMPLETE"
    assert result.total_market_value is None
    assert result.total_cash_value == Decimal("40.0000000000000000")
    assert result.total_portfolio_value is None
    assert result.cash_items[0].status == "COMPLETE"
    assert all(item.weight is None for item in result.items)


def test_total_market_value_and_asset_weights_remain_asset_only(db_session: Session) -> None:
    user = _create_user(db_session)
    portfolio = _create_portfolio(db_session, user_id=user.id)
    first_asset = _create_asset(db_session, asset_code="WGT1", currency="TRY")
    second_asset = _create_asset(db_session, asset_code="WGT2", currency="TRY")
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=first_asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("1.00000000"),
    )
    _add_transaction(
        db_session,
        portfolio_id=portfolio.id,
        asset_id=second_asset.id,
        quantity=Decimal("10.00000000"),
        unit_price=Decimal("1.00000000"),
    )
    _add_daily_data(db_session, asset_id=first_asset.id, price=Decimal("2.50000000"))
    _add_daily_data(db_session, asset_id=second_asset.id, price=Decimal("7.50000000"))
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("100.00000000"),
        currency="TRY",
    )

    result = _create_service(db_session).get_valuation(
        portfolio_id=portfolio.id,
        current_user=user,
        valuation_date=VALUATION_DATE,
    )

    assert result.total_market_value == Decimal("100.0000000000000000")
    assert result.total_cash_value == Decimal("80.0000000000000000")
    assert result.total_portfolio_value == Decimal("180.0000000000000000")
    assert result.items[0].weight == Decimal("0.25")
    assert result.items[1].weight == Decimal("0.75")
