from __future__ import annotations

from fastapi import HTTPException, status

from src.model.asset import Asset
from src.model.tefas_management_fee_history import TefasManagementFeeHistory
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_management_fee_history_repository import TefasManagementFeeHistoryRepository
from src.response.tefas_management_fee_response import TefasFundCurrentManagementFeeResponse


_SUPPORTED_MANAGEMENT_FEE_FUND_KINDS = {"YAT", "EMK"}


class TefasManagementFeeReadService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        management_fee_history_repository: TefasManagementFeeHistoryRepository,
    ) -> None:
        self.asset_repository = asset_repository
        self.management_fee_history_repository = management_fee_history_repository

    def get_current_management_fee(
        self,
        *,
        fund_code: str,
    ) -> TefasFundCurrentManagementFeeResponse:
        asset = self._get_tefas_asset(fund_code)
        if asset.fund_kind not in _SUPPORTED_MANAGEMENT_FEE_FUND_KINDS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS management fee not found.",
            )

        history = self.management_fee_history_repository.get_current_for_asset(
            asset_id=asset.id,
        )
        if history is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS management fee not found.",
            )

        return self._response(asset, history)

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
    def _response(
        asset: Asset,
        history: TefasManagementFeeHistory,
    ) -> TefasFundCurrentManagementFeeResponse:
        return TefasFundCurrentManagementFeeResponse(
            asset_id=asset.id,
            fund_code=asset.asset_code,
            fund_name=asset.asset_name,
            fund_kind=asset.fund_kind,
            management_fee_percentage=history.management_fee_percentage,
            first_observed_at=history.first_observed_at,
            last_observed_at=history.last_observed_at,
            source_endpoint=history.source_endpoint,
            source_field_name=history.source_field_name,
        )