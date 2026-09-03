from __future__ import annotations

from datetime import date, timedelta
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
from src.services.fx_conversion_service import FxConversionRate, FxConversionService
from src.services.portfolio_cash_replay_service import PortfolioCashReplayService
from src.services.portfolio_performance_service import (
    PERFORMANCE_STATUS_COMPLETE,
    PERFORMANCE_STATUS_INCOMPLETE,
    PERFORMANCE_STATUS_NOT_APPLICABLE,
    REASON_EXTERNAL_FLOW_FX_UNAVAILABLE,
    REASON_NON_POSITIVE_CAPITAL_BASE,
    REASON_VALUATION_INCOMPLETE,
    REASON_ZERO_DENOMINATOR_WITH_VALUE,
    PortfolioPerformanceService,
)
from src.services.portfolio_valuation_service import PortfolioValuationResult, PortfolioValuationService
from src.services.tefas_valuation_price_service import TefasValuationPriceService


START_DATE = date(2026, 1, 2)
PREVIOUS_DATE = date(2026, 1, 1)


def _create_user(db_session: Session, *, email: str = "performance@example.com") -> User:
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


def _create_portfolio(db_session: Session, *, user_id: int, base_currency: str = "TRY") -> Portfolio:
    portfolio = Portfolio(user_id=user_id, name="Performance Portfolio", base_currency=base_currency)
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _create_asset(db_session: Session, *, asset_code: str = "TPF") -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_cash_flow(db_session: Session, *, portfolio_id: int, flow_type: str = "DEPOSIT", amount: Decimal = Decimal("100.00000000"), currency: str = "TRY", flow_date: date = START_DATE) -> PortfolioCashFlow:
    cash_flow = PortfolioCashFlow(portfolio_id=portfolio_id, flow_type=flow_type, amount=amount, currency=currency, flow_date=flow_date)
    db_session.add(cash_flow)
    db_session.flush()
    return cash_flow


def _add_transaction(db_session: Session, *, portfolio_id: int, asset_id: int, transaction_type: str = "BUY", quantity: Decimal = Decimal("10.00000000"), unit_price: Decimal = Decimal("10.00000000"), transaction_currency: str | None = "TRY", transaction_date: date = START_DATE) -> Transaction:
    transaction = Transaction(portfolio_id=portfolio_id, asset_id=asset_id, transaction_type=transaction_type, quantity=quantity, unit_price=unit_price, transaction_currency=transaction_currency, transaction_date=transaction_date)
    db_session.add(transaction)
    db_session.flush()
    return transaction


def _add_daily_data(db_session: Session, *, asset_id: int, data_date: date, price: Decimal = Decimal("10.00000000")) -> TefasFundDailyData:
    daily_data = TefasFundDailyData(asset_id=asset_id, data_date=data_date, price=price, shares_outstanding=Decimal("1000.0000"), investor_count=100, portfolio_size=Decimal("10000.0000"))
    db_session.add(daily_data)
    db_session.flush()
    return daily_data


def _create_real_service(db_session: Session) -> PortfolioPerformanceService:
    portfolio_repository = PortfolioRepository(db_session)
    transaction_repository = TransactionRepository(db_session)
    cash_flow_repository = PortfolioCashFlowRepository(db_session)
    fx_conversion_service = FxConversionService(ExchangeRateRepository(db_session))
    valuation_service = PortfolioValuationService(
        portfolio_repository=portfolio_repository,
        transaction_repository=transaction_repository,
        tefas_valuation_price_service=TefasValuationPriceService(TefasFundDailyDataRepository(db_session)),
        fx_conversion_service=fx_conversion_service,
        portfolio_cash_replay_service=PortfolioCashReplayService(
            portfolio_repository=portfolio_repository,
            cash_flow_repository=cash_flow_repository,
            transaction_repository=transaction_repository,
        ),
    )
    return PortfolioPerformanceService(
        portfolio_repository=portfolio_repository,
        cash_flow_repository=cash_flow_repository,
        fx_conversion_service=fx_conversion_service,
        portfolio_valuation_service=valuation_service,
    )


def _valuation(portfolio_id: int, valuation_date: date, value: Decimal | None, status: str = "COMPLETE") -> PortfolioValuationResult:
    return PortfolioValuationResult(
        portfolio_id=portfolio_id,
        base_currency="TRY",
        valuation_date=valuation_date,
        status=status,
        total_market_value=value,
        total_cash_value=Decimal("0") if value is not None else None,
        total_portfolio_value=value,
        items=(),
        cash_items=(),
    )


