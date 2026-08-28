from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from src.model.asset import Asset
from src.model.user import User
from src.repositories.transaction_repository import TransactionRepository
from src.services.cost_basis_service import CostBasisService, CostBasisItem
from src.services.tefas_valuation_price_service import TefasValuationPriceService


ITEM_STATUS_COMPLETE = "COMPLETE"
ITEM_STATUS_UNAVAILABLE = "UNAVAILABLE"
RESULT_STATUS_COMPLETE = "COMPLETE"
RESULT_STATUS_INCOMPLETE = "INCOMPLETE"

REASON_PRICE_UNAVAILABLE = "PRICE_UNAVAILABLE"
REASON_ASSET_CURRENCY_UNAVAILABLE = "ASSET_CURRENCY_UNAVAILABLE"
REASON_UNSUPPORTED_ASSET = "UNSUPPORTED_ASSET"

TEFAS_SOURCE = "TEFAS"
SUPPORTED_ASSET_TYPE = "FUND"
SUPPORTED_TEFAS_FUND_KINDS = {"YAT", "EMK", "BYF", "GYF", "GSYF"}


@dataclass(frozen=True)
class UnrealizedPlItem:
    asset_id: int
    asset_code: str
    asset_name: str
    asset_currency: str | None
    status: str
    unavailable_reason: str | None
    quantity: Decimal
    total_cost_basis: Decimal | None
    average_cost_per_unit: Decimal | None
    price: Decimal | None
    price_date: date | None
    price_kind: str | None
    price_source: str | None
    native_market_value: Decimal | None
    native_unrealized_pl: Decimal | None


@dataclass(frozen=True)
class UnrealizedPlResult:
    portfolio_id: int
    as_of_date: date
    status: str
    items: tuple[UnrealizedPlItem, ...]


