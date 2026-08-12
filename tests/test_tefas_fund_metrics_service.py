from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.response.tefas_fund_metrics_response import TefasFundMetricsResponse
from src.services.tefas_fund_metrics_service import TefasFundMetricsService


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source=data_source,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_daily_data(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date,
    price: Decimal = Decimal("100"),
    shares_outstanding: Decimal | None = Decimal("1000"),
    investor_count: int | None = 100,
    portfolio_size: Decimal | None = Decimal("10000"),
) -> TefasFundDailyData:
    row = TefasFundDailyData(
        asset_id=asset_id,
        data_date=data_date,
        price=price,
        shares_outstanding=shares_outstanding,
        investor_count=investor_count,
        portfolio_size=portfolio_size,
        exchange_bulletin_price=None,
    )
    db_session.add(row)
    db_session.flush()
    return row


def _build_service(db_session: Session) -> TefasFundMetricsService:
    return TefasFundMetricsService(
        AssetRepository(db_session),
        TefasFundDailyDataRepository(db_session),
    )


def _metrics(db_session: Session, *, fund_code: str = "AAL", data_date: date = date(2026, 8, 11)) -> TefasFundMetricsResponse:
    return _build_service(db_session).get_fund_metrics(
        fund_code=fund_code,
        data_date=data_date,
    )


def test_positive_daily_return(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("102.5"))

    result = _metrics(db_session)

    assert result.daily_return_ratio == Decimal("0.025")
    assert result.daily_return_baseline_date == date(2026, 8, 10)


def test_negative_daily_return(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("90"))

    result = _metrics(db_session)

    assert result.daily_return_ratio == Decimal("-0.1")


def test_daily_baseline_skips_calendar_gaps_and_uses_previous_available_observation(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 7), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("101"))

    result = _metrics(db_session)

    assert result.previous_observation_date == date(2026, 8, 7)
    assert result.daily_return_ratio == Decimal("0.01")


def test_missing_previous_observation_sets_daily_and_change_metrics_none(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))

    result = _metrics(db_session)

    assert result.previous_observation_date is None
    assert result.daily_return_ratio is None
    assert result.daily_return_baseline_date is None
    assert result.investor_count_change is None
    assert result.investor_count_growth_ratio is None
    assert result.aum_change is None
    assert result.aum_growth_ratio is None
    assert result.shares_outstanding_change is None


def test_five_observation_return_uses_fifth_previous_observation(db_session: Session) -> None:
    asset = _create_asset(db_session)
    for item_date, price in [
        (date(2026, 8, 1), Decimal("100")),
        (date(2026, 8, 4), Decimal("110")),
        (date(2026, 8, 5), Decimal("120")),
        (date(2026, 8, 6), Decimal("130")),
        (date(2026, 8, 7), Decimal("140")),
        (date(2026, 8, 11), Decimal("125")),
    ]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=item_date, price=price)

    result = _metrics(db_session)

    assert result.five_observation_return_ratio == Decimal("0.25")
    assert result.five_observation_baseline_date == date(2026, 8, 1)


def test_exactly_current_plus_five_previous_observations_succeeds(db_session: Session) -> None:
    asset = _create_asset(db_session)
    for day in [1, 2, 3, 4, 5]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, day), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("110"))

    result = _metrics(db_session)

    assert result.five_observation_return_ratio == Decimal("0.1")
    assert result.five_observation_baseline_date == date(2026, 8, 1)


def test_current_plus_only_four_previous_observations_sets_five_observation_metric_none(db_session: Session) -> None:
    asset = _create_asset(db_session)
    for day in [1, 2, 3, 4]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, day))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))

    result = _metrics(db_session)

    assert result.five_observation_return_ratio is None
    assert result.five_observation_baseline_date is None


def test_one_month_exact_target_date_baseline(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 7, 11), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("110"))

    result = _metrics(db_session)

    assert result.one_month_return_ratio == Decimal("0.1")
    assert result.one_month_baseline_date == date(2026, 7, 11)


def test_one_month_weekend_or_holiday_fallback_before_target_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 7, 10), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("105"))

    result = _metrics(db_session)

    assert result.one_month_return_ratio == Decimal("0.05")
    assert result.one_month_baseline_date == date(2026, 7, 10)


def test_one_month_baseline_exactly_seven_calendar_days_old_is_accepted(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 7, 4), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("103"))

    result = _metrics(db_session)

    assert result.one_month_return_ratio == Decimal("0.03")
    assert result.one_month_baseline_date == date(2026, 7, 4)


