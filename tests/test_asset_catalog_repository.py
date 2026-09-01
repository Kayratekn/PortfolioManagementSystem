from __future__ import annotations

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.repositories.asset_repository import AssetRepository


def _create_asset(
    db_session: Session,
    *,
    asset_code: str,
    asset_name: str,
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    isin: str | None = "TRTESTISIN01",
    currency: str | None = "TRY",
    data_source: str = "TEFAS",
    is_active: bool = True,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type=asset_type,
        fund_kind=fund_kind,
        isin=isin,
        currency=currency,
        data_source=data_source,
        is_active=is_active,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def test_list_active_catalog_returns_only_active_assets_in_code_and_id_order(
    db_session: Session,
) -> None:
    repository = AssetRepository(db_session)
    second_same_code = _create_asset(
        db_session,
        asset_code="AAA",
        asset_name="Second AAA Fund",
        data_source="MANUAL",
    )
    later_code = _create_asset(
        db_session,
        asset_code="BBB",
        asset_name="BBB Fund",
    )
    first_same_code = _create_asset(
        db_session,
        asset_code="AAA",
        asset_name="First AAA Fund",
    )
    _create_asset(
        db_session,
        asset_code="AAB",
        asset_name="Inactive Fund",
        is_active=False,
    )

    result = repository.list_active_catalog(skip=0, limit=10)

    assert first_same_code.id > second_same_code.id
    assert result == [second_same_code, first_same_code, later_code]


def test_list_active_catalog_applies_pagination(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    _create_asset(db_session, asset_code="AAA", asset_name="AAA Fund")
    second = _create_asset(db_session, asset_code="BBB", asset_name="BBB Fund")
    third = _create_asset(db_session, asset_code="CCC", asset_name="CCC Fund")

    result = repository.list_active_catalog(skip=1, limit=2)

    assert result == [second, third]


def test_list_active_catalog_searches_code_and_name_case_insensitively(
    db_session: Session,
) -> None:
    repository = AssetRepository(db_session)
    code_match = _create_asset(db_session, asset_code="AAL", asset_name="Money Market")
    name_match = _create_asset(db_session, asset_code="BLH", asset_name="Aal Balanced")
    _create_asset(db_session, asset_code="CCC", asset_name="Equity Fund")
    _create_asset(
        db_session,
        asset_code="AALX",
        asset_name="Inactive Match",
        is_active=False,
    )

    result = repository.list_active_catalog(skip=0, limit=10, search="aal")

    assert result == [code_match, name_match]


def test_count_active_catalog_matches_active_search_scope(db_session: Session) -> None:
    repository = AssetRepository(db_session)
    _create_asset(db_session, asset_code="AAL", asset_name="Money Market")
    _create_asset(db_session, asset_code="BLH", asset_name="Aal Balanced")
    _create_asset(db_session, asset_code="CCC", asset_name="Equity Fund")
    _create_asset(
        db_session,
        asset_code="AALX",
        asset_name="Inactive Match",
        is_active=False,
    )

    assert repository.count_active_catalog(search="aal") == 2
    assert repository.count_active_catalog(search="missing") == 0