class FakeValuationService:
    def __init__(self, values: dict[date, Decimal | None], incomplete_dates: set[date] | None = None) -> None:
        self.values = values
        self.incomplete_dates = incomplete_dates or set()
        self.calls: list[date] = []

    def get_valuation(self, *, portfolio_id: int, current_user: User, valuation_date: date) -> PortfolioValuationResult:
        self.calls.append(valuation_date)
        status = "INCOMPLETE" if valuation_date in self.incomplete_dates else "COMPLETE"
        return _valuation(portfolio_id, valuation_date, self.values.get(valuation_date), status=status)


class FakeCashFlowRepository:
    def __init__(self, cash_flows: list[PortfolioCashFlow]) -> None:
        self.cash_flows = cash_flows
        self.calls: list[tuple[date, date]] = []

    def list_by_portfolio_between(self, *, portfolio_id: int, start_date: date, end_date: date) -> list[PortfolioCashFlow]:
        self.calls.append((start_date, end_date))
        return [cash_flow for cash_flow in self.cash_flows if cash_flow.portfolio_id == portfolio_id and start_date <= cash_flow.flow_date <= end_date]


class FakeFxConversionService:
    def __init__(self, rates: dict[tuple[str, str, date], Decimal]) -> None:
        self.rates = rates

    def get_rate(self, *, source_currency: str, target_currency: str, valuation_date: date) -> FxConversionRate | None:
        rate = self.rates.get((source_currency, target_currency, valuation_date))
        if rate is None:
            return None
        return FxConversionRate(source_currency=source_currency, target_currency=target_currency, rate=rate, rate_date=valuation_date, rate_kind="TCMB_MIDPOINT", source="TCMB")


def _fake_service(db_session: Session, *, portfolio: Portfolio, valuations: dict[date, Decimal | None], cash_flows: list[PortfolioCashFlow] | None = None, fx_rates: dict[tuple[str, str, date], Decimal] | None = None, incomplete_dates: set[date] | None = None) -> tuple[PortfolioPerformanceService, FakeValuationService, FakeCashFlowRepository]:
    valuation_service = FakeValuationService(valuations, incomplete_dates=incomplete_dates)
    cash_flow_repository = FakeCashFlowRepository(cash_flows or [])
    service = PortfolioPerformanceService(
        portfolio_repository=PortfolioRepository(db_session),
        cash_flow_repository=cash_flow_repository,  # type: ignore[arg-type]
        fx_conversion_service=FakeFxConversionService(fx_rates or {}),  # type: ignore[arg-type]
        portfolio_valuation_service=valuation_service,  # type: ignore[arg-type]
    )
    return service, valuation_service, cash_flow_repository


def _cash_flow(*, portfolio_id: int, flow_type: str = "DEPOSIT", amount: Decimal, currency: str = "TRY", flow_date: date = START_DATE) -> PortfolioCashFlow:
    return PortfolioCashFlow(portfolio_id=portfolio_id, flow_type=flow_type, amount=amount, currency=currency, flow_date=flow_date)

def test_no_flow_gain_returns_positive_daily_and_cumulative_return(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-gain@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("110")})

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.status == PERFORMANCE_STATUS_COMPLETE
    assert result.cumulative_return == Decimal("0.1")
    assert result.points[0].external_flow == Decimal("0")
    assert result.points[0].daily_return == Decimal("0.1")


def test_no_flow_loss_returns_negative_return(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-loss@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("90")})

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].daily_return == Decimal("-0.1")
    assert result.cumulative_return == Decimal("-0.1")


def test_pure_start_of_day_deposit_with_matching_value_increase_is_zero_return(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-deposit-zero@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    flow = _cash_flow(portfolio_id=portfolio.id, amount=Decimal("100"))
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("0"), START_DATE: Decimal("100")}, cash_flows=[flow])

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].external_flow == Decimal("100")
    assert result.points[0].daily_return == Decimal("0")
    assert result.cumulative_return == Decimal("0")


def test_withdrawal_semantics_use_negative_external_flow(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-withdrawal@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    flow = _cash_flow(portfolio_id=portfolio.id, flow_type="WITHDRAWAL", amount=Decimal("20"))
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("88")}, cash_flows=[flow])

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].external_flow == Decimal("-20")
    assert result.points[0].daily_return == Decimal("0.1")


