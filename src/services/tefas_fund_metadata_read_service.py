from __future__ import annotations

from fastapi import HTTPException, status

from src.model.asset import Asset
from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_detail_snapshot_repository import TefasFundDetailSnapshotRepository
from src.response.tefas_fund_metadata_response import TefasFundLatestMetadataResponse


class TefasFundMetadataReadService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        detail_snapshot_repository: TefasFundDetailSnapshotRepository,
    ) -> None:
        self.asset_repository = asset_repository
        self.detail_snapshot_repository = detail_snapshot_repository

    def get_latest_metadata(self, *, fund_code: str) -> TefasFundLatestMetadataResponse:
        asset = self._get_tefas_asset(fund_code)
        snapshot = self.detail_snapshot_repository.get_latest_for_asset(asset.id)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TEFAS fund detail metadata not found.",
            )

        return self._response(asset, snapshot)

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
        snapshot: TefasFundDetailSnapshot,
    ) -> TefasFundLatestMetadataResponse:
        return TefasFundLatestMetadataResponse(
            asset_id=asset.id,
            fund_code=asset.asset_code,
            fund_name=asset.asset_name,
            fund_kind=asset.fund_kind,
            isin=asset.isin,
            currency=asset.currency,
            observed_at=snapshot.observed_at,
            source_page=snapshot.source_page,
            fund_category=snapshot.fund_category,
            category_rank=snapshot.category_rank,
            category_fund_count=snapshot.category_fund_count,
            market_share_raw=snapshot.market_share_raw,
            risk_value=snapshot.risk_value,
            tefas_status=snapshot.tefas_status,
            transaction_start_time=snapshot.transaction_start_time,
            transaction_end_time=snapshot.transaction_end_time,
            entry_commission_raw=snapshot.entry_commission_raw,
            exit_commission_raw=snapshot.exit_commission_raw,
            interest_content=snapshot.interest_content,
            fund_sale_valor=snapshot.fund_sale_valor,
            fund_redemption_valor=snapshot.fund_redemption_valor,
        )