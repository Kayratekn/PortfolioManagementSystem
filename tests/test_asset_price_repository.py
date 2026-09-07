from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.asset_price import AssetPrice
from src.repositories.asset_price_repository import AssetPriceRepository


def _add_asset(
    db_session: Session,
    *,
    asset_code: str = "XAU_GR",
    data_source: str = "MANUAL",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Asset",
        asset_type="PRECIOUS_METAL",
        fund_kind=None,
        currency="TRY",
        data_source=data_source,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _asset_price(
    *,
    asset_id: int,
    price_date: date,
    price: Decimal = Decimal("100.00000000"),
    source: str = "SOURCE_A",
) -> AssetPrice:
    return AssetPrice(
        asset_id=asset_id,
        price_date=price_date,
        price=price,
        source=source,
    )


def test_asset_price_repository_add_get_exact_and_decimal_persistence(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session)
    repository = AssetPriceRepository(db_session)
    asset_price = _asset_price(
        asset_id=asset.id,
        price_date=date(2026, 9, 7),
        price=Decimal("1234.56789012"),
        source="PROVIDER_A",
    )

    result = repository.add(asset_price)

    assert result is asset_price
    assert asset_price.id is not None
    assert asset_price.price == Decimal("1234.56789012")
    assert isinstance(asset_price.price, Decimal)
    assert repository.get_by_asset_date_source(
        asset_id=asset.id,
        price_date=date(2026, 9, 7),
        source="PROVIDER_A",
    ) is asset_price
    assert repository.get_by_asset_date_source(
        asset_id=asset.id,
        price_date=date(2026, 9, 7),
        source="PROVIDER_B",
    ) is None


def test_latest_on_or_before_ignores_future_rows_within_selected_source(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session)
    repository = AssetPriceRepository(db_session)
    closest_prior = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 6), price=Decimal("106"))
    )
    future = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 8), price=Decimal("108"))
    )

    result = repository.get_latest_on_or_before(
        asset_id=asset.id,
        price_date=date(2026, 9, 7),
        source="SOURCE_A",
    )

    assert result is closest_prior
    assert result is not future


def test_latest_on_or_before_does_not_cross_sources(db_session: Session) -> None:
    asset = _add_asset(db_session)
    repository = AssetPriceRepository(db_session)
    selected_source_price = repository.add(
        _asset_price(
            asset_id=asset.id,
            price_date=date(2026, 9, 5),
            price=Decimal("105"),
            source="SOURCE_A",
        )
    )
    newer_other_source_price = repository.add(
        _asset_price(
            asset_id=asset.id,
            price_date=date(2026, 9, 7),
            price=Decimal("107"),
            source="SOURCE_B",
        )
    )

    result = repository.get_latest_on_or_before(
        asset_id=asset.id,
        price_date=date(2026, 9, 7),
        source="SOURCE_A",
    )

    assert result is selected_source_price
    assert result is not newer_other_source_price


def test_latest_on_or_before_orders_deterministically_within_selected_source(
    db_session: Session,
) -> None:
    asset = _add_asset(db_session)
    repository = AssetPriceRepository(db_session)
    older = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 5), price=Decimal("105"))
    )
    latest = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 7), price=Decimal("107"))
    )

    result = repository.get_latest_on_or_before(
        asset_id=asset.id,
        price_date=date(2026, 9, 7),
        source="SOURCE_A",
    )

    assert latest.id > older.id
    assert result is latest


def test_range_is_inclusive_deterministic_and_source_aware(db_session: Session) -> None:
    asset = _add_asset(db_session)
    other_asset = _add_asset(db_session, asset_code="XAG_GR", data_source="MANUAL")
    repository = AssetPriceRepository(db_session)
    outside_before = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 4), price=Decimal("104"))
    )
    start = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 5), price=Decimal("105"))
    )
    middle = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 6), price=Decimal("106"))
    )
    end = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 7), price=Decimal("107"))
    )
    outside_after = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 8), price=Decimal("108"))
    )
    other_source_row = repository.add(
        _asset_price(
            asset_id=asset.id,
            price_date=date(2026, 9, 6),
            price=Decimal("206"),
            source="SOURCE_B",
        )
    )
    other_asset_row = repository.add(
        _asset_price(asset_id=other_asset.id, price_date=date(2026, 9, 6), price=Decimal("306"))
    )

    result = repository.list_by_asset_between(
        asset_id=asset.id,
        start_date=date(2026, 9, 5),
        end_date=date(2026, 9, 7),
        source="SOURCE_A",
    )

    assert result == [start, middle, end]
    assert outside_before not in result
    assert outside_after not in result
    assert other_source_row not in result
    assert other_asset_row not in result


def test_latest_by_asset_returns_latest_for_selected_source(db_session: Session) -> None:
    asset = _add_asset(db_session)
    other_asset = _add_asset(db_session, asset_code="XAG_GR", data_source="MANUAL")
    repository = AssetPriceRepository(db_session)
    repository.add(_asset_price(asset_id=asset.id, price_date=date(2026, 9, 5)))
    selected_source_latest = repository.add(
        _asset_price(asset_id=asset.id, price_date=date(2026, 9, 7), price=Decimal("107"))
    )
    other_source_later = repository.add(
        _asset_price(
            asset_id=asset.id,
            price_date=date(2026, 9, 8),
            price=Decimal("208"),
            source="SOURCE_B",
        )
    )
    other_asset_latest = repository.add(
        _asset_price(asset_id=other_asset.id, price_date=date(2026, 9, 9), price=Decimal("309"))
    )

    result = repository.get_latest_by_asset(asset_id=asset.id, source="SOURCE_A")

    assert result is selected_source_latest
    assert result is not other_source_later
    assert result is not other_asset_latest


def test_asset_price_repository_add_flushes_but_does_not_commit(
    db_session: Session,
    monkeypatch,
) -> None:
    asset = _add_asset(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)
    asset_price = _asset_price(asset_id=asset.id, price_date=date(2026, 9, 7))

    created = AssetPriceRepository(db_session).add(asset_price)

    assert created.id is not None
    assert commit_calls == 0