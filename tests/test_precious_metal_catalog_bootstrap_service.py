from sqlalchemy import select
from sqlalchemy.orm import Session
import pytest

from src.model.asset import Asset
from src.services.precious_metal_catalog_bootstrap_service import (
    PreciousMetalCatalogBootstrapConflictError,
    PreciousMetalCatalogBootstrapService,
)


def _assets(db_session: Session) -> list[Asset]:
    return list(db_session.scalars(select(Asset).order_by(Asset.data_source, Asset.asset_code)))


def test_bootstrap_creates_exact_canonical_precious_metal_catalog(db_session: Session) -> None:
    result = PreciousMetalCatalogBootstrapService(db_session).bootstrap()

    assert result.assets_created == 3
    assert result.assets_skipped == 0
    metals = [asset for asset in _assets(db_session) if asset.data_source == "BORSA_ISTANBUL"]
    assert [(asset.asset_code, asset.asset_name) for asset in metals] == [
        ("GOLD", "Gold"),
        ("PLATINUM", "Platinum"),
        ("SILVER", "Silver"),
    ]
    assert all(asset.asset_type == "PRECIOUS_METAL" for asset in metals)
    assert all(asset.currency == "TRY" for asset in metals)
    assert all(asset.fund_kind is None and asset.isin is None and asset.is_active is True for asset in metals)


def test_bootstrap_is_idempotent(db_session: Session) -> None:
    service = PreciousMetalCatalogBootstrapService(db_session)
    service.bootstrap()

    result = service.bootstrap()

    assert result.assets_created == 0
    assert result.assets_skipped == 3
    assert len(_assets(db_session)) == 3


def test_bootstrap_rejects_incompatible_existing_identity_without_rewriting(db_session: Session) -> None:
    conflicting_asset = Asset(
        asset_code="GOLD",
        asset_name="Wrong Gold",
        asset_type="PRECIOUS_METAL",
        fund_kind=None,
        isin=None,
        currency="TRY",
        data_source="BORSA_ISTANBUL",
        is_active=True,
    )
    db_session.add(conflicting_asset)
    db_session.commit()

    with pytest.raises(PreciousMetalCatalogBootstrapConflictError, match="asset_name"):
        PreciousMetalCatalogBootstrapService(db_session).bootstrap()

    db_session.refresh(conflicting_asset)
    assert conflicting_asset.asset_name == "Wrong Gold"
    assert [asset.asset_code for asset in _assets(db_session)] == ["GOLD"]


def test_bootstrap_leaves_unrelated_assets_untouched(db_session: Session) -> None:
    unrelated = Asset(
        asset_code="AAA",
        asset_name="Unrelated Fund",
        asset_type="FUND",
        fund_kind="YAT",
        isin=None,
        currency="TRY",
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(unrelated)
    db_session.commit()

    PreciousMetalCatalogBootstrapService(db_session).bootstrap()

    db_session.refresh(unrelated)
    assert unrelated.asset_name == "Unrelated Fund"
    assert unrelated.data_source == "TEFAS"
