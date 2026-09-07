from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status

from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.response.tefas_fund_daily_data_response import (
    TefasFundDailyHistoryResponse,
    TefasFundDailyLatestResponse,
    TefasFundDailyObservationResponse,
)


class TefasFundDailyReadService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        daily_data_repository: TefasFundDailyDataRepository,
    ) -> None:
        self.asset_repository = asset_repository
        self.daily_data_repository = daily_data_repository

    def get_latest(self, *, fund_code: str) -> TefasFundDailyLatestResponse:
        asset = self._get_tefas_asset(fund_code)
        row = self.daily_data_repository.get_latest_by_asset(asset_id=asset.id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS fund daily data not found.",
            )

        return TefasFundDailyLatestResponse(
            asset_id=asset.id,
            fund_code=asset.asset_code,
            fund_name=asset.asset_name,
            fund_kind=asset.fund_kind,
            currency=asset.currency,
            observation=self._observation(row),
        )

    def get_history(
        self,
        *,
        fund_code: str,
        start_date: date,
        end_date: date,
    ) -> TefasFundDailyHistoryResponse:
        if start_date > end_date:
            raise HTTPException(
                status_code=422,
                detail="start_date must be before or equal to end_date.",
            )

        asset = self._get_tefas_asset(fund_code)
        rows = self.daily_data_repository.list_by_asset_between(
            asset_id=asset.id,
            start_date=start_date,
            end_date=end_date,
        )

        return TefasFundDailyHistoryResponse(
            asset_id=asset.id,
            fund_code=asset.asset_code,
            fund_name=asset.asset_name,
            fund_kind=asset.fund_kind,
            currency=asset.currency,
            items=[self._observation(row) for row in rows],
            total=len(rows),
        )

    def _get_tefas_asset(self, fund_code: str) -> Asset:
        normalized_fund_code = fund_code.strip().upper()
        if not normalized_fund_code:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS fund not found.",
            )

        asset = self.asset_repository.get_by_source_and_code(
            data_source="TEFAS",
            asset_code=normalized_fund_code,
        )
        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS fund not found.",
            )
        return asset

    @staticmethod
    def _observation(row: TefasFundDailyData) -> TefasFundDailyObservationResponse:
        return TefasFundDailyObservationResponse(
            data_date=row.data_date,
            price=row.price,
            exchange_bulletin_price=row.exchange_bulletin_price,
            shares_outstanding=row.shares_outstanding,
            investor_count=row.investor_count,
            portfolio_size=row.portfolio_size,
        )