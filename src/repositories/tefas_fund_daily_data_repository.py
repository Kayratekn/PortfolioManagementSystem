from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.model.tefas_fund_daily_data import TefasFundDailyData


class TefasFundDailyDataRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_asset_and_date(
        self,
        *,
        asset_id: int,
        data_date: date,
    ) -> TefasFundDailyData | None:
        statement = select(TefasFundDailyData).where(
            TefasFundDailyData.asset_id == asset_id,
            TefasFundDailyData.data_date == data_date,
        )
        return self.db.scalar(statement)

    def add(self, daily_data: TefasFundDailyData) -> TefasFundDailyData:
        self.db.add(daily_data)
        self.db.flush()
        return daily_data
