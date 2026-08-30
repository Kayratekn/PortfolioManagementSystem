from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from src.model.transaction import Transaction


@dataclass(frozen=True)
class MovingWeightedAverageReplayResult:
    quantity: Decimal
    total_cost: Decimal
    average_cost: Decimal
    sold_quantity: Decimal
    realized_proceeds: Decimal
    realized_cost_basis: Decimal
    native_realized_pl: Decimal


def replay_moving_weighted_average(
    transactions: list[Transaction],
) -> MovingWeightedAverageReplayResult:
    quantity = Decimal("0")
    total_cost = Decimal("0")
    average_cost = Decimal("0")
    sold_quantity = Decimal("0")
    realized_proceeds = Decimal("0")
    realized_cost_basis = Decimal("0")
    native_realized_pl = Decimal("0")

    for transaction in transactions:
        if transaction.transaction_type == "BUY":
            buy_cost = transaction.quantity * transaction.unit_price
            total_cost = total_cost + buy_cost
            quantity = quantity + transaction.quantity
            average_cost = total_cost / quantity
        elif transaction.transaction_type == "SELL":
            if transaction.quantity > quantity:
                raise ValueError(
                    "Moving weighted average replay encountered a SELL "
                    "exceeding quantity."
                )
            sell_proceeds = transaction.quantity * transaction.unit_price
            cost_removed = transaction.quantity * average_cost
            realized_pl_for_sell = sell_proceeds - cost_removed

            sold_quantity = sold_quantity + transaction.quantity
            realized_proceeds = realized_proceeds + sell_proceeds
            realized_cost_basis = realized_cost_basis + cost_removed
            native_realized_pl = native_realized_pl + realized_pl_for_sell

            total_cost = total_cost - cost_removed
            quantity = quantity - transaction.quantity
            if quantity == Decimal("0"):
                quantity = Decimal("0")
                total_cost = Decimal("0")
                average_cost = Decimal("0")
        else:
            raise ValueError(
                "Unsupported transaction type for moving weighted average replay."
            )

    return MovingWeightedAverageReplayResult(
        quantity=quantity,
        total_cost=total_cost,
        average_cost=average_cost,
        sold_quantity=sold_quantity,
        realized_proceeds=realized_proceeds,
        realized_cost_basis=realized_cost_basis,
        native_realized_pl=native_realized_pl,
    )
