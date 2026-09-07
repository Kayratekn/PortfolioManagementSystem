from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.dependencies import get_ai_client
from src.integrations.ai_client import (
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)
from src.main import app
from src.model.ai_analysis import AiAnalysis
from src.model.asset import Asset
from src.model.tefas_fund_allocation_data import TefasFundAllocationData
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.model.transaction import Transaction


AUTH_DETAIL = "Authentication credentials were not provided or are invalid."
AS_OF_DATE = date(2026, 8, 26)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FakeAiClient:
    def __init__(self, response: dict[str, Any] | Exception | None = None) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response = response if response is not None else _valid_ai_response()

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"endpoint": endpoint, "payload": payload})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _valid_ai_response(**overrides: Any) -> dict[str, Any]:
    response = {
        "scenario_impacts": {"TRY shock": -0.12},
        "robustness_score_100": 82.5,
        "verdict": "Resilient under tested scenarios.",
        "model_version": "ai-model-robustness-1",
        "formula_version": "robustness-formula-1",
        "extra_internal": "must not leak",
    }
    response.update(overrides)
    return response


def _register_user(
    client,
    *,
    email: str,
    username: str,
    risk_profile: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "email": email,
        "username": username,
        "password": "StrongPass123",
        "preferred_currency": "TRY",
    }
    if risk_profile is not None:
        payload["risk_profile"] = risk_profile
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201


def _login_user(client, *, email: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPass123"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_owner_portfolio(
    client,
    *,
    email: str = "robust-owner@example.com",
    username: str = "robust-owner",
    risk_profile: str | None = None,
) -> tuple[str, int]:
    _register_user(client, email=email, username=username, risk_profile=risk_profile)
    token = _login_user(client, email=email)
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "Robustness Portfolio", "base_currency": "TRY"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    return token, response.json()["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _robustness_url(portfolio_id: int) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/ai/robustness"


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AAL",
    asset_type: str = "FUND",
    fund_kind: str | None = "YAT",
    data_source: str = "TEFAS",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=f"{asset_code} Example Fund",
        asset_type=asset_type,
        fund_kind=fund_kind,
        currency="TRY",
        data_source=data_source,
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _add_transaction(
    db_session: Session,
    *,
    portfolio_id: int,
    asset_id: int,
    transaction_type: str = "BUY",
    quantity: Decimal = Decimal("10.00000000"),
    transaction_date: date = date(2026, 1, 1),
) -> Transaction:
    transaction = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type=transaction_type,
        quantity=quantity,
        unit_price=Decimal("1.00000000"),
        transaction_currency="TRY",
        transaction_date=transaction_date,
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction


def _add_nav(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date = AS_OF_DATE,
    price: Decimal = Decimal("60.00000000"),
) -> TefasFundDailyData:
    daily_data = TefasFundDailyData(asset_id=asset_id, data_date=data_date, price=price)
    db_session.add(daily_data)
    db_session.commit()
    db_session.refresh(daily_data)
    return daily_data


def _add_allocation(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date = AS_OF_DATE,
    raw_field_name: str = "hs",
    allocation_percentage: Decimal = Decimal("85.000000"),
) -> None:
    db_session.add(
        TefasFundAllocationData(
            asset_id=asset_id,
            data_date=data_date,
            raw_field_name=raw_field_name,
            allocation_percentage=allocation_percentage,
        )
    )
    db_session.commit()


def _install_ai_client(fake_client: FakeAiClient) -> FakeAiClient:
    app.dependency_overrides[get_ai_client] = lambda: fake_client
    return fake_client


def _prepare_supported_portfolio(
    client,
    db_session: Session,
    *,
    email: str = "robust-supported@example.com",
    username: str = "robust-supported",
    risk_profile: str | None = None,
    asset_code: str = "AAL",
    quantity: Decimal = Decimal("10.00000000"),
    nav_date: date = AS_OF_DATE,
    nav_price: Decimal = Decimal("60.00000000"),
) -> tuple[str, int, Asset]:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email=email,
        username=username,
        risk_profile=risk_profile,
    )
    asset = _create_asset(db_session, asset_code=asset_code)
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, quantity=quantity)
    _add_nav(db_session, asset_id=asset.id, data_date=nav_date, price=nav_price)
    return token, portfolio_id, asset


def _post_robustness(client, token: str, portfolio_id: int):
    return client.post(
        _robustness_url(portfolio_id),
        json={"as_of_date": AS_OF_DATE.isoformat()},
        headers=_auth_headers(token),
    )


