from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status

from src.model.asset import Asset
from src.model.user import User
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.fx_conversion_service import FxConversionService
from src.services.market_data_freshness import (
    MarketDataFreshness,
    not_applicable_market_data_freshness,
    observed_market_data_freshness,
    unavailable_market_data_freshness,
)
from src.services.tefas_valuation_price_service import TefasValuationPriceService


ITEM_STATUS_COMPLETE = "COMPLETE"
ITEM_STATUS_UNAVAILABLE = "UNAVAILABLE"
PORTFOLIO_STATUS_COMPLETE = "COMPLETE"
PORTFOLIO_STATUS_INCOMPLETE = "INCOMPLETE"

REASON_PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
REASON_ASSET_CURRENCY_UNAVAILABLE = "ASSET_CURRENCY_UNAVAILABLE"
REASON_FX_UNAVAILABLE = "FX_UNAVAILABLE"
REASON_UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"

TEFAS_SOURCE = "TEFAS"
SUPPORTED_ASSET_TYPE = "FUND"
SUPPORTED_TEFAS_FUND_KINDS = {"YAT", "EMK", "BYF", "GYF", "GSYF"}


@dataclass(frozen=True)
class PortfolioValuationItem:
    asset_id: int
    asset_code: str
    asset_name: str
    quantity: Decimal
    asset_currency: str | None
    status: str
    unavailable_reason: str | None
    price: Decimal | None
    price_date: date | None
    price_freshness: MarketDataFreshness
    price_kind: str | None
    price_source: str | None
    fx_rate: Decimal | None
    fx_rate_date: date | None
    fx_freshness: MarketDataFreshness
    fx_rate_kind: str | None
    fx_source: str | None
    native_market_value: Decimal | None
    market_value: Decimal | None
    weight: Decimal | None


@dataclass(frozen=True)
class PortfolioValuationResult:
    portfolio_id: int
    base_currency: str
    valuation_date: date
    status: str
    total_market_value: Decimal | None
    items: tuple[PortfolioValuationItem, ...]