def test_one_month_baseline_eight_calendar_days_old_is_rejected(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 7, 3), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("103"))

    result = _metrics(db_session)

    assert result.one_month_return_ratio is None
    assert result.one_month_baseline_date is None


def test_one_month_search_never_uses_observation_after_target_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 7, 12), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("120"))

    result = _metrics(db_session)

    assert result.one_month_return_ratio is None
    assert result.one_month_baseline_date is None


def test_calendar_month_subtraction_works_correctly_around_month_end(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 2, 28), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 3, 31), price=Decimal("110"))

    result = _metrics(db_session, data_date=date(2026, 3, 31))

    assert result.one_month_return_ratio == Decimal("0.1")
    assert result.one_month_baseline_date == date(2026, 2, 28)


def test_investor_count_change(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), investor_count=100)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), investor_count=115)

    result = _metrics(db_session)

    assert result.investor_count_change == 15


def test_investor_count_growth_ratio(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), investor_count=80)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), investor_count=100)

    result = _metrics(db_session)

    assert result.investor_count_growth_ratio == Decimal("0.25")


def test_investor_zero_baseline_sets_growth_none_but_change_still_valid(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), investor_count=0)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), investor_count=10)

    result = _metrics(db_session)

    assert result.investor_count_change == 10
    assert result.investor_count_growth_ratio is None


def test_aum_change(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), portfolio_size=Decimal("10000"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), portfolio_size=Decimal("12500"))

    result = _metrics(db_session)

    assert result.aum_change == Decimal("2500.0000")


def test_aum_growth_ratio(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), portfolio_size=Decimal("10000"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), portfolio_size=Decimal("12500"))

    result = _metrics(db_session)

    assert result.aum_growth_ratio == Decimal("0.25")


def test_aum_zero_baseline_sets_growth_none(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), portfolio_size=Decimal("0"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), portfolio_size=Decimal("12500"))

    result = _metrics(db_session)

    assert result.aum_change == Decimal("12500.0000")
    assert result.aum_growth_ratio is None


def test_average_aum_per_investor(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        investor_count=4,
        portfolio_size=Decimal("1000"),
    )

    result = _metrics(db_session)

    assert result.average_aum_per_investor == Decimal("250.0000")


def test_zero_investor_count_sets_average_none(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        investor_count=0,
        portfolio_size=Decimal("1000"),
    )

    result = _metrics(db_session)

    assert result.average_aum_per_investor is None


def test_shares_outstanding_change(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), shares_outstanding=Decimal("1000"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), shares_outstanding=Decimal("925.5"))

    result = _metrics(db_session)

    assert result.shares_outstanding_change == Decimal("-74.5000")


def test_stored_null_values_produce_none_safely(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 10),
        shares_outstanding=None,
        investor_count=None,
        portfolio_size=None,
    )
    _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        shares_outstanding=None,
        investor_count=None,
        portfolio_size=None,
    )

    result = _metrics(db_session)

    assert result.investor_count_change is None
    assert result.investor_count_growth_ratio is None
    assert result.aum_change is None
    assert result.aum_growth_ratio is None
    assert result.average_aum_per_investor is None
    assert result.shares_outstanding_change is None


def test_decimal_calculations_do_not_use_float_artifacts(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("0.1"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("0.3"))

    result = _metrics(db_session)

    assert result.daily_return_ratio == Decimal("2")
    assert isinstance(result.daily_return_ratio, Decimal)
    assert "2.999999" not in str(result.daily_return_ratio)



def test_daily_baseline_price_zero_keeps_baseline_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("0"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("100"))

    result = _metrics(db_session)

    assert result.daily_return_ratio is None
    assert result.daily_return_baseline_date == date(2026, 8, 10)


def test_five_observation_baseline_price_zero_keeps_baseline_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    for item_date, price in [
        (date(2026, 8, 1), Decimal("0")),
        (date(2026, 8, 4), Decimal("110")),
        (date(2026, 8, 5), Decimal("120")),
        (date(2026, 8, 6), Decimal("130")),
        (date(2026, 8, 7), Decimal("140")),
        (date(2026, 8, 11), Decimal("125")),
    ]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=item_date, price=price)

    result = _metrics(db_session)

    assert result.five_observation_return_ratio is None
    assert result.five_observation_baseline_date == date(2026, 8, 1)


def test_one_month_accepted_baseline_price_zero_keeps_baseline_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 7, 11), price=Decimal("0"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("100"))

    result = _metrics(db_session)

    assert result.one_month_return_ratio is None
    assert result.one_month_baseline_date == date(2026, 7, 11)