def test_ai_robustness_requires_authentication(client) -> None:
    response = client.post(_robustness_url(999999), json={"as_of_date": AS_OF_DATE.isoformat()})

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_ownership_isolation_returns_404_before_ai_call(client, db_session: Session) -> None:
    _owner_token, portfolio_id = _create_owner_portfolio(
        client,
        email="robust-owner-isolation@example.com",
        username="robust-owner-isolation",
    )
    _register_user(client, email="robust-other@example.com", username="robust-other")
    other_token = _login_user(client, email="robust-other@example.com")
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, other_token, portfolio_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_as_of_holdings_exclude_future_transactions(client, db_session: Session) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="robust-future-holding@example.com",
        username="robust-future-holding",
    )
    asset = _create_asset(db_session, asset_code="FUT")
    _add_transaction(
        db_session,
        portfolio_id=portfolio_id,
        asset_id=asset.id,
        transaction_date=date(2026, 8, 27),
    )
    _add_nav(db_session, asset_id=asset.id)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Portfolio has no supported holdings for AI robustness analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


@pytest.mark.parametrize(
    ("risk_profile", "expected"),
    [
        (None, "dengeli"),
        ("   ", "dengeli"),
        (" conservative ", "muhafazakar"),
        ("LOW", "muhafazakar"),
        ("düşük", "muhafazakar"),
        ("defansif", "muhafazakar"),
        ("balanced", "dengeli"),
        ("MEDIUM", "dengeli"),
        ("orta", "dengeli"),
        ("aggressive", "agresif"),
        ("HIGH", "agresif"),
        ("yüksek", "agresif"),
        ("dinamik", "agresif"),
        ("muhafazakar", "muhafazakar"),
        ("agresif", "agresif"),
    ],
)
def test_risk_profile_aliases_normalize_to_canonical_values(
    client,
    db_session: Session,
    risk_profile: str | None,
    expected: str,
) -> None:
    suffix = expected + str(len(risk_profile or "none"))
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email=f"robust-risk-{suffix}@example.com",
        username=f"robust-risk-{suffix}",
        risk_profile=risk_profile,
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    assert fake_ai.calls[0]["payload"]["risk_profile"] == expected


def test_unknown_risk_profile_returns_422_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-risk-unknown@example.com",
        username="robust-risk-unknown",
        risk_profile="speculative",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported risk profile."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_empty_holdings_returns_422_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="robust-empty@example.com",
        username="robust-empty",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Portfolio has no supported holdings for AI robustness analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_unsupported_held_asset_returns_422_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="robust-unsupported@example.com",
        username="robust-unsupported",
    )
    asset = _create_asset(db_session, asset_code="STK", asset_type="STOCK", fund_kind=None, data_source="MANUAL")
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Portfolio contains unsupported assets for AI robustness analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_ambiguous_normalized_tefas_fund_codes_return_422_before_ai_call(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="robust-ambiguous-codes@example.com",
        username="robust-ambiguous-codes",
    )
    first_asset = _create_asset(db_session, asset_code="DUP")
    second_asset = _create_asset(db_session, asset_code=" dup ")
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=first_asset.id)
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=second_asset.id)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Portfolio contains ambiguous TEFAS fund codes for AI robustness analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_blank_normalized_tefas_fund_code_returns_422_before_ai_call(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="robust-invalid-code@example.com",
        username="robust-invalid-code",
    )
    asset = _create_asset(db_session, asset_code="   ")
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Portfolio contains invalid TEFAS fund codes for AI robustness analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_missing_nav_on_or_before_returns_422_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="robust-missing-nav@example.com",
        username="robust-missing-nav",
    )
    asset = _create_asset(db_session, asset_code="NONAV")
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "TEFAS price unavailable for AI robustness analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_future_nav_is_not_used(client, db_session: Session) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-future-nav@example.com",
        username="robust-future-nav",
        nav_date=date(2026, 8, 25),
        nav_price=Decimal("40.00000000"),
    )
    _add_nav(db_session, asset_id=asset.id, data_date=date(2026, 8, 27), price=Decimal("99.00000000"))
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    assert fake_ai.calls[0]["payload"]["assets"][asset.asset_code] == 400


