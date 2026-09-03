from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterator

from fastapi import HTTPException, status

from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.model.user import User
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.services.fx_conversion_service import FxConversionService
from src.services.portfolio_valuation_service import (
    PORTFOLIO_STATUS_COMPLETE,
    PortfolioValuationResult,
    PortfolioValuationService,
)


PERFORMANCE_STATUS_COMPLETE = "COMPLETE"
PERFORMANCE_STATUS_INCOMPLETE = "INCOMPLETE"
PERFORMANCE_STATUS_NOT_APPLICABLE = "NOT_APPLICABLE"

REASON_VALUATION_INCOMPLETE = "VALUATION_INCOMPLETE"
REASON_EXTERNAL_FLOW_FX_UNAVAILABLE = "EXTERNAL_FLOW_FX_UNAVAILABLE"
REASON_ZERO_DENOMINATOR_WITH_VALUE = "ZERO_DENOMINATOR_WITH_VALUE"
REASON_NON_POSITIVE_CAPITAL_BASE = "NON_POSITIVE_CAPITAL_BASE"

MAX_PERFORMANCE_RANGE_DAYS = 365
DECIMAL_ZERO = Decimal("0")
DECIMAL_ONE = Decimal("1")


@dataclass(frozen=True)
class PortfolioPerformancePoint:
    date: date
    portfolio_value: Decimal | None
    external_flow: Decimal | None
    daily_return: Decimal | None
    cumulative_return: Decimal | None
    status: str
    unavailable_reason: str | None


@dataclass(frozen=True)
class PortfolioPerformanceResult:
    portfolio_id: int
    base_currency: str
    start_date: date
    end_date: date
    status: str
    cumulative_return: Decimal | None
    points: tuple[PortfolioPerformancePoint, ...]


