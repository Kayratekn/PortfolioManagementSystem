from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.model.tefas_fund_allocation_data import TefasFundAllocationData


@dataclass(frozen=True)
class TefasFundAllocationRowCreate:
    asset_id: int
    data_date: date
    raw_field_name: str
    allocation_percentage: Decimal


class TefasFundAllocationDataRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_asset_and_date(
        self,
        *,
        asset_id: int,
        data_date: date,
    ) -> list[TefasFundAllocationData]:
        statement = (
            select(TefasFundAllocationData)
            .where(
                TefasFundAllocationData.asset_id == asset_id,
                TefasFundAllocationData.data_date == data_date,
            )
            .order_by(TefasFundAllocationData.raw_field_name)
        )
        return list(self.db.scalars(statement))

    def delete_by_asset_and_date(
        self,
        *,
        asset_id: int,
        data_date: date,
    ) -> int:
        statement = delete(TefasFundAllocationData).where(
            TefasFundAllocationData.asset_id == asset_id,
            TefasFundAllocationData.data_date == data_date,
        )
        result = self.db.execute(statement)
        return int(result.rowcount or 0)

    def add_allocation_rows(
        self,
        rows: list[TefasFundAllocationRowCreate],
    ) -> list[TefasFundAllocationData]:
        persisted_rows: list[TefasFundAllocationData] = []
        for row in rows:
            allocation_row = TefasFundAllocationData(
                asset_id=row.asset_id,
                data_date=row.data_date,
                raw_field_name=row.raw_field_name,
                allocation_percentage=row.allocation_percentage,
            )
            self.db.add(allocation_row)
            persisted_rows.append(allocation_row)

        self.db.flush()
        return persisted_rows

    def replace_for_asset_and_date(
        self,
        *,
        asset_id: int,
        data_date: date,
        rows: list[TefasFundAllocationRowCreate],
    ) -> list[TefasFundAllocationData]:
        self.delete_by_asset_and_date(asset_id=asset_id, data_date=data_date)
        return self.add_allocation_rows(rows)
