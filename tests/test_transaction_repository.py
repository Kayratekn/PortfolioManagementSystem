from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.portfolio import Portfolio
from src.model.transaction import Transaction
from src.model.user import User
from src.repositories.transaction_repository import TransactionRepository


TRANSACTION_DATE = date(2026, 8, 25)


def _create_transaction_parents(db_session: Session) -> tuple[Portfolio, Asset]:
    user = User(
        email="transaction-repository@example.com",
        username="transaction-repository",
        hashed_password="hashed-password",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    portfolio = Portfolio(
        user_id=user.id,
        name="Transaction Portfolio",
        base_currency="TRY",
    )
    asset = Asset(
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add_all([portfolio, asset])
    db_session.flush()
    return portfolio, asset


def _create_user(db_session: Session, *, email: str, username: str) -> User:
    user = User(
        email=email,
        username=username,
        hashed_password="hashed-password",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _create_portfolio(db_session: Session, *, user_id: int, name: str) -> Portfolio:
    portfolio = Portfolio(
        user_id=user_id,
        name=name,
        base_currency="TRY",
    )
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _create_asset(
    db_session: Session,
    *,
    asset_code: str,
    is_active: bool = True,
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        currency="TRY",
        data_source="TEFAS",
        is_active=is_active,
    )
    db_session.add(asset)
    db_session.flush()
    return asset


def _build_transaction(
    *,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str = "BUY",
    quantity: Decimal = Decimal("12.50000000"),
    unit_price: Decimal = Decimal("34.12345678"),
    transaction_date: date = TRANSACTION_DATE,
    transaction_currency: str | None = None,
) -> Transaction:
    return Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=unit_price,
        transaction_currency=transaction_currency,
        transaction_date=transaction_date,
    )


def test_add_valid_transaction_assigns_id_and_persists_in_current_session(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    transaction = _build_transaction(portfolio_id=portfolio.id, asset_id=asset.id)

    result = repository.add(transaction)

    assert result is transaction
    assert transaction.id is not None
    assert db_session.get(Transaction, transaction.id) is transaction


def test_add_round_trips_decimal_quantity_and_unit_price(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    transaction = _build_transaction(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        quantity=Decimal("1.23456789"),
        unit_price=Decimal("98.76543210"),
    )

    repository.add(transaction)
    db_session.expire_all()
    persisted = db_session.get(Transaction, transaction.id)

    assert persisted is not None
    assert persisted.quantity == Decimal("1.23456789")
    assert persisted.unit_price == Decimal("98.76543210")


def test_add_does_not_call_commit(db_session: Session, monkeypatch) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    transaction = _build_transaction(portfolio_id=portfolio.id, asset_id=asset.id)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    repository.add(transaction)

    assert commit_calls == 0


def test_get_net_quantity_returns_decimal_zero_when_no_transactions(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)

    result = repository.get_net_quantity(portfolio_id=portfolio.id, asset_id=asset.id)

    assert result == Decimal("0")


def test_get_net_quantity_adds_buy_quantities(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("2.25000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("3.75000000"),
        )
    )

    result = repository.get_net_quantity(portfolio_id=portfolio.id, asset_id=asset.id)

    assert result == Decimal("6.00000000")


def test_get_net_quantity_subtracts_sell_quantities(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("10.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("4.12500000"),
        )
    )

    result = repository.get_net_quantity(portfolio_id=portfolio.id, asset_id=asset.id)

    assert result == Decimal("5.87500000")


def test_get_net_quantity_ignores_other_portfolio_transactions(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="other-transaction-repository@example.com",
        username="other-transaction-repository",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="Other Portfolio",
    )
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("5.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=other_portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("7.00000000"),
        )
    )

    result = repository.get_net_quantity(portfolio_id=portfolio.id, asset_id=asset.id)

    assert result == Decimal("5.00000000")


def test_get_net_quantity_ignores_other_asset_transactions(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_asset = _create_asset(db_session, asset_code="BBL")
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("5.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=other_asset.id,
            quantity=Decimal("7.00000000"),
        )
    )

    result = repository.get_net_quantity(portfolio_id=portfolio.id, asset_id=asset.id)

    assert result == Decimal("5.00000000")


def test_get_net_quantity_preserves_decimal_precision(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("1.23456789"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("0.00000001"),
        )
    )

    result = repository.get_net_quantity(portfolio_id=portfolio.id, asset_id=asset.id)

    assert result == Decimal("1.23456788")


def test_list_by_portfolio_and_asset_returns_empty_list_when_no_matches(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)

    result = repository.list_by_portfolio_and_asset(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert result == []


def test_list_by_portfolio_and_asset_returns_only_requested_portfolio_and_asset(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="list-other-transaction-repository@example.com",
        username="list-other-transaction-repository",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="List Other Portfolio",
    )
    other_asset = _create_asset(db_session, asset_code="BBL")
    repository = TransactionRepository(db_session)
    matching = repository.add(
        _build_transaction(portfolio_id=portfolio.id, asset_id=asset.id)
    )
    repository.add(_build_transaction(portfolio_id=other_portfolio.id, asset_id=asset.id))
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=other_asset.id))

    result = repository.list_by_portfolio_and_asset(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert result == [matching]


def test_list_by_portfolio_and_asset_orders_by_transaction_date_ascending(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    later = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 26),
        )
    )
    earlier = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 24),
        )
    )

    result = repository.list_by_portfolio_and_asset(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert result == [earlier, later]


def test_list_by_portfolio_and_asset_orders_same_date_by_id_ascending(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    first = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=TRANSACTION_DATE,
        )
    )
    second = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=TRANSACTION_DATE,
        )
    )

    result = repository.list_by_portfolio_and_asset(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert first.id < second.id
    assert result == [first, second]

def test_list_holdings_by_portfolio_returns_empty_list_when_no_transactions(
    db_session: Session,
) -> None:
    portfolio, _asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert result == []


def test_list_holdings_by_portfolio_returns_buy_only_asset_quantity(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("3.25000000"),
        )
    )

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert result == [(asset, Decimal("3.25000000"))]


