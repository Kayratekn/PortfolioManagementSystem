from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_allocation_data_repository import TefasFundAllocationDataRepository
from src.response.tefas_fund_response import (
    TefasFundAllocationItemResponse,
    TefasFundAllocationResponse,
)
from src.services.tefas_portfolio_allocation_mapping import (
    get_allocation_label,
    get_mapping_status,
)


class TefasFundAllocationReadService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        allocation_repository: TefasFundAllocationDataRepository,
    ) -> None:
        self.asset_repository = asset_repository
        self.allocation_repository = allocation_repository

    def get_fund_allocation(
        self,
        *,
        fund_code: str,
        data_date: date,
    ) -> TefasFundAllocationResponse:
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

        allocation_rows = self.allocation_repository.list_by_asset_and_date(
            asset_id=asset.id,
            data_date=data_date,
        )

        return TefasFundAllocationResponse(
            fund_code=asset.asset_code,
            fund_name=asset.asset_name,
            data_date=data_date,
            allocations=[
                self._build_allocation_item(row.raw_field_name, row.allocation_percentage)
                for row in allocation_rows
            ],
        )

    @staticmethod
    def _build_allocation_item(
        raw_field_name: str,
        percentage: Decimal,
    ) -> TefasFundAllocationItemResponse:
        mapping_status = get_mapping_status(raw_field_name)
        label = get_allocation_label(raw_field_name)

        return TefasFundAllocationItemResponse(
            label=label,
            raw_field_name=None if mapping_status == "VERIFIED" else raw_field_name,
            percentage=percentage,
            mapping_status=mapping_status,
        )
