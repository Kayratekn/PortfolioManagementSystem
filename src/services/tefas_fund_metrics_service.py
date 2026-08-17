from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status

from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.response.tefas_fund_metrics_response import TefasFundMetricsResponse


class TefasFundMetricsService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        daily_data_repository: TefasFundDailyDataRepository,
    ) -> None:
        self.asset_repository = asset_repository
        self.daily_data_repository = daily_data_repository

    def get_fund_metrics(
        self,
        *,
        fund_code: str,
        data_date: date,
    ) -> TefasFundMetricsResponse:
        normalized_fund_code = fund_code.strip().upper()
        if not normalized_fund_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS fund not found.",
            )

        asset = self.asset_repository.get_by_source_and_code(
            data_source="TEFAS",
            asset_code=normalized_fund_code,
        )
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS fund not found.",
            )

        current = self.daily_data_repository.get_by_asset_and_date(
            asset_id=asset.id,
            data_date=data_date,
        )
        if current is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS fund daily data not found.",
            )

        previous_rows = self.daily_data_repository.list_latest_before(
            asset_id=asset.id,
            data_date=data_date,
            limit=5,
        )
        previous = previous_rows[0] if previous_rows else None
        fifth_previous = previous_rows[4] if len(previous_rows) >= 5 else None

        one_month_target_date = _subtract_calendar_month(data_date)
        one_month_baseline = self.daily_data_repository.get_latest_on_or_before(
            asset_id=asset.id,
            data_date=one_month_target_date,
        )
        if (
            one_month_baseline is not None
            and one_month_baseline.data_date < one_month_target_date - timedelta(days=7)
        ):
            one_month_baseline = None

        daily_return_ratio = _return_ratio(current.price, previous.price) if previous else None
        five_observation_return_ratio = (
            _return_ratio(current.price, fifth_previous.price)
            if fifth_previous
            else None
        )
        one_month_return_ratio = (
            _return_ratio(current.price, one_month_baseline.price)
            if one_month_baseline
            else None
        )

        five_observation_aum_change = (
            _change(current.portfolio_size, fifth_previous.portfolio_size)
            if fifth_previous
            else None
        )
        five_observation_aum_growth_ratio = (
            _return_ratio(current.portfolio_size, fifth_previous.portfolio_size)
            if fifth_previous
            else None
        )
        five_observation_investor_count_change = (
            _change(current.investor_count, fifth_previous.investor_count)
            if fifth_previous
            else None
        )
        five_observation_investor_count_growth_ratio = (
            _int_growth_ratio(current.investor_count, fifth_previous.investor_count)
            if fifth_previous
            else None
        )
        one_month_aum_change = (
            _change(current.portfolio_size, one_month_baseline.portfolio_size)
            if one_month_baseline
            else None
        )
        one_month_aum_growth_ratio = (
            _return_ratio(current.portfolio_size, one_month_baseline.portfolio_size)
            if one_month_baseline
            else None
        )
        one_month_investor_count_change = (
            _change(current.investor_count, one_month_baseline.investor_count)
            if one_month_baseline
            else None
        )
        one_month_investor_count_growth_ratio = (
            _int_growth_ratio(
                current.investor_count,
                one_month_baseline.investor_count,
            )
            if one_month_baseline
            else None
        )
        investor_count_change = (
            _change(current.investor_count, previous.investor_count)
            if previous
            else None
        )
        investor_count_growth_ratio = (
            _int_growth_ratio(current.investor_count, previous.investor_count)
            if previous
            else None
        )

        aum_change = (
            _change(current.portfolio_size, previous.portfolio_size)
            if previous
            else None
        )
        aum_growth_ratio = (
            _return_ratio(current.portfolio_size, previous.portfolio_size)
            if previous
            else None
        )

        average_aum_per_investor = _average_aum_per_investor(
            current.portfolio_size,
            current.investor_count,
        )

        shares_outstanding_change = (
            _change(current.shares_outstanding, previous.shares_outstanding)
            if previous
            else None
        )

        is_byf = asset.fund_kind == "BYF"
        byf_exchange_bulletin_daily_return_ratio = (
            _return_ratio(
                current.exchange_bulletin_price,
                previous.exchange_bulletin_price,
            )
            if is_byf and previous
            else None
        )
        byf_exchange_bulletin_daily_return_baseline_date = (
            previous.data_date if is_byf and previous else None
        )
        byf_exchange_bulletin_price_to_price_ratio = (
            _return_ratio(current.exchange_bulletin_price, current.price)
            if is_byf
            else None
        )
        return TefasFundMetricsResponse(
            fund_code=asset.asset_code,
            fund_name=asset.asset_name,
            data_date=current.data_date,
            previous_observation_date=previous.data_date if previous else None,
            daily_return_ratio=daily_return_ratio,
            daily_return_baseline_date=previous.data_date if previous else None,
            five_observation_return_ratio=five_observation_return_ratio,
            five_observation_baseline_date=(
                fifth_previous.data_date if fifth_previous else None
            ),
            five_observation_aum_change=five_observation_aum_change,
            five_observation_aum_growth_ratio=five_observation_aum_growth_ratio,
            five_observation_investor_count_change=(
                five_observation_investor_count_change
            ),
            five_observation_investor_count_growth_ratio=(
                five_observation_investor_count_growth_ratio
            ),
            one_month_return_ratio=one_month_return_ratio,
            one_month_baseline_date=(
                one_month_baseline.data_date if one_month_baseline else None
            ),
            one_month_aum_change=one_month_aum_change,
            one_month_aum_growth_ratio=one_month_aum_growth_ratio,
            one_month_investor_count_change=one_month_investor_count_change,
            one_month_investor_count_growth_ratio=(
                one_month_investor_count_growth_ratio
            ),
            investor_count_change=investor_count_change,
            investor_count_growth_ratio=investor_count_growth_ratio,
            aum_change=aum_change,
            aum_growth_ratio=aum_growth_ratio,
            average_aum_per_investor=average_aum_per_investor,
            shares_outstanding_change=shares_outstanding_change,
            byf_exchange_bulletin_daily_return_ratio=(
                byf_exchange_bulletin_daily_return_ratio
            ),
            byf_exchange_bulletin_daily_return_baseline_date=(
                byf_exchange_bulletin_daily_return_baseline_date
            ),
            byf_exchange_bulletin_price_to_price_ratio=(
                byf_exchange_bulletin_price_to_price_ratio
            ),
        )


def _subtract_calendar_month(value: date) -> date:
    year = value.year
    month = value.month - 1
    if month == 0:
        year -= 1
        month = 12

    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(value.day, last_day))


def _return_ratio(
    current_value: Decimal | None,
    baseline_value: Decimal | None,
) -> Decimal | None:
    if current_value is None or baseline_value is None or baseline_value == 0:
        return None

    return (current_value / baseline_value) - Decimal("1")


def _int_growth_ratio(
    current_value: int | None,
    baseline_value: int | None,
) -> Decimal | None:
    if current_value is None or baseline_value is None or baseline_value == 0:
        return None

    return (Decimal(current_value) / Decimal(baseline_value)) - Decimal("1")


def _average_aum_per_investor(
    portfolio_size: Decimal | None,
    investor_count: int | None,
) -> Decimal | None:
    if portfolio_size is None or investor_count is None or investor_count == 0:
        return None

    return portfolio_size / Decimal(investor_count)


def _change(
    current_value: int | Decimal | None,
    baseline_value: int | Decimal | None,
) -> int | Decimal | None:
    if current_value is None or baseline_value is None:
        return None

    return current_value - baseline_value