def test_multiple_deposit_withdrawal_same_day_net_correctly(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-net-flow@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    cash_flows = [
        _cash_flow(portfolio_id=portfolio.id, amount=Decimal("100")),
        _cash_flow(portfolio_id=portfolio.id, flow_type="WITHDRAWAL", amount=Decimal("30")),
        _cash_flow(portfolio_id=portfolio.id, amount=Decimal("5")),
    ]
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("10"), START_DATE: Decimal("85")}, cash_flows=cash_flows)

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].external_flow == Decimal("75")
    assert result.points[0].daily_return == Decimal("0")


def test_foreign_external_flow_uses_historical_fx_on_flow_date(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-fx-flow@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    flow = _cash_flow(portfolio_id=portfolio.id, amount=Decimal("3"), currency="USD")
    service, _valuation_service, _cash_repo = _fake_service(
        db_session,
        portfolio=portfolio,
        valuations={PREVIOUS_DATE: Decimal("0"), START_DATE: Decimal("30")},
        cash_flows=[flow],
        fx_rates={("USD", "TRY", START_DATE): Decimal("10")},
    )

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].external_flow == Decimal("30")
    assert result.points[0].daily_return == Decimal("0")


def test_missing_external_flow_fx_makes_point_incomplete(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-missing-fx@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    flow = _cash_flow(portfolio_id=portfolio.id, amount=Decimal("3"), currency="USD")
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("0"), START_DATE: Decimal("30")}, cash_flows=[flow])

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    point = result.points[0]
    assert result.status == PERFORMANCE_STATUS_INCOMPLETE
    assert point.external_flow is None
    assert point.unavailable_reason == REASON_EXTERNAL_FLOW_FX_UNAVAILABLE


def test_start_date_minus_one_valuation_used_for_first_point(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-prev-day@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, valuation_service, cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("125")})

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].daily_return == Decimal("0.25")
    assert valuation_service.calls == [PREVIOUS_DATE, START_DATE]
    assert cash_repo.calls == [(START_DATE, START_DATE)]


def test_withdrawal_to_zero_is_not_applicable(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-zero-withdraw@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    flow = _cash_flow(portfolio_id=portfolio.id, flow_type="WITHDRAWAL", amount=Decimal("100"))
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("0")}, cash_flows=[flow])

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.status == PERFORMANCE_STATUS_NOT_APPLICABLE
    assert result.points[0].status == PERFORMANCE_STATUS_NOT_APPLICABLE
    assert result.points[0].daily_return is None


def test_zero_capital_gap_preserves_chain_and_later_deposit_restarts_segment(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-zero-gap@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    cash_flows = [
        _cash_flow(portfolio_id=portfolio.id, flow_type="WITHDRAWAL", amount=Decimal("110"), flow_date=date(2026, 1, 3)),
        _cash_flow(portfolio_id=portfolio.id, amount=Decimal("50"), flow_date=date(2026, 1, 4)),
    ]
    service, _valuation_service, _cash_repo = _fake_service(
        db_session,
        portfolio=portfolio,
        valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("110"), date(2026, 1, 3): Decimal("0"), date(2026, 1, 4): Decimal("55")},
        cash_flows=cash_flows,
    )

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=date(2026, 1, 4))

    assert [point.status for point in result.points] == [PERFORMANCE_STATUS_COMPLETE, PERFORMANCE_STATUS_NOT_APPLICABLE, PERFORMANCE_STATUS_COMPLETE]
    assert result.points[0].cumulative_return == Decimal("0.1")
    assert result.points[1].cumulative_return == Decimal("0.1")
    assert result.points[2].daily_return == Decimal("0.1")
    assert result.points[2].cumulative_return == Decimal("0.21")
    assert result.cumulative_return == Decimal("0.21")


def test_zero_denominator_with_value_is_incomplete(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-zero-denom-value@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("0"), START_DATE: Decimal("5")})

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].status == PERFORMANCE_STATUS_INCOMPLETE
    assert result.points[0].unavailable_reason == REASON_ZERO_DENOMINATOR_WITH_VALUE


def test_negative_capital_base_is_incomplete(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-negative-base@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    flow = _cash_flow(portfolio_id=portfolio.id, flow_type="WITHDRAWAL", amount=Decimal("20"))
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("10"), START_DATE: Decimal("0")}, cash_flows=[flow])

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].status == PERFORMANCE_STATUS_INCOMPLETE
    assert result.points[0].unavailable_reason == REASON_NON_POSITIVE_CAPITAL_BASE


