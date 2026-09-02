from __future__ import annotations

from sqlalchemy import CheckConstraint

from src.model.transaction import Transaction


def test_transaction_model_defines_nullable_currency_constraint() -> None:
    constraints = {
        constraint.name
        for constraint in Transaction.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert "ck_transactions_transaction_currency_allowed" in constraints
    assert Transaction.__table__.c.transaction_currency.nullable is True