def test_assets_use_decimal_arithmetic_and_latest_nav_at_json_boundary(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-decimal-boundary@example.com",
        username="robust-decimal-boundary",
        quantity=Decimal("1.23456789"),
        nav_price=Decimal("60.12345678"),
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    value = fake_ai.calls[0]["payload"]["assets"][asset.asset_code]
    expected = Decimal("1.23456789") * Decimal("60.12345678")
    assert value == float(expected)
    assert isinstance(value, float)


def test_latest_allocation_snapshot_on_or_before_and_verified_fraction_payload(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-allocation@example.com",
        username="robust-allocation",
    )
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 20), allocation_percentage=Decimal("10.000000"))
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 25), allocation_percentage=Decimal("85.000000"))
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 27), allocation_percentage=Decimal("99.000000"))
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    assert fake_ai.calls[0]["payload"]["asset_breakdowns"] == {
        asset.asset_code: {"Hisse Senedi": 0.85}
    }


def test_absent_allocation_omits_fund_breakdown(client, db_session: Session) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-no-allocation@example.com",
        username="robust-no-allocation",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    assert asset.asset_code not in fake_ai.calls[0]["payload"]["asset_breakdowns"]


def test_zero_allocation_is_ignored(client, db_session: Session) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-zero-allocation@example.com",
        username="robust-zero-allocation",
    )
    _add_allocation(db_session, asset_id=asset.id, raw_field_name="vmtl", allocation_percentage=Decimal("0.000000"))
    _add_allocation(db_session, asset_id=asset.id, raw_field_name="hs", allocation_percentage=Decimal("85.000000"))
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    assert fake_ai.calls[0]["payload"]["asset_breakdowns"] == {
        asset.asset_code: {"Hisse Senedi": 0.85}
    }


@pytest.mark.parametrize("allocation_percentage", [Decimal("-1.250000"), Decimal("100.000001")])
def test_invalid_verified_allocation_percentage_omits_entire_fund_breakdown(
    client,
    db_session: Session,
    allocation_percentage: Decimal,
) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email=f"robust-invalid-allocation-{str(allocation_percentage).replace('.', '-').replace('-', 'neg')}@example.com",
        username=f"robust-invalid-allocation-{str(allocation_percentage).replace('.', '-').replace('-', 'neg')}",
    )
    _add_allocation(db_session, asset_id=asset.id, raw_field_name="hs", allocation_percentage=allocation_percentage)
    _add_allocation(db_session, asset_id=asset.id, raw_field_name="tpp", allocation_percentage=Decimal("10.000000"))
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    payload_breakdowns = fake_ai.calls[0]["payload"]["asset_breakdowns"]
    assert asset.asset_code not in payload_breakdowns
    assert all(
        Decimal("0") <= Decimal(str(fraction)) <= Decimal("1")
        for breakdown in payload_breakdowns.values()
        for fraction in breakdown.values()
    )


def test_non_zero_unverified_allocation_omits_entire_fund_breakdown(client, db_session: Session) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-unverified-allocation@example.com",
        username="robust-unverified-allocation",
    )
    _add_allocation(db_session, asset_id=asset.id, raw_field_name="hs", allocation_percentage=Decimal("85.000000"))
    _add_allocation(db_session, asset_id=asset.id, raw_field_name="bb", allocation_percentage=Decimal("5.000000"))
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    assert asset.asset_code not in fake_ai.calls[0]["payload"]["asset_breakdowns"]


def test_ai_endpoint_and_payload_shape_are_exact(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-payload@example.com",
        username="robust-payload",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    call = fake_ai.calls[0]
    assert call["endpoint"] == "/api/ai/robustness"
    assert set(call["payload"]) == {"user_id", "risk_profile", "assets", "asset_breakdowns"}
    assert "historical_prices" not in call["payload"]
    assert "recent_news" not in call["payload"]
    assert "target_currency" not in call["payload"]


@pytest.mark.parametrize("robustness_score_100", [0, 100])
def test_robustness_score_boundaries_are_accepted(
    client,
    db_session: Session,
    robustness_score_100: int,
) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email=f"robust-score-boundary-{robustness_score_100}@example.com",
        username=f"robust-score-boundary-{robustness_score_100}",
    )
    fake_ai = _install_ai_client(
        FakeAiClient(_valid_ai_response(robustness_score_100=robustness_score_100))
    )

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    assert response.json()["robustness_score_100"] == str(robustness_score_100)
    persisted = db_session.scalar(
        select(AiAnalysis).where(AiAnalysis.id == response.json()["analysis_id"])
    )
    assert persisted is not None
    assert persisted.result_payload["robustness_score_100"] == str(robustness_score_100)


