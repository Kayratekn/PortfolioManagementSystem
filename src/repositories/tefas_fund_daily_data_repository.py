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

    def get_latest_before(
        self,
        *,
        asset_id: int,
        data_date: date,
    ) -> TefasFundDailyData | None:
        statement = (
            select(TefasFundDailyData)
            .where(
                TefasFundDailyData.asset_id == asset_id,
                TefasFundDailyData.data_date < data_date,
            )
            .order_by(TefasFundDailyData.data_date.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def get_latest_on_or_before(
        self,
        *,
        asset_id: int,
        data_date: date,
    ) -> TefasFundDailyData | None:
        statement = (
            select(TefasFundDailyData)
            .where(
                TefasFundDailyData.asset_id == asset_id,
                TefasFundDailyData.data_date <= data_date,
            )
            .order_by(TefasFundDailyData.data_date.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def list_latest_before(
        self,
        *,
        asset_id: int,
        data_date: date,
        limit: int,
    ) -> list[TefasFundDailyData]:
        if limit <= 0:
            return []

        statement = (
            select(TefasFundDailyData)
            .where(
                TefasFundDailyData.asset_id == asset_id,
                TefasFundDailyData.data_date < data_date,
            )
            .order_by(TefasFundDailyData.data_date.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def list_latest_on_or_before(
        self,
        *,
        asset_id: int,
        data_date: date,
        limit: int,
    ) -> list[TefasFundDailyData]:
        if limit <= 0:
            return []

        statement = (
            select(TefasFundDailyData)
            .where(
                TefasFundDailyData.asset_id == asset_id,
                TefasFundDailyData.data_date <= data_date,
            )
            .order_by(TefasFundDailyData.data_date.desc(), TefasFundDailyData.id.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement))
    def get_latest_by_asset(self, *, asset_id: int) -> TefasFundDailyData | None:
        statement = (
            select(TefasFundDailyData)
            .where(TefasFundDailyData.asset_id == asset_id)
            .order_by(TefasFundDailyData.data_date.desc(), TefasFundDailyData.id.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def list_by_asset_between(
        self,
        *,
        asset_id: int,
        start_date: date,
        end_date: date,
    ) -> list[TefasFundDailyData]:
        statement = (
            select(TefasFundDailyData)
            .where(
                TefasFundDailyData.asset_id == asset_id,
                TefasFundDailyData.data_date >= start_date,
                TefasFundDailyData.data_date <= end_date,
            )
            .order_by(TefasFundDailyData.data_date.asc(), TefasFundDailyData.id.asc())
        )
        return list(self.db.scalars(statement))

    def add(self, daily_data: TefasFundDailyData) -> TefasFundDailyData:
        self.db.add(daily_data)
        self.db.flush()
        return daily_data
