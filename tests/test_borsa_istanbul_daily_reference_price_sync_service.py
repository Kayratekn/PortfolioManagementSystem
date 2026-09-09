from datetime import date
from decimal import Decimal

import pytest

from src.config.supported_precious_metals import BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE
from src.integrations.borsa_istanbul_current_reference_prices_client import BorsaIstanbulCurrentReferencePricesSnapshot
from src.model.asset import Asset
from src.model.asset_price import AssetPrice
from src.services.borsa_istanbul_daily_reference_price_sync_service import (
    BorsaIstanbulDailyReferencePriceSyncError,
    BorsaIstanbulDailyReferencePriceSyncService,
)
from src.services.precious_metal_catalog_bootstrap_service import PreciousMetalCatalogBootstrapService


EFFECTIVE_DATE = date(2026, 9, 8)
EXECUTION_DATE = date(2026, 9, 9)


class FakeCurrentClient:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.calls = 0

    def fetch_current(self):
        self.calls += 1
        return self.snapshot


def snapshot(*, gold=Decimal("6830296.91"), silver=Decimal("103103.93"), platinum=Decimal("2800000.00"), effective_date=EFFECTIVE_DATE):
    return BorsaIstanbulCurrentReferencePricesSnapshot(effective_date, gold, silver, platinum)


def bootstrap(db_session):
    PreciousMetalCatalogBootstrapService(db_session).bootstrap()


def prices(db_session):
    return list(db_session.query(AssetPrice).order_by(AssetPrice.asset_id))


def test_complete_snapshot_imports_all_three_using_provider_effective_date(db_session):
    bootstrap(db_session)
    result = BorsaIstanbulDailyReferencePriceSyncService(db_session, FakeCurrentClient(snapshot())).sync()

    assets = {asset.asset_code: asset for asset in db_session.query(Asset).filter(Asset.data_source == "BORSA_ISTANBUL")}
    persisted = {price.asset_id: price for price in prices(db_session)}
    assert (result.effective_date, result.provider_observations, result.rows_inserted, result.rows_skipped) == (EFFECTIVE_DATE, 3, 3, 0)
    assert persisted[assets["GOLD"].id].price == Decimal("6830.29691000")
    assert persisted[assets["SILVER"].id].price == Decimal("103.10393000")
    assert persisted[assets["PLATINUM"].id].price == Decimal("2800.00000000")
    assert {price.price_date for price in persisted.values()} == {EFFECTIVE_DATE}
    assert {price.source for price in persisted.values()} == {BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE}
    assert db_session.query(AssetPrice).filter(AssetPrice.price_date == EXECUTION_DATE).count() == 0


def test_repeated_old_snapshot_is_idempotent_and_never_creates_carry_forward_rows(db_session):
    bootstrap(db_session)
    service = BorsaIstanbulDailyReferencePriceSyncService(db_session, FakeCurrentClient(snapshot()))
    assert service.sync().rows_inserted == 3
    result = service.sync()
    assert (result.rows_inserted, result.rows_skipped) == (0, 3)
    assert db_session.query(AssetPrice).count() == 3
    assert db_session.query(AssetPrice).filter(AssetPrice.price_date == EXECUTION_DATE).count() == 0


def test_malformed_one_metal_has_no_asset_price_writes(db_session):
    bootstrap(db_session)
    invalid = snapshot(silver=Decimal("0"))
    with pytest.raises(Exception):
        BorsaIstanbulDailyReferencePriceSyncService(db_session, FakeCurrentClient(invalid)).sync()
    assert db_session.query(AssetPrice).count() == 0


def test_conflict_rolls_back_three_metal_batch_without_overwrite(db_session):
    bootstrap(db_session)
    silver = db_session.query(Asset).filter(Asset.asset_code == "SILVER").one()
    db_session.add(AssetPrice(asset_id=silver.id, price_date=EFFECTIVE_DATE, price=Decimal("1"), source=BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE))
    db_session.commit()

    with pytest.raises(Exception):
        BorsaIstanbulDailyReferencePriceSyncService(db_session, FakeCurrentClient(snapshot())).sync()

    persisted = prices(db_session)
    assert len(persisted) == 1
    assert persisted[0].asset_id == silver.id and persisted[0].price == Decimal("1.00000000")


def test_missing_or_incompatible_catalog_fails_before_persistence(db_session):
    with pytest.raises(BorsaIstanbulDailyReferencePriceSyncError, match="missing"):
        BorsaIstanbulDailyReferencePriceSyncService(db_session, FakeCurrentClient(snapshot())).sync()
    assert db_session.query(AssetPrice).count() == 0

    bootstrap(db_session)
    gold = db_session.query(Asset).filter(Asset.asset_code == "GOLD").one()
    gold.is_active = False
    db_session.commit()
    with pytest.raises(BorsaIstanbulDailyReferencePriceSyncError, match="incompatible"):
        BorsaIstanbulDailyReferencePriceSyncService(db_session, FakeCurrentClient(snapshot())).sync()
    assert db_session.query(AssetPrice).count() == 0


def test_palladium_has_no_application_asset_or_price(db_session):
    bootstrap(db_session)
    BorsaIstanbulDailyReferencePriceSyncService(db_session, FakeCurrentClient(snapshot())).sync()
    assert db_session.query(Asset).filter(Asset.asset_code == "PALLADIUM").count() == 0
    assert db_session.query(AssetPrice).count() == 3