def test_list_holdings_by_portfolio_returns_buy_minus_sell_net_quantity(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("10.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("4.12500000"),
        )
    )

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert result == [(asset, Decimal("5.87500000"))]


def test_list_holdings_by_portfolio_aggregates_multiple_assets_independently(
    db_session: Session,
) -> None:
    portfolio, first_asset = _create_transaction_parents(db_session)
    second_asset = _create_asset(db_session, asset_code="BBL")
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=first_asset.id,
            quantity=Decimal("5.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=second_asset.id,
            quantity=Decimal("7.50000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=second_asset.id,
            transaction_type="SELL",
            quantity=Decimal("2.00000000"),
        )
    )

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert result == [
        (first_asset, Decimal("5.00000000")),
        (second_asset, Decimal("5.50000000")),
    ]


def test_list_holdings_by_portfolio_omits_fully_sold_assets(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("5.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("5.00000000"),
        )
    )

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert result == []


def test_list_holdings_by_portfolio_ignores_other_portfolio_transactions(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="holdings-other-portfolio@example.com",
        username="holdings-other-portfolio",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="Holdings Other Portfolio",
    )
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("5.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=other_portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("9.00000000"),
        )
    )

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert result == [(asset, Decimal("5.00000000"))]


def test_list_holdings_by_portfolio_includes_inactive_assets_with_positive_quantity(
    db_session: Session,
) -> None:
    user = _create_user(
        db_session,
        email="inactive-holding@example.com",
        username="inactive-holding",
    )
    portfolio = _create_portfolio(
        db_session,
        user_id=user.id,
        name="Inactive Holding Portfolio",
    )
    asset = _create_asset(db_session, asset_code="INA", is_active=False)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("2.00000000"),
        )
    )

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert result == [(asset, Decimal("2.00000000"))]


def test_list_holdings_by_portfolio_orders_by_asset_id(db_session: Session) -> None:
    portfolio, first_asset = _create_transaction_parents(db_session)
    second_asset = _create_asset(db_session, asset_code="BBL")
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=second_asset.id,
            quantity=Decimal("2.00000000"),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=first_asset.id,
            quantity=Decimal("1.00000000"),
        )
    )

    result = repository.list_holdings_by_portfolio(portfolio_id=portfolio.id)

    assert first_asset.id < second_asset.id
    assert result == [
        (first_asset, Decimal("1.00000000")),
        (second_asset, Decimal("2.00000000")),
    ]