class UnrealizedPlService:
    def __init__(
        self,
        cost_basis_service: CostBasisService,
        transaction_repository: TransactionRepository,
        tefas_valuation_price_service: TefasValuationPriceService,
    ) -> None:
        self.cost_basis_service = cost_basis_service
        self.transaction_repository = transaction_repository
        self.tefas_valuation_price_service = tefas_valuation_price_service

    def get_unrealized_pl(
        self,
        *,
        portfolio_id: int,
        current_user: User,
        as_of_date: date,
    ) -> UnrealizedPlResult:
        cost_basis_result = self.cost_basis_service.get_cost_basis(
            portfolio_id=portfolio_id,
            current_user=current_user,
            as_of_date=as_of_date,
        )
        self._validate_cost_basis_result_header(
            cost_basis_result=cost_basis_result,
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
        )

        holdings = self.transaction_repository.list_holdings_by_portfolio_on_or_before(
            portfolio_id=portfolio_id,
            transaction_date=as_of_date,
        )
        self._validate_unique_cost_basis_asset_ids(cost_basis_result.items)
        cost_basis_by_asset_id = {
            item.asset_id: item for item in cost_basis_result.items
        }
        self._validate_asset_sets(
            holdings=holdings,
            cost_basis_by_asset_id=cost_basis_by_asset_id,
        )

        items = tuple(
            self._build_item(
                asset=asset,
                holding_quantity=holding_quantity,
                cost_basis_item=cost_basis_by_asset_id[asset.id],
                as_of_date=as_of_date,
            )
            for asset, holding_quantity in holdings
        )
        result_status = RESULT_STATUS_COMPLETE
        if any(item.status == ITEM_STATUS_UNAVAILABLE for item in items):
            result_status = RESULT_STATUS_INCOMPLETE

        return UnrealizedPlResult(
            portfolio_id=portfolio_id,
            as_of_date=as_of_date,
            status=result_status,
            items=items,
        )

    def _build_item(
        self,
        *,
        asset: Asset,
        holding_quantity: Decimal,
        cost_basis_item: CostBasisItem,
        as_of_date: date,
    ) -> UnrealizedPlItem:
        if cost_basis_item.quantity != holding_quantity:
            raise ValueError(
                "Cost Basis quantity does not match as-of holding quantity."
            )
        self._validate_cost_basis_item(cost_basis_item)

        if not self._is_supported_tefas_fund(asset):
            return self._unavailable_item(
                asset=asset,
                quantity=holding_quantity,
                cost_basis_item=cost_basis_item,
                unavailable_reason=REASON_UNSUPPORTED_ASSET,
            )

        valuation_price = self.tefas_valuation_price_service.get_price(
            asset=asset,
            valuation_date=as_of_date,
        )
        if valuation_price is None:
            return self._unavailable_item(
                asset=asset,
                quantity=holding_quantity,
                cost_basis_item=cost_basis_item,
                unavailable_reason=REASON_PRICE_UNAVAILABLE,
            )

        if cost_basis_item.status == ITEM_STATUS_UNAVAILABLE:
            if cost_basis_item.unavailable_reason is None:
                raise ValueError("Unavailable Cost Basis item is missing a reason.")
            return self._unavailable_item(
                asset=asset,
                quantity=holding_quantity,
                cost_basis_item=cost_basis_item,
                unavailable_reason=cost_basis_item.unavailable_reason,
                price=valuation_price.price,
                price_date=valuation_price.price_date,
                price_kind=valuation_price.price_kind,
                price_source=valuation_price.source,
            )

        if cost_basis_item.total_cost_basis is None:
            raise ValueError("Complete Cost Basis item is missing total cost basis.")

        native_market_value = holding_quantity * valuation_price.price
        native_unrealized_pl = native_market_value - cost_basis_item.total_cost_basis
        return UnrealizedPlItem(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            asset_currency=asset.currency,
            status=ITEM_STATUS_COMPLETE,
            unavailable_reason=None,
            quantity=holding_quantity,
            total_cost_basis=cost_basis_item.total_cost_basis,
            average_cost_per_unit=cost_basis_item.average_cost_per_unit,
            price=valuation_price.price,
            price_date=valuation_price.price_date,
            price_kind=valuation_price.price_kind,
            price_source=valuation_price.source,
            native_market_value=native_market_value,
            native_unrealized_pl=native_unrealized_pl,
        )

    @staticmethod
    def _validate_cost_basis_result_header(
        *,
        cost_basis_result,
        portfolio_id: int,
        as_of_date: date,
    ) -> None:
        if cost_basis_result.portfolio_id != portfolio_id:
            raise ValueError("Cost Basis result portfolio does not match request.")
        if cost_basis_result.as_of_date != as_of_date:
            raise ValueError("Cost Basis result date does not match request.")

    @staticmethod
    def _validate_asset_sets(
        *,
        holdings: list[tuple[Asset, Decimal]],
        cost_basis_by_asset_id: dict[int, CostBasisItem],
    ) -> None:
        holding_asset_ids = {asset.id for asset, _quantity in holdings}
        cost_basis_asset_ids = set(cost_basis_by_asset_id)
        if holding_asset_ids != cost_basis_asset_ids:
            raise ValueError("Cost Basis asset set does not match as-of holdings.")

    @staticmethod
    def _validate_unique_cost_basis_asset_ids(
        cost_basis_items: tuple[CostBasisItem, ...],
    ) -> None:
        seen_asset_ids: set[int] = set()
        duplicate_asset_ids: set[int] = set()
        for item in cost_basis_items:
            if item.asset_id in seen_asset_ids:
                duplicate_asset_ids.add(item.asset_id)
            seen_asset_ids.add(item.asset_id)
        if duplicate_asset_ids:
            sorted_duplicates = sorted(duplicate_asset_ids)
            raise ValueError(
                f"Duplicate Cost Basis asset IDs in result: {sorted_duplicates}."
            )

    @staticmethod
    def _validate_cost_basis_item(cost_basis_item: CostBasisItem) -> None:
        if cost_basis_item.status == ITEM_STATUS_COMPLETE:
            return
        if cost_basis_item.status == ITEM_STATUS_UNAVAILABLE:
            if cost_basis_item.unavailable_reason is None:
                raise ValueError("Unavailable Cost Basis item is missing a reason.")
            return
        raise ValueError("Unexpected Cost Basis item status.")

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
        cost_basis_item: CostBasisItem,
        unavailable_reason: str,
        price: Decimal | None = None,
        price_date: date | None = None,
        price_kind: str | None = None,
        price_source: str | None = None,
    ) -> UnrealizedPlItem:
        return UnrealizedPlItem(
            asset_id=asset.id,
            asset_code=asset.asset_code,
            asset_name=asset.asset_name,
            asset_currency=asset.currency,
            status=ITEM_STATUS_UNAVAILABLE,
            unavailable_reason=unavailable_reason,
            quantity=quantity,
            total_cost_basis=cost_basis_item.total_cost_basis,
            average_cost_per_unit=cost_basis_item.average_cost_per_unit,
            price=price,
            price_date=price_date,
            price_kind=price_kind,
            price_source=price_source,
            native_market_value=None,
            native_unrealized_pl=None,
        )