def test_incomplete_day_breaks_requested_period_cumulative_but_later_daily_return_resumes(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-incomplete-break@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, _valuation_service, _cash_repo = _fake_service(
        db_session,
        portfolio=portfolio,
        valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("110"), date(2026, 1, 3): Decimal("120"), date(2026, 1, 4): Decimal("132"), date(2026, 1, 5): Decimal("145.2")},
        incomplete_dates={date(2026, 1, 3)},
    )

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=date(2026, 1, 5))

    assert result.status == PERFORMANCE_STATUS_INCOMPLETE
    assert result.cumulative_return is None
    assert result.points[0].daily_return == Decimal("0.1")
    assert result.points[0].cumulative_return == Decimal("0.1")
    assert result.points[1].unavailable_reason == REASON_VALUATION_INCOMPLETE
    assert result.points[2].unavailable_reason == REASON_VALUATION_INCOMPLETE
    assert result.points[3].status == PERFORMANCE_STATUS_COMPLETE
    assert result.points[3].daily_return == Decimal("0.1")
    assert result.points[3].cumulative_return is None


def test_all_not_applicable_range_returns_not_applicable(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-all-na@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("0"), START_DATE: Decimal("0"), date(2026, 1, 3): Decimal("0")})

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=date(2026, 1, 3))

    assert result.status == PERFORMANCE_STATUS_NOT_APPLICABLE
    assert result.cumulative_return is None
    assert all(point.status == PERFORMANCE_STATUS_NOT_APPLICABLE for point in result.points)


def test_exact_decimal_chaining_over_multiple_calendar_days(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-decimal-chain@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("3"), START_DATE: Decimal("4"), date(2026, 1, 3): Decimal("5")})

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=date(2026, 1, 3))

    expected_first = Decimal("1") / Decimal("3")
    expected_second = Decimal("1") / Decimal("4")
    expected_cumulative = (Decimal("1") + expected_first) * (Decimal("1") + expected_second) - Decimal("1")
    assert result.points[0].daily_return == expected_first
    assert result.points[1].daily_return == expected_second
    assert result.cumulative_return == expected_cumulative
    assert isinstance(result.cumulative_return, Decimal)


def test_future_transactions_and_cash_flows_do_not_affect_historical_performance(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-future@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    _add_cash_flow(db_session, portfolio_id=portfolio.id, amount=Decimal("100.00000000"), flow_date=PREVIOUS_DATE)
    _add_cash_flow(db_session, portfolio_id=portfolio.id, amount=Decimal("999.00000000"), flow_date=date(2026, 1, 5))
    asset = _create_asset(db_session, asset_code="FUT")
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id, quantity=Decimal("1.00000000"), unit_price=Decimal("999.00000000"), transaction_date=date(2026, 1, 5))

    result = _create_real_service(db_session).get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.status == PERFORMANCE_STATUS_COMPLETE
    assert result.points[0].portfolio_value == Decimal("100.00000000")
    assert result.points[0].external_flow == Decimal("0")
    assert result.points[0].daily_return == Decimal("0")


def test_buy_does_not_enter_external_flow(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-buy-internal@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    asset = _create_asset(db_session, asset_code="BUYI")
    _add_cash_flow(db_session, portfolio_id=portfolio.id, amount=Decimal("100.00000000"), flow_date=PREVIOUS_DATE)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="BUY", quantity=Decimal("5.00000000"), unit_price=Decimal("10.00000000"), transaction_date=START_DATE)
    _add_daily_data(db_session, asset_id=asset.id, data_date=START_DATE, price=Decimal("10.00000000"))

    result = _create_real_service(db_session).get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].external_flow == Decimal("0")
    assert result.points[0].portfolio_value == Decimal("100.0000000000000000")
    assert result.points[0].daily_return == Decimal("0E-16")


