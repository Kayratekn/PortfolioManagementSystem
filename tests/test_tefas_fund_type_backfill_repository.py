from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_type_history import TefasFundTypeHistory
from src.repositories.asset_repository import AssetRepository


def _add_asset(
    db_session: Session,
    *,
    asset_code: str,
    fund_kind: str = "YAT",
    data_source: str = "TEFAS",
    is_active: bool = True,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Fund",
        asset_type="FUND",
        fund_kind=fund_kind,
        currency=None,
        data_source=data_source,
        is_active=is_active,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _add_history(
    db_session: Session,
    *,
    asset_id: int,
    closed: bool = False,
) -> None:
    observed_at = datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)
    db_session.add(
        TefasFundTypeHistory(
            asset_id=asset_id,
            fund_type_name="Type A",
            source_endpoint="fonProfilDtyGetir",
            source_field_name="fonTuru",
            first_observed_at=observed_at,
            last_observed_at=observed_at,
            closed_at=observed_at if closed else None,
        )
    )
    db_session.flush()


def test_list_active_tefas_without_current_fund_type_filters_scope_and_orders_by_code(
    db_session: Session,
) -> None:
    eligible_b = _add_asset(db_session, asset_code="BLH")
    eligible_a = _add_asset(db_session, asset_code="AAL")
    open_history = _add_asset(db_session, asset_code="AB1")
    closed_history = _add_asset(db_session, asset_code="AFO")
    _add_asset(db_session, asset_code="EMK1", fund_kind="EMK")
    _add_asset(db_session, asset_code="OLD", is_active=False)
    _add_asset(db_session, asset_code="EXT", data_source="OTHER")
    _add_history(db_session, asset_id=open_history.id, closed=False)
    _add_history(db_session, asset_id=closed_history.id, closed=True)

    result = AssetRepository(db_session).list_active_tefas_without_current_fund_type(
        fund_kind="YAT",
        limit=10,
    )

    assert [asset.asset_code for asset in result] == [
        eligible_a.asset_code,
        closed_history.asset_code,
        eligible_b.asset_code,
    ]


def test_list_active_tefas_without_current_fund_type_applies_limit(
    db_session: Session,
) -> None:
    _add_asset(db_session, asset_code="AAL")
    _add_asset(db_session, asset_code="AB1")
    _add_asset(db_session, asset_code="BLH")

    result = AssetRepository(db_session).list_active_tefas_without_current_fund_type(
        fund_kind="YAT",
        limit=2,
    )

    assert [asset.asset_code for asset in result] == ["AAL", "AB1"]


def test_list_active_tefas_without_current_fund_type_returns_empty_for_nonpositive_limit(
    db_session: Session,
) -> None:
    _add_asset(db_session, asset_code="AAL")

    result = AssetRepository(db_session).list_active_tefas_without_current_fund_type(
        fund_kind="YAT",
        limit=0,
    )

    assert result == []
