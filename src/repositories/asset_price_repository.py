from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.asset_price import AssetPrice


class AssetPriceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, asset_price: AssetPrice) -> AssetPrice:
        self.db.add(asset_price)
        self.db.flush()
        return asset_price

    def get_by_asset_date_source(
        self,
        *,
        asset_id: int,
        price_date: date,
        source: str,
    ) -> AssetPrice | None:
        statement = select(AssetPrice).where(
            AssetPrice.asset_id == asset_id,
            AssetPrice.price_date == price_date,
            AssetPrice.source == source,
        )
        return self.db.scalar(statement)

    def get_latest_on_or_before(
        self,
        *,
        asset_id: int,
        price_date: date,
        source: str,
    ) -> AssetPrice | None:
        statement = (
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
                AssetPrice.source == source,
                AssetPrice.price_date <= price_date,
            )
            .order_by(AssetPrice.price_date.desc(), AssetPrice.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def list_by_asset_between(
        self,
        *,
        asset_id: int,
        start_date: date,
        end_date: date,
        source: str,
    ) -> list[AssetPrice]:
        statement = (
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
                AssetPrice.source == source,
                AssetPrice.price_date >= start_date,
                AssetPrice.price_date <= end_date,
            )
            .order_by(AssetPrice.price_date.asc(), AssetPrice.id.asc())
        )
        return list(self.db.scalars(statement))

    def get_latest_by_asset(self, *, asset_id: int, source: str) -> AssetPrice | None:
        statement = (
            select(AssetPrice)
            .where(
                AssetPrice.asset_id == asset_id,
                AssetPrice.source == source,
            )
            .order_by(AssetPrice.price_date.desc(), AssetPrice.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)