@pytest.mark.parametrize(
    ("case_name", "response_override"),
    [
        ("verdict", {"verdict": ""}),
        ("model-version", {"model_version": "   "}),
        ("formula-version", {"formula_version": ""}),
        ("scenario-impacts", {"scenario_impacts": []}),
        ("score-negative", {"robustness_score_100": -1}),
        ("score-above-100", {"robustness_score_100": "100.01"}),
    ],
)
def test_invalid_ai_response_returns_502_and_no_persistence(
    client,
    db_session: Session,
    case_name: str,
    response_override: dict[str, Any],
) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email=f"robust-invalid-response-{case_name}@example.com",
        username=f"robust-invalid-response-{case_name}",
    )
    fake_ai = _install_ai_client(FakeAiClient(_valid_ai_response(**response_override)))

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert len(fake_ai.calls) == 1
    assert db_session.query(AiAnalysis).count() == 0


def test_ai_unavailable_returns_503_and_no_persistence(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-unavailable@example.com",
        username="robust-unavailable",
    )
    _install_ai_client(FakeAiClient(AiServiceUnavailableError("down")))

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 503
    assert response.json()["detail"] == "AI service temporarily unavailable."
    assert db_session.query(AiAnalysis).count() == 0


def test_ai_4xx_returns_502_and_no_persistence(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-4xx@example.com",
        username="robust-4xx",
    )
    _install_ai_client(FakeAiClient(AiServiceRequestError("bad", status_code=422)))

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service rejected the backend request."
    assert db_session.query(AiAnalysis).count() == 0


def test_ai_response_error_returns_502_and_no_persistence(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-response-error@example.com",
        username="robust-response-error",
    )
    _install_ai_client(FakeAiClient(AiServiceResponseError("bad json")))

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert db_session.query(AiAnalysis).count() == 0


def test_successful_call_persists_one_structured_ai_analysis_and_public_response(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-success@example.com",
        username="robust-success",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"] is not None
    assert body["portfolio_id"] == portfolio_id
    assert body["as_of_date"] == AS_OF_DATE.isoformat()
    assert body["model_version"] == "ai-model-robustness-1"
    assert body["formula_version"] == "robustness-formula-1"
    assert "extra_internal" not in body
    persisted = db_session.scalar(select(AiAnalysis).where(AiAnalysis.id == body["analysis_id"]))
    assert persisted is not None
    assert persisted.user_id == fake_ai.calls[0]["payload"]["user_id"]
    assert persisted.portfolio_id == portfolio_id
    assert persisted.analysis_type == "robustness"
    assert persisted.explanation_text is None
    assert persisted.disclaimer is None
    assert persisted.model_version == "ai-model-robustness-1"
    assert persisted.formula_version == "robustness-formula-1"
    assert persisted.result_payload == {
        "scenario_impacts": {"TRY shock": -0.12},
        "robustness_score_100": "82.5",
        "verdict": "Resilient under tested scenarios.",
    }
    assert "assets" not in persisted.result_payload
    assert "asset_breakdowns" not in persisted.result_payload
    assert "extra_internal" not in persisted.result_payload


def test_persistence_uses_validated_serialized_ai_result_not_raw_coercible_values(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-validated-persistence@example.com",
        username="robust-validated-persistence",
    )
    fake_ai = _install_ai_client(
        FakeAiClient(_valid_ai_response(robustness_score_100="82.5000"))
    )

    response = _post_robustness(client, token, portfolio_id)

    assert response.status_code == 200
    persisted = db_session.scalar(
        select(AiAnalysis).where(AiAnalysis.id == response.json()["analysis_id"])
    )
    assert persisted is not None
    assert fake_ai.response["robustness_score_100"] == "82.5000"
    assert persisted.result_payload == {
        "scenario_impacts": {"TRY shock": -0.12},
        "robustness_score_100": "82.5000",
        "verdict": "Resilient under tested scenarios.",
    }


def test_second_successful_analysis_appends_second_row(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-append@example.com",
        username="robust-append",
    )
    _install_ai_client(FakeAiClient())

    first = _post_robustness(client, token, portfolio_id)
    second = _post_robustness(client, token, portfolio_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["analysis_id"] != second.json()["analysis_id"]
    assert db_session.query(AiAnalysis).count() == 2


def test_request_rejects_frontend_supplied_ssot_fields(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="robust-ssot-fields@example.com",
        username="robust-ssot-fields",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = client.post(
        _robustness_url(portfolio_id),
        json={"as_of_date": AS_OF_DATE.isoformat(), "holdings": []},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422
    assert fake_ai.calls == []


def test_no_migration_added_for_ai_robustness_slice() -> None:
    assert not (PROJECT_ROOT / "alembic" / "versions" / "20260907_0024_create_ai_robustness.py").exists()