class PortfolioValuationService:
    def __init__(
        self,
        portfolio_repository: PortfolioRepository,
        transaction_repository: TransactionRepository,
        tefas_valuation_price_service: TefasValuationPriceService,
        fx_conversion_service: FxConversionService,
    ) -> None:
        self.portfolio_repository = portfolio_repository
        self.transaction_repository = transaction_repository
        self.tefas_valuation_price_service = tefas_valuation_price_service
        self.fx_conversion_service = fx_conversion_service

    def get_valuation(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        valuation_date: date,
    ) -> PortfolioValuationResult:
        portfolio = self.portfolio_repository.get_by_id_for_user(
            portfolio_id,
            current_user.id,
        )
        if portfolio is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio not found.",
            )

        holdings = self.transaction_repository.list_holdings_by_portfolio_on_or_before(
            portfolio_id=portfolio_id,
            transaction_date=valuation_date,
        )
        if not holdings:
            return PortfolioValuationResult(
                portfolio_id=portfolio_id,
                base_currency=portfolio.base_currency,
                valuation_date=valuation_date,
                status=PORTFOLIO_STATUS_COMPLETE,
                total_market_value=Decimal("0"),
                items=(),
            )

        items = tuple(
            self._build_item(
                asset=asset,
                quantity=quantity,
                base_currency=portfolio.base_currency,
                valuation_date=valuation_date,
            )
            for asset, quantity in holdings
        )
        has_unavailable_item = any(item.status == ITEM_STATUS_UNAVAILABLE for item in items)
        if has_unavailable_item:
            total_market_value = None
            portfolio_status = PORTFOLIO_STATUS_INCOMPLETE
        else:
            total_market_value = sum(
                (item.market_value for item in items),
                Decimal("0"),
            )
            items = tuple(
                replace(item, weight=item.market_value / total_market_value)
                for item in items
            )
            portfolio_status = PORTFOLIO_STATUS_COMPLETE

        return PortfolioValuationResult(
            portfolio_id=portfolio_id,
            base_currency=portfolio.base_currency,
            valuation_date=valuation_date,
            status=portfolio_status,
            total_market_value=total_market_value,
            items=items,
        )

    def _build_item(
        self,
        *,
        asset: Asset,
        quantity: Decimal,
        base_currency: str,
        valuation_date: date,
    ) -> PortfolioValuationItem:
        if not self._is_supported_tefas_fund(asset):
            return self._unavailable_item(
                asset=asset,
                quantity=quantity,
                requested_date=valuation_date,
                unavailable_reason=REASON_UNSUPPORTED_ASSET,
            )

        valuation_price = self.tefas_valuation_price_service.get_price(
            asset=asset,
            valuation_date=valuation_date,
        )
        if valuation_price is None:
            return self._unavailable_item(
                asset=asset,
                quantity=quantity,
                requested_date=valuation_date,
                unavailable_reason=REASON_PRICE_UNAVAILABLE,
            )

        asset_currency = asset.currency
        if asset_currency is None or not asset_currency.strip():
            return self._unavailable_item(
                asset=asset,
                quantity=quantity,
                requested_date=valuation_date,
                unavailable_reason=REASON_ASSET_CURRENCY_UNAVAILABLE,
                price=valuation_price.price,
                price_date=valuation_price.price_date,
                price_kind=valuation_price.price_kind,
                price_source=valuation_price.source,
            )

        native_market_value = quantity * valuation_price.price
        fx_rate = self.fx_conversion_service.get_rate(
            source_currency=asset_currency,
            target_currency=base_currency,
            valuation_date=valuation_date,
        )
        if fx_rate is None:
            return self._unavailable_item(
                asset=asset,
                quantity=quantity,
                requested_date=valuation_date,
                unavailable_reason=REASON_FX_UNAVAILABLE,
                price=valuation_price.price,
                price_date=valuation_price.price_date,
                price_kind=valuation_price.price_kind,
                price_source=valuation_price.source,
                native_market_value=native_market_value,
            )

        market_value = native_market_value * fx_rate.rate
        return PortfolioValuationItem(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            quantity=quantity,
            asset_currency=asset.currency,
            status=ITEM_STATUS_COMPLETE,
            unavailable_reason=None,
            price=valuation_price.price,
            price_date=valuation_price.price_date,
            price_freshness=observed_market_data_freshness(
                requested_date=valuation_date,
                effective_date=valuation_price.price_date,
            ),
            price_kind=valuation_price.price_kind,
            price_source=valuation_price.source,
            fx_rate=fx_rate.rate,
            fx_rate_date=fx_rate.rate_date,
            fx_freshness=(
                not_applicable_market_data_freshness(requested_date=valuation_date)
                if fx_rate.source == "IDENTITY" and fx_rate.rate_kind == "IDENTITY"
                else observed_market_data_freshness(
                    requested_date=valuation_date,
                    effective_date=fx_rate.rate_date,
                )
            ),
            fx_rate_kind=fx_rate.rate_kind,
            fx_source=fx_rate.source,
            native_market_value=native_market_value,
            market_value=market_value,
            weight=None,
        )

    @staticmethod
    def _is_supported_tefas_fund(asset: Asset) -> bool:
        return (
            asset.data_source == TEFAS_SOURCE
            and asset.asset_type == SUPPORTED_ASSET_TYPE
            and asset.fund_kind in SUPPORTED_TEFAS_FUND_KINDS
        )

    @staticmethod
    def _unavailable_item(
        *,
        asset: Asset,
        quantity: Decimal,
        requested_date: date,
        unavailable_reason: str,
        price: Decimal | None = None,
        price_date: date | None = None,
        price_kind: str | None = None,
        price_source: str | None = None,
        native_market_value: Decimal | None = None,
    ) -> PortfolioValuationItem:
        return PortfolioValuationItem(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            quantity=quantity,
            asset_currency=asset.currency,
            status=ITEM_STATUS_UNAVAILABLE,
            unavailable_reason=unavailable_reason,
            price=price,
            price_date=price_date,
            price_freshness=observed_market_data_freshness(
                requested_date=requested_date,
                effective_date=price_date,
            ),
            price_kind=price_kind,
            price_source=price_source,
            fx_rate=None,
            fx_rate_date=None,
            fx_freshness=unavailable_market_data_freshness(
                requested_date=requested_date,
            ),
            fx_rate_kind=None,
            fx_source=None,
            native_market_value=native_market_value,
            market_value=None,
            weight=None,
        )