def test_list_holdings_by_portfolio_on_or_before_excludes_future_buy(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("5.00000000"),
            transaction_date=date(2026, 8, 24),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("7.00000000"),
            transaction_date=date(2026, 8, 27),
        )
    )

    result = repository.list_holdings_by_portfolio_on_or_before(
        portfolio_id=portfolio.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == [(asset, Decimal("5.00000000"))]


def test_list_holdings_by_portfolio_on_or_before_excludes_future_sell(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("10.00000000"),
            transaction_date=date(2026, 8, 24),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("4.00000000"),
            transaction_date=date(2026, 8, 27),
        )
    )

    result = repository.list_holdings_by_portfolio_on_or_before(
        portfolio_id=portfolio.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == [(asset, Decimal("10.00000000"))]


def test_list_holdings_by_portfolio_on_or_before_includes_exact_as_of_date(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("5.00000000"),
            transaction_date=date(2026, 8, 24),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("2.00000000"),
            transaction_date=date(2026, 8, 26),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("1.00000000"),
            transaction_date=date(2026, 8, 26),
        )
    )

    result = repository.list_holdings_by_portfolio_on_or_before(
        portfolio_id=portfolio.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == [(asset, Decimal("6.00000000"))]


def test_list_holdings_by_portfolio_on_or_before_omits_fully_sold_asset(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="BUY",
            quantity=Decimal("5.00000000"),
            transaction_date=date(2026, 8, 24),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_type="SELL",
            quantity=Decimal("5.00000000"),
            transaction_date=date(2026, 8, 26),
        )
    )

    result = repository.list_holdings_by_portfolio_on_or_before(
        portfolio_id=portfolio.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == []


def test_list_holdings_by_portfolio_on_or_before_ignores_other_portfolio_transactions(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="as-of-other-portfolio@example.com",
        username="as-of-other-portfolio",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="As Of Other Portfolio",
    )
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("5.00000000"),
            transaction_date=date(2026, 8, 24),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=other_portfolio.id,
            asset_id=asset.id,
            quantity=Decimal("9.00000000"),
            transaction_date=date(2026, 8, 24),
        )
    )

    result = repository.list_holdings_by_portfolio_on_or_before(
        portfolio_id=portfolio.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == [(asset, Decimal("5.00000000"))]

def test_list_by_portfolio_and_asset_on_or_before_excludes_future_transactions(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    included = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 25),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 27),
        )
    )

    result = repository.list_by_portfolio_and_asset_on_or_before(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == [included]


def test_list_by_portfolio_and_asset_on_or_before_includes_exact_requested_date(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    earlier = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 25),
        )
    )
    exact = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 26),
        )
    )

    result = repository.list_by_portfolio_and_asset_on_or_before(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == [earlier, exact]


def test_list_by_portfolio_and_asset_on_or_before_orders_by_date_ascending(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    later = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 26),
        )
    )
    earlier = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 24),
        )
    )

    result = repository.list_by_portfolio_and_asset_on_or_before(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_date=date(2026, 8, 26),
    )

    assert result == [earlier, later]


def test_list_by_portfolio_and_asset_on_or_before_orders_same_date_by_id_ascending(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    first = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=TRANSACTION_DATE,
        )
    )
    second = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=TRANSACTION_DATE,
        )
    )

    result = repository.list_by_portfolio_and_asset_on_or_before(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_date=TRANSACTION_DATE,
    )

    assert first.id < second.id
    assert result == [first, second]


def test_list_by_portfolio_and_asset_on_or_before_isolates_portfolio_and_asset(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="as-of-history-other@example.com",
        username="as-of-history-other",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="As Of History Other Portfolio",
    )
    other_asset = _create_asset(db_session, asset_code="HST")
    repository = TransactionRepository(db_session)
    matching = repository.add(
        _build_transaction(portfolio_id=portfolio.id, asset_id=asset.id)
    )
    repository.add(_build_transaction(portfolio_id=other_portfolio.id, asset_id=asset.id))
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=other_asset.id))

    result = repository.list_by_portfolio_and_asset_on_or_before(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
        transaction_date=TRANSACTION_DATE,
    )

    assert result == [matching]


def test_list_by_portfolio_and_asset_still_includes_future_transactions(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    earlier = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 25),
        )
    )
    future = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 27),
        )
    )

    result = repository.list_by_portfolio_and_asset(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert result == [earlier, future]

def test_list_assets_with_sell_on_or_before_returns_distinct_assets(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="BUY", quantity=Decimal("10.00000000")))
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("2.00000000")))
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("3.00000000")))

    result = repository.list_assets_with_sell_on_or_before(portfolio_id=portfolio.id, transaction_date=TRANSACTION_DATE)

    assert result == [asset]


def test_list_assets_with_sell_on_or_before_excludes_future_sell(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="SELL", transaction_date=date(2026, 8, 27)))

    result = repository.list_assets_with_sell_on_or_before(portfolio_id=portfolio.id, transaction_date=TRANSACTION_DATE)

    assert result == []


