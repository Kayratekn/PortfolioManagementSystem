from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.model.asset import Asset
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository


TEFAS_SOURCE = "TEFAS"
NAV_FUND_KINDS = {"YAT", "EMK", "GYF", "GSYF"}
SUPPORTED_FUND_KINDS = NAV_FUND_KINDS | {"BYF"}


@dataclass(frozen=True)
class TefasValuationPrice:
    price: Decimal
    price_date: date
    price_kind: str
    source: str


class TefasValuationPriceService:
    def __init__(self, daily_data_repository: TefasFundDailyDataRepository) -> None:
        self.daily_data_repository = daily_data_repository

    def get_price(
        self,
        *,
        asset: Asset,
        valuation_date: date,
    ) -> TefasValuationPrice | None:
        if asset.data_source != TEFAS_SOURCE:
            raise ValueError("Only TEFAS assets are supported for TEFAS valuation prices.")
        if asset.fund_kind is None:
            raise ValueError("TEFAS asset fund_kind is required for valuation price selection.")
        if asset.fund_kind not in SUPPORTED_FUND_KINDS:
            raise ValueError(f"Unsupported TEFAS fund_kind for valuation price selection: {asset.fund_kind}")

        daily_data = self.daily_data_repository.get_latest_on_or_before(
            asset_id=asset.id,
            data_date=valuation_date,
        )
        if daily_data is None:
            return None

        if asset.fund_kind == "BYF":
            selected_price = daily_data.exchange_bulletin_price
            price_kind = "EXCHANGE_MARKET"
            if selected_price is None:
                return None
        else:
            selected_price = daily_data.price
            price_kind = "NAV"

        if selected_price <= 0:
            raise ValueError("Selected TEFAS valuation price must be greater than 0.")

        return TefasValuationPrice(
            price=selected_price,
            price_date=daily_data.data_date,
            price_kind=price_kind,
            source=TEFAS_SOURCE,
        )