def test_sell_does_not_enter_external_flow(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-sell-internal@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    asset = _create_asset(db_session, asset_code="SELLI")
    _add_cash_flow(db_session, portfolio_id=portfolio.id, amount=Decimal("100.00000000"), flow_date=date(2025, 12, 31))
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="BUY", quantity=Decimal("10.00000000"), unit_price=Decimal("10.00000000"), transaction_date=PREVIOUS_DATE)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("5.00000000"), unit_price=Decimal("10.00000000"), transaction_date=START_DATE)
    _add_daily_data(db_session, asset_id=asset.id, data_date=PREVIOUS_DATE, price=Decimal("10.00000000"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=START_DATE, price=Decimal("10.00000000"))

    result = _create_real_service(db_session).get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].external_flow == Decimal("0")
    assert result.points[0].portfolio_value == Decimal("100.0000000000000000")
    assert result.points[0].daily_return == Decimal("0E-16")


def test_calendar_day_behavior_uses_latest_on_or_before_prices(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-calendar@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    asset = _create_asset(db_session, asset_code="CAL")
    _add_cash_flow(db_session, portfolio_id=portfolio.id, amount=Decimal("100.00000000"), flow_date=PREVIOUS_DATE)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id, quantity=Decimal("10.00000000"), unit_price=Decimal("10.00000000"), transaction_date=PREVIOUS_DATE)
    _add_daily_data(db_session, asset_id=asset.id, data_date=PREVIOUS_DATE, price=Decimal("10.00000000"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 1, 4), price=Decimal("12.00000000"))

    result = _create_real_service(db_session).get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=date(2026, 1, 4))

    assert [point.date for point in result.points] == [START_DATE, date(2026, 1, 3), date(2026, 1, 4)]
    assert result.points[0].daily_return == Decimal("0E-16")
    assert result.points[1].daily_return == Decimal("0")
    assert result.points[2].daily_return == Decimal("0.2")


def test_same_day_convention_is_deterministic_with_flow_and_trade(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-same-day@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    asset = _create_asset(db_session, asset_code="SDAY")
    _add_cash_flow(db_session, portfolio_id=portfolio.id, amount=Decimal("100.00000000"), flow_date=START_DATE)
    _add_transaction(db_session, portfolio_id=portfolio.id, asset_id=asset.id, quantity=Decimal("5.00000000"), unit_price=Decimal("10.00000000"), transaction_date=START_DATE)
    _add_daily_data(db_session, asset_id=asset.id, data_date=START_DATE, price=Decimal("12.00000000"))

    result = _create_real_service(db_session).get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.points[0].external_flow == Decimal("100.00000000")
    assert result.points[0].portfolio_value == Decimal("110.0000000000000000")
    assert result.points[0].daily_return == Decimal("0.1000000000000000")


def test_missing_previous_or_current_complete_valuation_makes_point_incomplete(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-missing-valuation@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: None})

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=START_DATE, end_date=START_DATE)

    assert result.status == PERFORMANCE_STATUS_INCOMPLETE
    assert result.points[0].portfolio_value is None
    assert result.points[0].unavailable_reason == REASON_VALUATION_INCOMPLETE


def test_reversed_date_range_raises_422(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-reversed@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service = _create_real_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=date(2026, 1, 4), end_date=START_DATE)

    assert exc_info.value.status_code == 422


def test_too_large_range_raises_422(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-too-large@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    service = _create_real_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=date(2026, 1, 1), end_date=date(2027, 1, 2))

    assert exc_info.value.status_code == 422


def test_exactly_366_inclusive_days_is_accepted(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-366@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    start_date = date(2026, 1, 1)
    end_date = date(2027, 1, 1)
    values = {start_date - timedelta(days=1): Decimal("0")}
    current = start_date
    while current <= end_date:
        values[current] = Decimal("0")
        current += timedelta(days=1)
    service, _valuation_service, _cash_repo = _fake_service(db_session, portfolio=portfolio, valuations=values)

    result = service.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=start_date, end_date=end_date)

    assert len(result.points) == 366
    assert result.status == PERFORMANCE_STATUS_NOT_APPLICABLE


def test_not_owned_portfolio_returns_canonical_404(db_session: Session) -> None:
    owner = _create_user(db_session, email="perf-owner@example.com")
    other = _create_user(db_session, email="perf-other@example.com")
    portfolio = _create_portfolio(db_session, user_id=owner.id)
    service = _create_real_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_performance(portfolio_id=portfolio.id, current_user=other, start_date=START_DATE, end_date=START_DATE)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Portfolio not found."

