from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.asset_price import AssetPrice
from src.model.exchange_rate import ExchangeRate
from src.model.portfolio import Portfolio
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.asset_price_repository import AssetPriceRepository
from src.repositories.exchange_rate_repository import ExchangeRateRepository
from src.repositories.portfolio_cash_flow_repository import PortfolioCashFlowRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.cost_basis_service import CostBasisService
from src.services.fx_conversion_service import FxConversionService
from src.services.portfolio_cash_replay_service import PortfolioCashReplayService
from src.services.portfolio_performance_service import PortfolioPerformanceService
from src.services.portfolio_valuation_service import PortfolioValuationService
from src.services.precious_metal_catalog_bootstrap_service import PreciousMetalCatalogBootstrapService
from src.services.realized_pl_service import RealizedPlService
from src.services.tefas_valuation_price_service import TefasValuationPriceService
from src.services.unrealized_pl_service import UnrealizedPlService
from src.services.valuation_price_service import ValuationPriceService


AS_OF = date(2026, 9, 7)
PRICE_SOURCE = "BORSA_ISTANBUL_REFERENCE_PRICES"


def _user(db: Session, *, email: str = "metal@example.com") -> User:
    user = User(email=email, username=email.split("@")[0], hashed_password="x", preferred_currency="TRY", is_active=True)
    db.add(user); db.flush(); return user


def _portfolio(db: Session, user: User, *, base_currency: str = "TRY") -> Portfolio:
    portfolio = Portfolio(user_id=user.id, name="Metal Portfolio", base_currency=base_currency)
    db.add(portfolio); db.flush(); return portfolio


def _tx(db: Session, portfolio: Portfolio, asset: Asset, *, kind: str = "BUY", quantity: Decimal = Decimal("2.5"), unit_price: Decimal = Decimal("6000"), day: date = date(2026,9,4)) -> None:
    db.add(Transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type=kind, quantity=quantity, unit_price=unit_price, transaction_currency="TRY", transaction_date=day)); db.flush()


def _price(db: Session, asset: Asset, *, value: Decimal, day: date, source: str = PRICE_SOURCE) -> None:
    db.add(AssetPrice(asset_id=asset.id, price_date=day, price=value, source=source)); db.flush()


def _service_bundle(db: Session):
    portfolio_repo = PortfolioRepository(db)
    transaction_repo = TransactionRepository(db)
    valuation_prices = ValuationPriceService(TefasValuationPriceService(TefasFundDailyDataRepository(db)), AssetPriceRepository(db))
    valuation = PortfolioValuationService(
        portfolio_repository=portfolio_repo,
        transaction_repository=transaction_repo,
        tefas_valuation_price_service=valuation_prices,
        fx_conversion_service=FxConversionService(ExchangeRateRepository(db)),
        portfolio_cash_replay_service=PortfolioCashReplayService(portfolio_repo, PortfolioCashFlowRepository(db), transaction_repo),
    )
    cost_basis = CostBasisService(portfolio_repo, transaction_repo)
    unrealized = UnrealizedPlService(cost_basis, transaction_repo, valuation_prices)
    realized = RealizedPlService(portfolio_repo, transaction_repo)
    performance = PortfolioPerformanceService(portfolio_repo, PortfolioCashFlowRepository(db), FxConversionService(ExchangeRateRepository(db)), valuation)
    return valuation, unrealized, cost_basis, realized, performance


def _metals(db: Session) -> dict[str, Asset]:
    PreciousMetalCatalogBootstrapService(db).bootstrap()
    return {asset.asset_code: asset for asset in db.query(Asset).filter_by(data_source="BORSA_ISTANBUL")}


def test_all_canonical_metals_select_only_bist_source_and_never_future_price(db_session: Session):
    metals = _metals(db_session)
    selector = ValuationPriceService(TefasValuationPriceService(TefasFundDailyDataRepository(db_session)), AssetPriceRepository(db_session))
    for code, value in {"GOLD": Decimal("6830.29691"), "SILVER": Decimal("101.25"), "PLATINUM": Decimal("2800")}.items():
        _price(db_session, metals[code], value=value, day=date(2026,9,4))
        _price(db_session, metals[code], value=Decimal("9999"), day=AS_OF, source="WRONG_SOURCE")
        _price(db_session, metals[code], value=Decimal("7777"), day=date(2026,9,8))
        selected = selector.get_price(asset=metals[code], valuation_date=AS_OF)
        assert selected is not None
        assert selected.price == value
        assert selected.price_date == date(2026,9,4)
        assert selected.source == PRICE_SOURCE
        assert selected.price_kind == "REFERENCE_PRICE"


def test_current_valuation_uses_exact_grams_try_per_gram_freshness_and_fx(db_session: Session):
    gold = _metals(db_session)["GOLD"]
    user = _user(db_session); portfolio = _portfolio(db_session, user)
    _tx(db_session, portfolio, gold, quantity=Decimal("2.5"), unit_price=Decimal("6000"))
    _price(db_session, gold, value=Decimal("6830.29691"), day=AS_OF)
    valuation, _, _, _, _ = _service_bundle(db_session)
    result = valuation.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=AS_OF)
    item = result.items[0]
    expected = Decimal("2.5") * Decimal("6830.29691")
    assert item.status == "COMPLETE" and item.price_freshness.status.value == "CURRENT"
    assert item.native_market_value == expected and item.market_value == expected
    assert item.fx_source == "IDENTITY" and item.price_source == PRICE_SOURCE

    usd_portfolio = _portfolio(db_session, user, base_currency="USD")
    _tx(db_session, usd_portfolio, gold, quantity=Decimal("2.5"), unit_price=Decimal("6000"))
    db_session.add(ExchangeRate(base_currency="USD", quote_currency="TRY", rate_date=AS_OF, forex_buying=Decimal("39"), forex_selling=Decimal("41"), source="TCMB")); db_session.flush()
    converted = valuation.get_valuation(portfolio_id=usd_portfolio.id, current_user=user, valuation_date=AS_OF).items[0]
    assert converted.market_value == expected / Decimal("40")
    assert converted.fx_rate_date == AS_OF