def test_list_assets_with_sell_on_or_before_excludes_buy_only_asset(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="BUY"))

    result = repository.list_assets_with_sell_on_or_before(portfolio_id=portfolio.id, transaction_date=TRANSACTION_DATE)

    assert result == []


def test_list_assets_with_sell_on_or_before_includes_fully_sold_asset(db_session: Session) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="BUY", quantity=Decimal("5.00000000")))
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id, transaction_type="SELL", quantity=Decimal("5.00000000")))

    result = repository.list_assets_with_sell_on_or_before(portfolio_id=portfolio.id, transaction_date=TRANSACTION_DATE)

    assert result == [asset]


def test_list_assets_with_sell_on_or_before_orders_by_asset_id(db_session: Session) -> None:
    portfolio, first_asset = _create_transaction_parents(db_session)
    second_asset = _create_asset(db_session, asset_code="BBL")
    repository = TransactionRepository(db_session)
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=second_asset.id, transaction_type="SELL"))
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=first_asset.id, transaction_type="SELL"))

    result = repository.list_assets_with_sell_on_or_before(portfolio_id=portfolio.id, transaction_date=TRANSACTION_DATE)

    assert first_asset.id < second_asset.id
    assert result == [first_asset, second_asset]


def test_list_assets_with_sell_on_or_before_isolates_portfolio(
    db_session: Session,
) -> None:
    portfolio, owned_asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="sell-assets-other-portfolio@example.com",
        username="sell-assets-other-portfolio",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="Sell Assets Other Portfolio",
    )
    other_asset = _create_asset(db_session, asset_code="OTH")
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=owned_asset.id,
            transaction_type="SELL",
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=other_portfolio.id,
            asset_id=other_asset.id,
            transaction_type="SELL",
        )
    )

    result = repository.list_assets_with_sell_on_or_before(
        portfolio_id=portfolio.id,
        transaction_date=TRANSACTION_DATE,
    )

    assert result == [owned_asset]


def test_list_by_portfolio_returns_ordered_paginated_transactions(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="history-other-transaction-repository@example.com",
        username="history-other-transaction-repository",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="History Other Portfolio",
    )
    repository = TransactionRepository(db_session)
    later = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 26),
        )
    )
    first_same_date = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 25),
        )
    )
    second_same_date = repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 25),
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=other_portfolio.id,
            asset_id=asset.id,
            transaction_date=date(2026, 8, 24),
        )
    )

    result = repository.list_by_portfolio(
        portfolio_id=portfolio.id,
        skip=1,
        limit=2,
    )

    assert first_same_date.id < second_same_date.id
    assert result == [second_same_date, later]


def test_count_by_portfolio_counts_only_requested_portfolio(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="count-other-transaction-repository@example.com",
        username="count-other-transaction-repository",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="Count Other Portfolio",
    )
    repository = TransactionRepository(db_session)
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id))
    repository.add(_build_transaction(portfolio_id=portfolio.id, asset_id=asset.id))
    repository.add(
        _build_transaction(portfolio_id=other_portfolio.id, asset_id=asset.id)
    )

    result = repository.count_by_portfolio(portfolio_id=portfolio.id)

    assert result == 2


def test_list_existing_non_null_currencies_ignores_legacy_null_rows(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_currency=None,
        )
    )

    result = repository.list_existing_non_null_currencies(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert result == []


def test_list_existing_non_null_currencies_returns_distinct_ordered_values(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_currency="USD",
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_currency="TRY",
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_currency="USD",
        )
    )

    result = repository.list_existing_non_null_currencies(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert result == ["TRY", "USD"]


def test_list_existing_non_null_currencies_isolates_portfolio_and_asset(
    db_session: Session,
) -> None:
    portfolio, asset = _create_transaction_parents(db_session)
    other_user = _create_user(
        db_session,
        email="currency-other-transaction-repository@example.com",
        username="currency-other-transaction-repository",
    )
    other_portfolio = _create_portfolio(
        db_session,
        user_id=other_user.id,
        name="Currency Other Portfolio",
    )
    other_asset = _create_asset(db_session, asset_code="CUR")
    repository = TransactionRepository(db_session)
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=asset.id,
            transaction_currency="TRY",
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=other_portfolio.id,
            asset_id=asset.id,
            transaction_currency="USD",
        )
    )
    repository.add(
        _build_transaction(
            portfolio_id=portfolio.id,
            asset_id=other_asset.id,
            transaction_currency="EUR",
        )
    )

    result = repository.list_existing_non_null_currencies(
        portfolio_id=portfolio.id,
        asset_id=asset.id,
    )

    assert result == ["TRY"]