class PortfolioPerformanceService:
    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        cash_flow_repository: PortfolioCashFlowRepository,
        fx_conversion_service: FxConversionService,
        portfolio_valuation_service: PortfolioValuationService,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.cash_flow_repository = cash_flow_repository
        self.fx_conversion_service = fx_conversion_service
        self.portfolio_valuation_service = portfolio_valuation_service

    def get_performance(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        start_date: date,
        end_date: date,
    ) -> PortfolioPerformanceResult:
        self._validate_date_range(start_date=start_date, end_date=end_date)
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        cash_flows_by_date = self._group_cash_flows_by_date(
            self.cash_flow_repository.list_by_portfolio_between(
                portfolio_id=portfolio_id,
                start_date=start_date,
                end_date=end_date,
            )
        )

        factor = DECIMAL_ONE
        cumulative_chain_broken = False
        has_complete_point = False
        has_incomplete_point = False
        points: list[PortfolioPerformancePoint] = []

        previous_valuation = self.portfolio_valuation_service.get_valuation(
            portfolio_id=portfolio_id,
            current_user=current_user,
            valuation_date=start_date - timedelta(days=1),
        )

        for current_date in self._iter_dates(start_date=start_date, end_date=end_date):
            current_valuation = self.portfolio_valuation_service.get_valuation(
                portfolio_id=portfolio_id,
                current_user=current_user,
                valuation_date=current_date,
            )
            external_flow = self._calculate_external_flow(
                cash_flows=cash_flows_by_date.get(current_date, ()),
                base_currency=portfolio.base_currency,
                flow_date=current_date,
            )
            point = self._build_point(
                point_date=current_date,
                previous_valuation=previous_valuation,
                current_valuation=current_valuation,
                external_flow=external_flow,
                factor=factor,
                cumulative_chain_broken=cumulative_chain_broken,
                has_complete_point=has_complete_point,
            )

            if point.status == PERFORMANCE_STATUS_COMPLETE:
                has_complete_point = True
                if not cumulative_chain_broken and point.daily_return is not None:
                    factor *= DECIMAL_ONE + point.daily_return
                    point = PortfolioPerformancePoint(
                        date=point.date,
                        portfolio_value=point.portfolio_value,
                        external_flow=point.external_flow,
                        daily_return=point.daily_return,
                        cumulative_return=factor - DECIMAL_ONE,
                        status=point.status,
                        unavailable_reason=point.unavailable_reason,
                    )
            elif point.status == PERFORMANCE_STATUS_INCOMPLETE:
                has_incomplete_point = True
                cumulative_chain_broken = True

            points.append(point)
            previous_valuation = current_valuation

        result_status = self._aggregate_status(
            has_incomplete_point=has_incomplete_point,
            has_complete_point=has_complete_point,
        )
        return PortfolioPerformanceResult(
            portfolio_id=portfolio_id,
            base_currency=portfolio.base_currency,
            start_date=start_date,
            end_date=end_date,
            status=result_status,
            cumulative_return=(
                factor - DECIMAL_ONE
                if result_status == PERFORMANCE_STATUS_COMPLETE
                else None
            ),
            points=tuple(points),
        )

    @staticmethod
    def _validate_date_range(*, start_date: date, end_date: date) -> None:
        if end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="end_date must be greater than or equal to start_date.",
            )
        if (end_date - start_date).days > MAX_PERFORMANCE_RANGE_DAYS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Performance date range cannot exceed 366 calendar days.",
            )

    @staticmethod
    def _group_cash_flows_by_date(
        cash_flows: list[PortfolioCashFlow],
    ) -> dict[date, tuple[PortfolioCashFlow, ...]]:
        grouped: dict[date, list[PortfolioCashFlow]] = defaultdict(list)
        for cash_flow in cash_flows:
            grouped[cash_flow.flow_date].append(cash_flow)
        return {
            flow_date: tuple(day_cash_flows)
            for flow_date, day_cash_flows in grouped.items()
        }

    @staticmethod
    def _iter_dates(*, start_date: date, end_date: date) -> Iterator[date]:
        current_date = start_date
        while current_date <= end_date:
            yield current_date
            current_date += timedelta(days=1)

    def _calculate_external_flow(
        self,
        *,
        cash_flows: tuple[PortfolioCashFlow, ...],
        base_currency: str,
        flow_date: date,
    ) -> Decimal | None:
        total = DECIMAL_ZERO
        for cash_flow in cash_flows:
            signed_amount = (
                cash_flow.amount
                if cash_flow.flow_type == "DEPOSIT"
                else -cash_flow.amount
            )
            if cash_flow.currency == base_currency:
                total += signed_amount
                continue

            fx_rate = self.fx_conversion_service.get_rate(
                source_currency=cash_flow.currency,
                target_currency=base_currency,
                valuation_date=flow_date,
            )
            if fx_rate is None:
                return None
            total += signed_amount * fx_rate.rate
        return total

    def _build_point(
        self,
        *,
        point_date: date,
        previous_valuation: PortfolioValuationResult,
        current_valuation: PortfolioValuationResult,
        external_flow: Decimal | None,
        factor: Decimal,
        cumulative_chain_broken: bool,
        has_complete_point: bool,
    ) -> PortfolioPerformancePoint:
        portfolio_value = self._complete_portfolio_value(current_valuation)
        if external_flow is None:
            return self._incomplete_point(
                point_date=point_date,
                portfolio_value=portfolio_value,
                external_flow=None,
                unavailable_reason=REASON_EXTERNAL_FLOW_FX_UNAVAILABLE,
            )

        previous_value = self._complete_portfolio_value(previous_valuation)
        if previous_value is None or portfolio_value is None:
            return self._incomplete_point(
                point_date=point_date,
                portfolio_value=portfolio_value,
                external_flow=external_flow,
                unavailable_reason=REASON_VALUATION_INCOMPLETE,
            )

        capital_base = previous_value + external_flow
        if capital_base > DECIMAL_ZERO:
            daily_return = (portfolio_value - previous_value - external_flow) / capital_base
            return PortfolioPerformancePoint(
                date=point_date,
                portfolio_value=portfolio_value,
                external_flow=external_flow,
                daily_return=daily_return,
                cumulative_return=None if cumulative_chain_broken else factor - DECIMAL_ONE,
                status=PERFORMANCE_STATUS_COMPLETE,
                unavailable_reason=None,
            )

        if capital_base == DECIMAL_ZERO and portfolio_value == DECIMAL_ZERO:
            return PortfolioPerformancePoint(
                date=point_date,
                portfolio_value=portfolio_value,
                external_flow=external_flow,
                daily_return=None,
                cumulative_return=(
                    None
                    if cumulative_chain_broken or not has_complete_point
                    else factor - DECIMAL_ONE
                ),
                status=PERFORMANCE_STATUS_NOT_APPLICABLE,
                unavailable_reason=None,
            )

        reason = (
            REASON_ZERO_DENOMINATOR_WITH_VALUE
            if capital_base == DECIMAL_ZERO
            else REASON_NON_POSITIVE_CAPITAL_BASE
        )
        return self._incomplete_point(
            point_date=point_date,
            portfolio_value=portfolio_value,
            external_flow=external_flow,
            unavailable_reason=reason,
        )

    @staticmethod
    def _complete_portfolio_value(
        valuation: PortfolioValuationResult,
    ) -> Decimal | None:
        if valuation.status != PORTFOLIO_STATUS_COMPLETE:
            return None
        return valuation.total_portfolio_value

    @staticmethod
    def _incomplete_point(
        *,
        point_date: date,
        portfolio_value: Decimal | None,
        external_flow: Decimal | None,
        unavailable_reason: str,
    ) -> PortfolioPerformancePoint:
        return PortfolioPerformancePoint(
            date=point_date,
            portfolio_value=portfolio_value,
            external_flow=external_flow,
            daily_return=None,
            cumulative_return=None,
            status=PERFORMANCE_STATUS_INCOMPLETE,
            unavailable_reason=unavailable_reason,
        )

    @staticmethod
    def _aggregate_status(
        *,
        has_incomplete_point: bool,
        has_complete_point: bool,
    ) -> str:
        if has_incomplete_point:
            return PERFORMANCE_STATUS_INCOMPLETE
        if has_complete_point:
            return PERFORMANCE_STATUS_COMPLETE
        return PERFORMANCE_STATUS_NOT_APPLICABLE