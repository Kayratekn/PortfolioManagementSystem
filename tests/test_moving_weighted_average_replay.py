from __future__ import annotations

import inspect
from datetime import date
from decimal import Decimal

import pytest

from src.model.transaction import Transaction
from src.services import moving_weighted_average_replay
from src.services.moving_weighted_average_replay import replay_moving_weighted_average


def _transaction(transaction_type: str, quantity: str, unit_price: str) -> Transaction:
    return Transaction(
        id=1,
        portfolio_id=1,
        asset_id=1,
        transaction_type=transaction_type,
        quantity=Decimal(quantity),
        unit_price=Decimal(unit_price),
        transaction_date=date(2026, 8, 25),
    )


def test_empty_replay_starts_with_zero_state() -> None:
    result = replay_moving_weighted_average([])

    assert result.quantity == Decimal("0")
    assert result.total_cost == Decimal("0")
    assert result.average_cost == Decimal("0")
    assert result.sold_quantity == Decimal("0")
    assert result.realized_proceeds == Decimal("0")
    assert result.realized_cost_basis == Decimal("0")
    assert result.native_realized_pl == Decimal("0")


def test_partial_sell_average_unchanged_and_realized_values_accumulate() -> None:
    result = replay_moving_weighted_average(
        [
            _transaction("BUY", "10.00000000", "20.00000000"),
            _transaction("BUY", "10.00000000", "30.00000000"),
            _transaction("SELL", "5.00000000", "40.00000000"),
        ]
    )

    assert result.quantity == Decimal("15.00000000")
    assert result.total_cost == Decimal("375.0000000000000000")
    assert result.average_cost == Decimal("25.00000000")
    assert result.sold_quantity == Decimal("5.00000000")
    assert result.realized_proceeds == Decimal("200.0000000000000000")
    assert result.realized_cost_basis == Decimal("125.0000000000000000")
    assert result.native_realized_pl == Decimal("75.0000000000000000")


def test_full_exit_resets_state_and_later_buy_starts_new_cycle() -> None:
    result = replay_moving_weighted_average(
        [
            _transaction("BUY", "10.00000000", "20.00000000"),
            _transaction("SELL", "10.00000000", "25.00000000"),
            _transaction("BUY", "5.00000000", "30.00000000"),
        ]
    )

    assert result.quantity == Decimal("5.00000000")
    assert result.total_cost == Decimal("150.0000000000000000")
    assert result.average_cost == Decimal("30.00000000")
    assert result.sold_quantity == Decimal("10.00000000")
    assert result.native_realized_pl == Decimal("50.0000000000000000")


def test_precision_preserved_without_internal_rounding() -> None:
    result = replay_moving_weighted_average(
        [
            _transaction("BUY", "1.00000000", "1.00000000"),
            _transaction("BUY", "2.00000000", "2.00000000"),
            _transaction("SELL", "1.00000000", "3.00000000"),
        ]
    )

    assert result.average_cost == Decimal("1.666666666666666666666666667")
    assert result.realized_cost_basis == Decimal("1.666666666666666666666666667")
    assert result.native_realized_pl == Decimal("1.333333333333333333333333333")


def test_historical_oversell_fails() -> None:
    with pytest.raises(ValueError, match="SELL exceeding quantity"):
        replay_moving_weighted_average(
            [_transaction("SELL", "1.00000000", "10.00000000")]
        )


def test_unsupported_transaction_type_fails() -> None:
    with pytest.raises(ValueError, match="Unsupported transaction type"):
        replay_moving_weighted_average(
            [_transaction("DIVIDEND", "1.00000000", "10.00000000")]
        )


def test_replay_module_does_not_use_float_round_or_quantize() -> None:
    source = inspect.getsource(moving_weighted_average_replay)

    assert "float" not in source
    assert "round(" not in source
    assert "quantize" not in source