def test_foreign_external_flow_uses_real_latest_on_or_before_fx(db_session: Session) -> None:
    user = _create_user(db_session, email="perf-real-fx-flow@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    _add_cash_flow(
        db_session,
        portfolio_id=portfolio.id,
        amount=Decimal("3.00000000"),
        currency="USD",
        flow_date=START_DATE,
    )
    db_session.add(
        ExchangeRate(
            base_currency="USD",
            quote_currency="TRY",
            rate_date=PREVIOUS_DATE,
            forex_buying=Decimal("9.00000000"),
            forex_selling=Decimal("11.00000000"),
            source="TCMB",
        )
    )
    db_session.add(
        ExchangeRate(
            base_currency="USD",
            quote_currency="TRY",
            rate_date=date(2026, 1, 3),
            forex_buying=Decimal("19.00000000"),
            forex_selling=Decimal("21.00000000"),
            source="TCMB",
        )
    )
    db_session.flush()

    result = _create_real_service(db_session).get_performance(
        portfolio_id=portfolio.id,
        current_user=user,
        start_date=START_DATE,
        end_date=START_DATE,
    )

    assert result.status == PERFORMANCE_STATUS_COMPLETE
    assert result.points[0].portfolio_value == Decimal("30.0000000000000000")
    assert result.points[0].external_flow == Decimal("30.0000000000000000")
    assert result.points[0].daily_return == Decimal("0")

def test_mixed_same_day_external_flows_missing_one_fx_exposes_no_partial_flow(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="perf-partial-fx-flow@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    cash_flows = [
        _cash_flow(
            portfolio_id=portfolio.id,
            amount=Decimal("3"),
            currency="USD",
        ),
        _cash_flow(
            portfolio_id=portfolio.id,
            amount=Decimal("2"),
            currency="EUR",
        ),
    ]
    service, _valuation_service, _cash_repo = _fake_service(
        db_session,
        portfolio=portfolio,
        valuations={
            PREVIOUS_DATE: Decimal("100"),
            START_DATE: Decimal("130"),
            date(2026, 1, 3): Decimal("143"),
        },
        cash_flows=cash_flows,
        fx_rates={("USD", "TRY", START_DATE): Decimal("10")},
    )

    result = service.get_performance(
        portfolio_id=portfolio.id,
        current_user=user,
        start_date=START_DATE,
        end_date=date(2026, 1, 3),
    )

    incomplete_point = result.points[0]
    resumed_point = result.points[1]
    assert result.status == PERFORMANCE_STATUS_INCOMPLETE
    assert result.cumulative_return is None
    assert incomplete_point.status == PERFORMANCE_STATUS_INCOMPLETE
    assert incomplete_point.unavailable_reason == REASON_EXTERNAL_FLOW_FX_UNAVAILABLE
    assert incomplete_point.external_flow is None
    assert incomplete_point.daily_return is None
    assert incomplete_point.cumulative_return is None
    assert resumed_point.status == PERFORMANCE_STATUS_COMPLETE
    assert resumed_point.external_flow == Decimal("0")
    assert resumed_point.daily_return == Decimal("0.1")
    assert resumed_point.cumulative_return is None


def test_foreign_currency_withdrawal_preserves_negative_sign_after_fx_conversion(
    db_session: Session,
) -> None:
    user = _create_user(db_session, email="perf-foreign-withdrawal@example.com")
    portfolio = _create_portfolio(db_session, user_id=user.id)
    flow = _cash_flow(
        portfolio_id=portfolio.id,
        flow_type="WITHDRAWAL",
        amount=Decimal("3"),
        currency="USD",
    )
    service, _valuation_service, _cash_repo = _fake_service(
        db_session,
        portfolio=portfolio,
        valuations={PREVIOUS_DATE: Decimal("100"), START_DATE: Decimal("77")},
        cash_flows=[flow],
        fx_rates={("USD", "TRY", START_DATE): Decimal("10")},
    )

    result = service.get_performance(
        portfolio_id=portfolio.id,
        current_user=user,
        start_date=START_DATE,
        end_date=START_DATE,
    )

    point = result.points[0]
    expected_external_flow = Decimal("-30")
    expected_denominator = Decimal("100") + expected_external_flow
    expected_return = (Decimal("77") - Decimal("100") - expected_external_flow) / expected_denominator
    assert point.status == PERFORMANCE_STATUS_COMPLETE
    assert point.external_flow == expected_external_flow
    assert expected_denominator == Decimal("70")
    assert point.daily_return == expected_return
    assert point.daily_return == Decimal("0.1")
    assert isinstance(point.daily_return, Decimal)
