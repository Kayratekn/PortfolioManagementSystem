from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from src.integrations.tefas_client import FundKind
from src.model.asset import Asset
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.services.tefas_service import TefasService


@dataclass(frozen=True)
class TefasSyncResult:
    fetched_rows: int
    assets_created: int
    assets_updated: int
    daily_rows_created: int
    daily_rows_updated: int


class TefasSyncService:
    def __init__(
        self,
        db: Session,
        tefas_service: TefasService | None = None,
    ) -> None:
        self.db = db
        self.tefas_service = tefas_service or TefasService()
        self.asset_repository = AssetRepository(db)
        self.daily_data_repository = TefasFundDailyDataRepository(db)

    def sync_general_info(
        self,
        *,
        start_date: date,
        end_date: date,
        fund_kind: FundKind = "YAT",
        fund_code: str | None = None,
    ) -> TefasSyncResult:
        rows = self.tefas_service.fetch_general_info(
            start_date=start_date,
            end_date=end_date,
            fund_kind=fund_kind,
            fund_code=fund_code,
        )

        if not rows:
            return TefasSyncResult(
                fetched_rows=0,
                assets_created=0,
                assets_updated=0,
                daily_rows_created=0,
                daily_rows_updated=0,
            )

        assets_created = 0
        assets_updated = 0
        daily_rows_created = 0
        daily_rows_updated = 0

        try:
            for row in rows:
                asset = self.asset_repository.get_by_source_and_code(
                    data_source="TEFAS",
                    asset_code=row["fund_code"],
                )

                if asset is None:
                    asset = Asset(
                        asset_code=row["fund_code"],
                        asset_name=row["fund_name"],
                        asset_type="FUND",
                        fund_kind=row["fund_kind"],
                        currency=None,
                        data_source="TEFAS",
                        is_active=True,
                    )
                    self.asset_repository.add(asset)
                    assets_created += 1
                else:
                    asset_changed = False
                    if asset.asset_name != row["fund_name"]:
                        asset.asset_name = row["fund_name"]
                        asset_changed = True
                    if asset.asset_type != "FUND":
                        asset.asset_type = "FUND"
                        asset_changed = True
                    if asset.fund_kind != row["fund_kind"]:
                        asset.fund_kind = row["fund_kind"]
                        asset_changed = True
                    if asset.is_active is not True:
                        asset.is_active = True
                        asset_changed = True
                    if asset_changed:
                        assets_updated += 1

                daily_data = self.daily_data_repository.get_by_asset_and_date(
                    asset_id=asset.id,
                    data_date=row["data_date"],
                )

                if daily_data is None:
                    daily_data = TefasFundDailyData(
                        asset_id=asset.id,
                        data_date=row["data_date"],
                        price=row["price"],
                        shares_outstanding=row["shares_outstanding"],
                        investor_count=row["investor_count"],
                        portfolio_size=row["portfolio_size"],
                        exchange_bulletin_price=row["exchange_bulletin_price"],
                    )
                    self.daily_data_repository.add(daily_data)
                    daily_rows_created += 1
                else:
                    daily_data_changed = False
                    if daily_data.price != row["price"]:
                        daily_data.price = row["price"]
                        daily_data_changed = True
                    if daily_data.shares_outstanding != row["shares_outstanding"]:
                        daily_data.shares_outstanding = row["shares_outstanding"]
                        daily_data_changed = True
                    if daily_data.investor_count != row["investor_count"]:
                        daily_data.investor_count = row["investor_count"]
                        daily_data_changed = True
                    if daily_data.portfolio_size != row["portfolio_size"]:
                        daily_data.portfolio_size = row["portfolio_size"]
                        daily_data_changed = True
                    if daily_data.exchange_bulletin_price != row["exchange_bulletin_price"]:
                        daily_data.exchange_bulletin_price = row["exchange_bulletin_price"]
                        daily_data_changed = True
                    if daily_data_changed:
                        daily_rows_updated += 1

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return TefasSyncResult(
            fetched_rows=len(rows),
            assets_created=assets_created,
            assets_updated=assets_updated,
            daily_rows_created=daily_rows_created,
            daily_rows_updated=daily_rows_updated,
        )