def test_mixed_tefas_metal_and_unrealized_pl_share_selector_semantics(db_session: Session):
    gold = _metals(db_session)["GOLD"]
    user = _user(db_session); portfolio = _portfolio(db_session, user)
    _tx(db_session, portfolio, gold, quantity=Decimal("2.5"), unit_price=Decimal("6000"))
    _price(db_session, gold, value=Decimal("6830.29691"), day=date(2026,9,4))
    tefas = Asset(asset_code="TFS", asset_name="Tefas", asset_type="FUND", fund_kind="YAT", currency="TRY", data_source="TEFAS", is_active=True)
    db_session.add(tefas); db_session.flush(); _tx(db_session, portfolio, tefas, quantity=Decimal("2"), unit_price=Decimal("10"))
    db_session.add(TefasFundDailyData(asset_id=tefas.id, data_date=AS_OF, price=Decimal("12"), shares_outstanding=Decimal("1"), investor_count=1, portfolio_size=Decimal("1"))); db_session.flush()
    valuation, unrealized, _, _, _ = _service_bundle(db_session)
    valuation_result = valuation.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=AS_OF)
    assert valuation_result.status == "COMPLETE"
    assert {item.asset_code for item in valuation_result.items} == {"GOLD", "TFS"}
    metal_item = next(item for item in valuation_result.items if item.asset_code == "GOLD")
    assert metal_item.price_date == date(2026,9,4) and metal_item.price_freshness.status.value == "STALE"
    pl_item = next(item for item in unrealized.get_unrealized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF).items if item.asset_code == "GOLD")
    assert pl_item.status == "COMPLETE"
    assert pl_item.native_market_value == Decimal("2.5") * Decimal("6830.29691")
    assert pl_item.native_unrealized_pl == (Decimal("2.5") * Decimal("6830.29691")) - Decimal("15000")


def test_historical_performance_cost_basis_and_realized_pl_use_gram_quantities_without_formula_change(db_session: Session):
    gold = _metals(db_session)["GOLD"]
    user = _user(db_session); portfolio = _portfolio(db_session, user)
    _tx(db_session, portfolio, gold, quantity=Decimal("3"), unit_price=Decimal("6000"), day=date(2026,9,4))
    _price(db_session, gold, value=Decimal("6830.29691"), day=date(2026,9,4))
    _price(db_session, gold, value=Decimal("7000"), day=date(2026,9,8))
    valuation, _, cost_basis, realized, performance = _service_bundle(db_session)
    historical = valuation.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=AS_OF)
    assert historical.items[0].price == Decimal("6830.29691")
    assert historical.items[0].price_date == date(2026,9,4)
    performance_result = performance.get_performance(portfolio_id=portfolio.id, current_user=user, start_date=date(2026,9,6), end_date=AS_OF)
    assert performance_result.status == "COMPLETE"
    assert all(point.status == "COMPLETE" for point in performance_result.points)
    _tx(db_session, portfolio, gold, kind="SELL", quantity=Decimal("1"), unit_price=Decimal("7000"), day=AS_OF)
    basis_item = cost_basis.get_cost_basis(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF).items[0]
    realized_item = realized.get_realized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF).items[0]
    assert basis_item.quantity == Decimal("2") and basis_item.total_cost_basis == Decimal("12000")
    assert realized_item.realized_proceeds == Decimal("7000")
    assert realized_item.realized_cost_basis == Decimal("6000")
    assert realized_item.native_realized_pl == Decimal("1000")

def test_wrong_source_or_future_only_metal_price_is_unavailable_for_valuation_and_unrealized_pl(db_session: Session):
    gold = _metals(db_session)["GOLD"]
    user = _user(db_session); portfolio = _portfolio(db_session, user)
    _tx(db_session, portfolio, gold, quantity=Decimal("1"), unit_price=Decimal("6000"))
    _price(db_session, gold, value=Decimal("9000"), day=AS_OF, source="WRONG_SOURCE")
    _price(db_session, gold, value=Decimal("9000"), day=date(2026,9,8))
    valuation, unrealized, _, _, _ = _service_bundle(db_session)
    valuation_item = valuation.get_valuation(portfolio_id=portfolio.id, current_user=user, valuation_date=AS_OF).items[0]
    pl_item = unrealized.get_unrealized_pl(portfolio_id=portfolio.id, current_user=user, as_of_date=AS_OF).items[0]
    assert valuation_item.status == "UNAVAILABLE" and valuation_item.unavailable_reason == "PRICE_UNAVAILABLE"
    assert pl_item.status == "UNAVAILABLE" and pl_item.unavailable_reason == "PRICE_UNAVAILABLE"