def test_daily_baseline_price_null_keeps_baseline_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    previous = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("110"))
    previous.price = None  # type: ignore[assignment]

    result = _metrics(db_session)

    assert result.daily_return_ratio is None
    assert result.daily_return_baseline_date == date(2026, 8, 10)


def test_five_observation_baseline_price_null_keeps_baseline_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    fifth_previous = _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 1),
        price=Decimal("100"),
    )
    for day in [4, 5, 6, 7]:
        _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, day), price=Decimal("110"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("125"))
    fifth_previous.price = None  # type: ignore[assignment]

    result = _metrics(db_session)

    assert result.five_observation_return_ratio is None
    assert result.five_observation_baseline_date == date(2026, 8, 1)


def test_one_month_baseline_price_null_keeps_baseline_date(db_session: Session) -> None:
    asset = _create_asset(db_session)
    baseline = _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 7, 11), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), price=Decimal("110"))
    baseline.price = None  # type: ignore[assignment]

    result = _metrics(db_session)

    assert result.one_month_return_ratio is None
    assert result.one_month_baseline_date == date(2026, 7, 11)


def test_current_zero_investor_count_with_positive_previous_has_negative_one_growth(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10), investor_count=100)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11), investor_count=0)

    result = _metrics(db_session)

    assert result.investor_count_change == -100
    assert result.investor_count_growth_ratio == Decimal("-1")


def test_leap_year_calendar_month_subtraction_uses_february_29(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2024, 2, 29), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2024, 3, 31), price=Decimal("110"))

    result = _metrics(db_session, data_date=date(2024, 3, 31))

    assert result.one_month_return_ratio == Decimal("0.1")
    assert result.one_month_baseline_date == date(2024, 2, 29)


def test_january_calendar_month_subtraction_uses_previous_december(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2025, 12, 31), price=Decimal("100"))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 1, 31), price=Decimal("110"))

    result = _metrics(db_session, data_date=date(2026, 1, 31))

    assert result.one_month_return_ratio == Decimal("0.1")
    assert result.one_month_baseline_date == date(2025, 12, 31)

def test_fund_code_normalization(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="AB1")
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))

    result = _metrics(db_session, fund_code="  ab1  ")

    assert result.fund_code == "AB1"
    assert result.fund_name == "AB1 Fund"


def test_missing_tefas_asset_uses_current_not_found_behavior(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        _metrics(db_session, fund_code="AAL")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS fund not found."


def test_missing_exact_current_daily_data_observation_uses_clear_not_found_behavior(db_session: Session) -> None:
    _create_asset(db_session)

    with pytest.raises(HTTPException) as exc_info:
        _metrics(db_session, fund_code="AAL", data_date=date(2026, 8, 11))

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "TEFAS fund daily data not found."


def test_result_names_never_describe_aum_change_as_fund_flow_or_inflow() -> None:
    field_names = set(TefasFundMetricsResponse.model_fields)

    assert "aum_change" in field_names
    assert not any("flow" in field_name for field_name in field_names)
    assert not any("inflow" in field_name for field_name in field_names)


def test_input_orm_rows_are_not_mutated(db_session: Session) -> None:
    asset = _create_asset(db_session)
    previous = _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 10),
        price=Decimal("100"),
        shares_outstanding=Decimal("1000"),
        investor_count=100,
        portfolio_size=Decimal("10000"),
    )
    current = _add_daily_data(
        db_session,
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
        price=Decimal("110"),
        shares_outstanding=Decimal("1100"),
        investor_count=110,
        portfolio_size=Decimal("11000"),
    )
    before = (
        previous.price,
        previous.shares_outstanding,
        previous.investor_count,
        previous.portfolio_size,
        current.price,
        current.shares_outstanding,
        current.investor_count,
        current.portfolio_size,
    )

    _metrics(db_session)

    after = (
        previous.price,
        previous.shares_outstanding,
        previous.investor_count,
        previous.portfolio_size,
        current.price,
        current.shares_outstanding,
        current.investor_count,
        current.portfolio_size,
    )
    assert after == before


def test_service_does_not_write_or_commit(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    asset = _create_asset(db_session)
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 10))
    _add_daily_data(db_session, asset_id=asset.id, data_date=date(2026, 8, 11))
    commit_calls = 0
    flush_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    def counting_flush(*args: object, **kwargs: object) -> None:
        nonlocal flush_calls
        flush_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    monkeypatch.setattr(db_session, "flush", counting_flush)

    _metrics(db_session)

    assert commit_calls == 0
    assert flush_calls == 0

