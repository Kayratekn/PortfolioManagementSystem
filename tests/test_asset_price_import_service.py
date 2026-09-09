from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.supported_precious_metals import BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE
from src.model.asset import Asset
from src.model.asset_price import AssetPrice
from src.services.asset_price_import_service import (
    AssetPriceImportConflictError,
    AssetPriceImportObservation,
    AssetPriceImportService,
)


PRICE_DATE = date(2026, 9, 8)


def _asset(db_session: Session, *, code: str, source: str = "BORSA_ISTANBUL") -> Asset:
    asset = Asset(
        asset_code=code,
        asset_name=code.title(),
        asset_type="PRECIOUS_METAL" if source == "BORSA_ISTANBUL" else "FUND",
        fund_kind=None if source == "BORSA_ISTANBUL" else "YAT",
        isin=None,
        currency="TRY",
        data_source=source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    return asset


def _observation(asset_id: int, *, price: Decimal = Decimal("1234.56789000"), source: str = BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE) -> AssetPriceImportObservation:
    return AssetPriceImportObservation(asset_id=asset_id, price_date=PRICE_DATE, price=price, source=source)


def _prices(db_session: Session) -> list[AssetPrice]:
    return list(db_session.scalars(select(AssetPrice).order_by(AssetPrice.id)))


def test_missing_observation_inserts_canonical_price(db_session: Session) -> None:
    gold = _asset(db_session, code="GOLD")

    result = AssetPriceImportService(db_session).import_observations([_observation(gold.id)])

    assert result.rows_inserted == 1
    assert result.rows_skipped == 0
    assert _prices(db_session)[0].price == Decimal("1234.56789000")


def test_identical_existing_observation_is_skipped(db_session: Session) -> None:
    gold = _asset(db_session, code="GOLD")
    service = AssetPriceImportService(db_session)
    service.import_observations([_observation(gold.id)])

    result = service.import_observations([_observation(gold.id)])

    assert result.rows_inserted == 0
    assert result.rows_skipped == 1
    assert len(_prices(db_session)) == 1


def test_different_existing_observation_conflicts_and_never_overwrites(db_session: Session) -> None:
    gold = _asset(db_session, code="GOLD")
    service = AssetPriceImportService(db_session)
    service.import_observations([_observation(gold.id)])

    with pytest.raises(AssetPriceImportConflictError, match="EXISTING_OBSERVATION_DIFFERENT_PRICE"):
        service.import_observations([_observation(gold.id, price=Decimal("1235.00000000"))])

    assert _prices(db_session)[0].price == Decimal("1234.56789000")


def test_identical_duplicate_input_is_coalesced_safely(db_session: Session) -> None:
    gold = _asset(db_session, code="GOLD")

    result = AssetPriceImportService(db_session).import_observations([
        _observation(gold.id),
        _observation(gold.id),
    ])

    assert result.rows_inserted == 1
    assert result.rows_skipped == 1
    assert len(_prices(db_session)) == 1


def test_conflicting_duplicate_input_aborts_before_mutation(db_session: Session) -> None:
    gold = _asset(db_session, code="GOLD")

    with pytest.raises(AssetPriceImportConflictError, match="INCOMING_DUPLICATE_DIFFERENT_PRICE"):
        AssetPriceImportService(db_session).import_observations([
            _observation(gold.id),
            _observation(gold.id, price=Decimal("1200.00000000")),
        ])

    assert _prices(db_session) == []


def test_existing_conflict_rolls_back_the_entire_batch(db_session: Session) -> None:
    gold = _asset(db_session, code="GOLD")
    silver = _asset(db_session, code="SILVER")
    service = AssetPriceImportService(db_session)
    service.import_observations([_observation(gold.id)])

    with pytest.raises(AssetPriceImportConflictError):
        service.import_observations([
            _observation(silver.id),
            _observation(gold.id, price=Decimal("1200.00000000")),
        ])

    assert [(row.asset_id, row.price) for row in _prices(db_session)] == [
        (gold.id, Decimal("1234.56789000")),
    ]


def test_asset_date_source_identity_is_respected_and_non_metal_rows_are_untouched(db_session: Session) -> None:
    gold = _asset(db_session, code="GOLD")
    other = _asset(db_session, code="AAA", source="MANUAL")
    db_session.add(AssetPrice(
        asset_id=other.id,
        price_date=PRICE_DATE,
        price=Decimal("99.00000000"),
        source="MANUAL_SOURCE",
    ))
    db_session.commit()

    result = AssetPriceImportService(db_session).import_observations([
        _observation(gold.id),
        _observation(gold.id, source="OTHER_SOURCE"),
        AssetPriceImportObservation(
            asset_id=gold.id,
            price_date=date(2026, 9, 9),
            price=Decimal("1300.00000000"),
            source=BORSA_ISTANBUL_REFERENCE_PRICES_SOURCE,
        ),
    ])

    assert result.rows_inserted == 3
    manual_row = next(row for row in _prices(db_session) if row.asset_id == other.id)
    assert manual_row.price == Decimal("99.00000000")
