from datetime import date
from decimal import Decimal

import pytest

from src.integrations.borsa_istanbul_reference_prices_client import BorsaIstanbulHistoricalObservation
from src.model.asset import Asset
from src.model.asset_price import AssetPrice
from src.services.borsa_istanbul_historical_backfill_service import BorsaIstanbulHistoricalBackfillError, BorsaIstanbulHistoricalBackfillService
from src.services.precious_metal_catalog_bootstrap_service import PreciousMetalCatalogBootstrapService


class FakeClient:
    def __init__(self, values): self.values, self.calls = values, []
    def fetch_historical(self, *, start_date, end_date, provider_metal_code):
        self.calls.append((start_date,end_date,provider_metal_code))
        return list(self.values.get((start_date,end_date,provider_metal_code), []))


def observation(code, day, raw): return BorsaIstanbulHistoricalObservation(code, day, raw)
def bootstrap(db): PreciousMetalCatalogBootstrapService(db).bootstrap()


def test_maps_all_three_normalizes_and_is_idempotent(db_session):
    bootstrap(db_session); day=date(2026,9,8)
    client=FakeClient({(day,day,"AU"):[observation("AU",day,Decimal("6830296.91"))], (day,day,"AG"):[observation("AG",day,101250)], (day,day,"PT"):[observation("PT",day,2800000)]})
    service=BorsaIstanbulHistoricalBackfillService(db_session,client)
    result=service.backfill(start_date=day,end_date=day,apply=True)
    assert (result.provider_observations,result.rows_inserted,result.rows_skipped)==(3,3,0)
    assets={a.asset_code:a for a in db_session.query(Asset).filter(Asset.data_source=="BORSA_ISTANBUL")}
    prices={p.asset_id:p for p in db_session.query(AssetPrice)}
    assert prices[assets["GOLD"].id].price==Decimal("6830.29691000")
    assert prices[assets["SILVER"].id].price==Decimal("101.25000000")
    assert prices[assets["PLATINUM"].id].price==Decimal("2800.00000000")
    assert {p.source for p in prices.values()}=={"BORSA_ISTANBUL_REFERENCE_PRICES"}
    assert service.backfill(start_date=day,end_date=day,apply=True).rows_skipped==3


def test_dry_run_missing_dates_and_exact_batch_boundaries(db_session):
    bootstrap(db_session); start,end=date(2026,9,8),date(2026,9,12)
    client=FakeClient({(start,date(2026,9,9),"AU"):[observation("AU",start,1000)]})
    result=BorsaIstanbulHistoricalBackfillService(db_session,client).backfill(start_date=start,end_date=end,asset_codes=("GOLD",),batch_days=2)
    assert result.dry_run and result.provider_observations==1 and db_session.query(AssetPrice).count()==0
    assert client.calls==[(start,date(2026,9,9),"AU"),(date(2026,9,10),date(2026,9,11),"AU"),(date(2026,9,12),end,"AU")]


def test_conflict_is_atomic_per_batch_and_prior_batches_remain(db_session):
    bootstrap(db_session); first,second=date(2026,9,8),date(2026,9,9)
    client=FakeClient({(first,first,"AU"):[observation("AU",first,1000)],(second,second,"AU"):[observation("AU",second,2000),observation("AU",second,3000)]})
    with pytest.raises(Exception): BorsaIstanbulHistoricalBackfillService(db_session,client).backfill(start_date=first,end_date=second,asset_codes=("GOLD",),batch_days=1,apply=True)
    assert [(p.price_date,p.price) for p in db_session.query(AssetPrice)]==[(first,Decimal("1.00000000"))]


def test_catalog_missing_wrong_metal_existing_conflict_and_invalid_ranges(db_session):
    day=date(2026,9,8); client=FakeClient({(day,day,"AU"):[observation("AU",day,1000)]})
    service=BorsaIstanbulHistoricalBackfillService(db_session,client)
    with pytest.raises(BorsaIstanbulHistoricalBackfillError): service.backfill(start_date=day,end_date=day,asset_codes=("GOLD",),apply=True)
    bootstrap(db_session); service.backfill(start_date=day,end_date=day,asset_codes=("GOLD",),apply=True)
    client.values[(day,day,"AU")]=[observation("AU",day,2000)]
    with pytest.raises(Exception): service.backfill(start_date=day,end_date=day,asset_codes=("GOLD",),apply=True)
    assert db_session.query(AssetPrice).one().price==Decimal("1.00000000")
    client.values[(day,day,"AU")]=[observation("AG",day,1000)]
    with pytest.raises(BorsaIstanbulHistoricalBackfillError): service.backfill(start_date=day,end_date=day,asset_codes=("GOLD",),apply=True)
    with pytest.raises(ValueError): service.backfill(start_date=date(2008,8,3),end_date=day)
    with pytest.raises(ValueError): service.backfill(start_date=day,end_date=date(2026,9,7))