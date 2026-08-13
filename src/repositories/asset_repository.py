from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.asset import Asset


class AssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_source_and_code(
        self,
        *,
        data_source: str,
        asset_code: str,
    ) -> Asset | None:
        statement = select(Asset).where(
            Asset.data_source == data_source,
            Asset.asset_code == asset_code,
        )
        return self.db.scalar(statement)

    def list_active_by_data_source(self, data_source: str) -> list[Asset]:
        statement = (
            select(Asset)
            .where(
                Asset.data_source == data_source,
                Asset.is_active.is_(True),
            )
            .order_by(Asset.asset_code.asc())
        )
        return list(self.db.scalars(statement))

    def add(self, asset: Asset) -> Asset:
        self.db.add(asset)
        self.db.flush()
        return asset
