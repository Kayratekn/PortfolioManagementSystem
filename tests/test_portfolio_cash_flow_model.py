from __future__ import annotations

from sqlalchemy import CheckConstraint, Index

from src.model.portfolio_cash_flow import PortfolioCashFlow


def test_portfolio_cash_flow_model_defines_constraints_and_index() -> None:
    constraints = {
        constraint.name
        for constraint in PortfolioCashFlow.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {
        index.name
        for index in PortfolioCashFlow.__table__.indexes
        if isinstance(index, Index)
    }

    assert "ck_portfolio_cash_flows_flow_type_allowed" in constraints
    assert "ck_portfolio_cash_flows_amount_positive" in constraints
    assert "ck_portfolio_cash_flows_currency_allowed" in constraints
    assert "ix_portfolio_cash_flows_portfolio_date_id" in indexes
    assert PortfolioCashFlow.__table__.c.amount.type.precision == 20
    assert PortfolioCashFlow.__table__.c.amount.type.scale == 8
