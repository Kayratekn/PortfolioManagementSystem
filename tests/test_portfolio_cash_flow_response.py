from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from src.model.portfolio_cash_flow import PortfolioCashFlow
from src.response.portfolio_cash_flow_response import (
    PortfolioCashFlowListResponse,
    PortfolioCashFlowResponse,
)


CREATED_AT = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def _build_cash_flow() -> PortfolioCashFlow:
    return PortfolioCashFlow(
        id=1,
        portfolio_id=2,
        flow_type="DEPOSIT",
        amount=Decimal("123.45678901"),
        currency="TRY",
        flow_date=date(2026, 9, 2),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def test_cash_flow_response_preserves_fields() -> None:
    response = PortfolioCashFlowResponse.model_validate(_build_cash_flow())

    assert response.id == 1
    assert response.portfolio_id == 2
    assert response.flow_type == "DEPOSIT"
    assert response.amount == Decimal("123.45678901")
    assert response.currency == "TRY"
    assert response.flow_date == date(2026, 9, 2)


def test_cash_flow_response_serializes_decimal_as_string() -> None:
    response = PortfolioCashFlowResponse.model_validate(_build_cash_flow())

    body = response.model_dump(mode="json")

    assert body["amount"] == "123.45678901"


def test_cash_flow_list_response_preserves_pagination_and_decimal_serialization() -> None:
    item = PortfolioCashFlowResponse.model_validate(_build_cash_flow())
    response = PortfolioCashFlowListResponse(items=[item], total=1, skip=0, limit=50)

    body = response.model_dump(mode="json")

    assert body["total"] == 1
    assert body["skip"] == 0
    assert body["limit"] == 50
    assert body["items"][0]["amount"] == "123.45678901"
