from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.config.dependencies import get_ai_client
from src.main import app
from src.model.ai_analysis import AiAnalysis
from src.model.asset import Asset
from src.model.tefas_fund_allocation_data import TefasFundAllocationData
from src.model.tefas_fund_daily_data import TefasFundDailyData
from src.model.transaction import Transaction
from src.repositories.tefas_fund_allocation_data_repository import TefasFundAllocationDataRepository
from src.repositories.tefas_fund_daily_data_repository import TefasFundDailyDataRepository
from src.integrations.ai_client import (
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)


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
        "optimal_weights": {"AAL": 1},
        "expected_return": 0.12,
        "expected_volatility": 0.08,
        "sharpe_ratio": 1.5,
        "robustness_score": 0.91,
        "scenario_impacts": {"stress": -0.02},
        "correlation_matrix": {"AAL": {"AAL": 1}},
        "sentiment_score": 0.2,
        "sentiment_label": "neutral",
        "educational_advice": "Hold diversified TEFAS exposure.",
        "disclaimer": "Educational only.",
        "model_version": "ai-model-1",
        "formula_version": "portfolio-formula-1",
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
    email: str = "ai-owner@example.com",
    username: str = "ai-owner",
    risk_profile: str | None = None,
) -> tuple[str, int]:
    _register_user(client, email=email, username=username, risk_profile=risk_profile)
    token = _login_user(client, email=email)
    response = client.post(
        "/api/v1/portfolios",
        json={"name": "AI Portfolio", "base_currency": "TRY"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    return token, response.json()["id"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _analysis_url(portfolio_id: int) -> str:
    return f"/api/v1/portfolios/{portfolio_id}/ai/portfolio-analysis"


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
    quantity: Decimal = Decimal("10.00000000"),
    transaction_date: date = date(2026, 1, 1),
) -> Transaction:
    transaction = Transaction(
        portfolio_id=portfolio_id,
        asset_id=asset_id,
        transaction_type="BUY",
        quantity=quantity,
        unit_price=Decimal("1.00000000"),
        transaction_currency="TRY",
        transaction_date=transaction_date,
    )
    db_session.add(transaction)
    db_session.commit()
    db_session.refresh(transaction)
    return transaction


def _add_history(
    db_session: Session,
    *,
    asset_id: int,
    count: int = 60,
    end_date: date = AS_OF_DATE,
    start_price: Decimal = Decimal("1.00000000"),
) -> None:
    start_date = end_date - timedelta(days=count - 1)
    for index in range(count):
        db_session.add(
            TefasFundDailyData(
                asset_id=asset_id,
                data_date=start_date + timedelta(days=index),
                price=start_price + Decimal(index),
                shares_outstanding=None,
                investor_count=None,
                portfolio_size=None,
                exchange_bulletin_price=None,
            )
        )
    db_session.commit()


def _add_allocation(
    db_session: Session,
    *,
    asset_id: int,
    data_date: date,
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
    email: str = "ai-supported@example.com",
    username: str = "ai-supported",
    risk_profile: str | None = None,
    history_count: int = 60,
    asset_code: str = "AAL",
    quantity: Decimal = Decimal("10.00000000"),
) -> tuple[str, int, Asset]:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email=email,
        username=username,
        risk_profile=risk_profile,
    )
    asset = _create_asset(db_session, asset_code=asset_code)
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id, quantity=quantity)
    _add_history(db_session, asset_id=asset.id, count=history_count)
    return token, portfolio_id, asset


def _post_analysis(client, token: str, portfolio_id: int):
    return client.post(
        _analysis_url(portfolio_id),
        json={"as_of_date": AS_OF_DATE.isoformat()},
        headers=_auth_headers(token),
    )


def test_ai_portfolio_analysis_requires_authentication(client) -> None:
    response = client.post(_analysis_url(999999), json={"as_of_date": AS_OF_DATE.isoformat()})

    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_DETAIL


def test_ownership_isolation_returns_404_before_ai_call(client, db_session: Session) -> None:
    owner_token, portfolio_id = _create_owner_portfolio(
        client,
        email="ai-owner-isolation@example.com",
        username="ai-owner-isolation",
    )
    assert owner_token
    _register_user(client, email="ai-other@example.com", username="ai-other")
    other_token = _login_user(client, email="ai-other@example.com")
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, other_token, portfolio_id)

    assert response.status_code == 404
    assert response.json()["detail"] == "Portfolio not found."
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
        email=f"ai-risk-{suffix}@example.com",
        username=f"ai-risk-{suffix}",
        risk_profile=risk_profile,
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    assert fake_ai.calls[0]["payload"]["risk_profile"] == expected


def test_unknown_risk_profile_returns_422_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-risk-unknown@example.com",
        username="ai-risk-unknown",
        risk_profile="speculative",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Unsupported risk profile."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_empty_holdings_returns_422_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="ai-empty@example.com",
        username="ai-empty",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 422
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_unsupported_held_asset_returns_422_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="ai-unsupported@example.com",
        username="ai-unsupported",
    )
    asset = _create_asset(db_session, asset_code="STK", asset_type="STOCK", fund_kind=None, data_source="MANUAL")
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=asset.id)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Portfolio contains unsupported assets for AI analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_ambiguous_normalized_tefas_fund_codes_return_422_before_ai_call(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id = _create_owner_portfolio(
        client,
        email="ai-ambiguous-codes@example.com",
        username="ai-ambiguous-codes",
    )
    first_asset = _create_asset(db_session, asset_code="DUP")
    second_asset = _create_asset(db_session, asset_code=" dup ")
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=first_asset.id)
    _add_transaction(db_session, portfolio_id=portfolio_id, asset_id=second_asset.id)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Portfolio contains ambiguous TEFAS fund codes for AI analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_exactly_60_history_observations_are_accepted_and_use_persisted_nav(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(client, db_session)
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    payload = fake_ai.calls[0]["payload"]
    history = payload["historical_prices"][asset.asset_code]
    assert len(history) == 60
    assert list(history)[0] == "2026-06-28"
    assert list(history)[-1] == "2026-08-26"
    assert history["2026-08-26"] == 60


def test_59_history_observations_are_rejected_before_ai_call(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-history-59@example.com",
        username="ai-history-59",
        history_count=59,
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 422
    assert response.json()["detail"] == "Insufficient TEFAS history for AI analysis."
    assert fake_ai.calls == []
    assert db_session.query(AiAnalysis).count() == 0


def test_more_than_252_history_observations_sends_latest_252_chronologically(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-history-300@example.com",
        username="ai-history-300",
        history_count=300,
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    history = fake_ai.calls[0]["payload"]["historical_prices"][asset.asset_code]
    assert len(history) == 252
    assert list(history)[0] == "2025-12-18"
    assert list(history)[-1] == "2026-08-26"
    assert list(history.keys()) == sorted(history.keys())


def test_assets_use_decimal_arithmetic_and_json_numeric_boundary(client, db_session: Session) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-decimal-boundary@example.com",
        username="ai-decimal-boundary",
        quantity=Decimal("1.23456789"),
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    value = fake_ai.calls[0]["payload"]["assets"][asset.asset_code]
    expected = Decimal("1.23456789") * Decimal("60.00000000")
    assert value == float(expected)
    assert isinstance(value, float)


def test_latest_allocation_snapshot_on_or_before_and_verified_fraction_payload(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-allocation@example.com",
        username="ai-allocation",
    )
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 20), allocation_percentage=Decimal("10.000000"))
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 25), allocation_percentage=Decimal("85.000000"))
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 27), allocation_percentage=Decimal("1.000000"))
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    assert fake_ai.calls[0]["payload"]["asset_breakdowns"] == {
        asset.asset_code: {"Hisse Senedi": 0.85}
    }


def test_absent_allocation_omits_fund_breakdown(client, db_session: Session) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-no-allocation@example.com",
        username="ai-no-allocation",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    assert asset.asset_code not in fake_ai.calls[0]["payload"]["asset_breakdowns"]


def test_non_zero_unverified_allocation_omits_entire_fund_breakdown(client, db_session: Session) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-unverified-allocation@example.com",
        username="ai-unverified-allocation",
    )
    _add_allocation(db_session, asset_id=asset.id, data_date=AS_OF_DATE, raw_field_name="hs", allocation_percentage=Decimal("85.000000"))
    _add_allocation(db_session, asset_id=asset.id, data_date=AS_OF_DATE, raw_field_name="bb", allocation_percentage=Decimal("5.000000"))
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    assert asset.asset_code not in fake_ai.calls[0]["payload"]["asset_breakdowns"]


@pytest.mark.parametrize(
    "allocation_percentage",
    [Decimal("-1.250000"), Decimal("100.000001")],
)
def test_invalid_verified_allocation_percentage_omits_entire_fund_breakdown(
    client,
    db_session: Session,
    allocation_percentage: Decimal,
) -> None:
    token, portfolio_id, asset = _prepare_supported_portfolio(
        client,
        db_session,
        email=f"ai-invalid-allocation-{str(allocation_percentage).replace('.', '-').replace('-', 'neg')}@example.com",
        username=f"ai-invalid-allocation-{str(allocation_percentage).replace('.', '-').replace('-', 'neg')}",
    )
    _add_allocation(
        db_session,
        asset_id=asset.id,
        data_date=AS_OF_DATE,
        raw_field_name="hs",
        allocation_percentage=allocation_percentage,
    )
    _add_allocation(
        db_session,
        asset_id=asset.id,
        data_date=AS_OF_DATE,
        raw_field_name="tpp",
        allocation_percentage=Decimal("10.000000"),
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    assert len(fake_ai.calls) == 1
    payload_breakdowns = fake_ai.calls[0]["payload"]["asset_breakdowns"]
    assert asset.asset_code not in payload_breakdowns
    assert all(
        Decimal("0") <= Decimal(str(fraction)) <= Decimal("1")
        for breakdown in payload_breakdowns.values()
        for fraction in breakdown.values()
    )


def test_recent_news_is_empty_and_ai_endpoint_is_exact(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-news-endpoint@example.com",
        username="ai-news-endpoint",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    assert fake_ai.calls[0]["endpoint"] == "/api/ai/portfolio-analysis"
    assert fake_ai.calls[0]["payload"]["recent_news"] == []
    assert set(fake_ai.calls[0]["payload"]) == {
        "user_id",
        "risk_profile",
        "target_currency",
        "assets",
        "recent_news",
        "historical_prices",
        "asset_breakdowns",
    }


@pytest.mark.parametrize(
    ("case_name", "response_override"),
    [
        ("model-version", {"model_version": ""}),
        ("formula-version", {"formula_version": "   "}),
        ("advice", {"educational_advice": ""}),
        ("weights", {"optimal_weights": []}),
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
        email=f"ai-invalid-response-{case_name}@example.com",
        username=f"ai-invalid-response-{case_name}",
    )
    fake_ai = _install_ai_client(FakeAiClient(_valid_ai_response(**response_override)))

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service returned an invalid response."
    assert len(fake_ai.calls) == 1
    assert db_session.query(AiAnalysis).count() == 0


def test_ai_unavailable_returns_503_and_no_persistence(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-unavailable@example.com",
        username="ai-unavailable",
    )
    _install_ai_client(FakeAiClient(AiServiceUnavailableError("down")))

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 503
    assert response.json()["detail"] == "AI service temporarily unavailable."
    assert db_session.query(AiAnalysis).count() == 0


def test_ai_4xx_returns_502_and_no_persistence(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-4xx@example.com",
        username="ai-4xx",
    )
    _install_ai_client(FakeAiClient(AiServiceRequestError("bad", status_code=422)))

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 502
    assert response.json()["detail"] == "AI service rejected the backend request."
    assert db_session.query(AiAnalysis).count() == 0


def test_ai_response_error_returns_502_and_no_persistence(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-response-error@example.com",
        username="ai-response-error",
    )
    _install_ai_client(FakeAiClient(AiServiceResponseError("bad json")))

    response = _post_analysis(client, token, portfolio_id)

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
        email="ai-success@example.com",
        username="ai-success",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    body = response.json()
    assert body["analysis_id"] is not None
    assert body["portfolio_id"] == portfolio_id
    assert body["as_of_date"] == AS_OF_DATE.isoformat()
    assert body["model_version"] == "ai-model-1"
    assert body["formula_version"] == "portfolio-formula-1"
    assert "extra_internal" not in body
    persisted = db_session.scalar(select(AiAnalysis).where(AiAnalysis.id == body["analysis_id"]))
    assert persisted is not None
    assert persisted.user_id == fake_ai.calls[0]["payload"]["user_id"]
    assert persisted.portfolio_id == portfolio_id
    assert persisted.analysis_type == "portfolio-analysis"
    assert persisted.explanation_text == "Hold diversified TEFAS exposure."
    assert persisted.disclaimer == "Educational only."
    assert persisted.model_version == "ai-model-1"
    assert persisted.formula_version == "portfolio-formula-1"
    assert set(persisted.result_payload) == {
        "optimal_weights",
        "expected_return",
        "expected_volatility",
        "sharpe_ratio",
        "robustness_score",
        "scenario_impacts",
        "correlation_matrix",
        "sentiment_score",
        "sentiment_label",
    }
    assert "historical_prices" not in persisted.result_payload
    assert "recent_news" not in persisted.result_payload
    assert "asset_breakdowns" not in persisted.result_payload
    assert "extra_internal" not in persisted.result_payload


def test_persistence_uses_validated_serialized_ai_result_not_raw_coercible_values(
    client,
    db_session: Session,
) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-validated-persistence@example.com",
        username="ai-validated-persistence",
    )
    fake_ai = _install_ai_client(
        FakeAiClient(
            _valid_ai_response(
                optimal_weights={"AAL": "1.0"},
                expected_return="0.1200",
                expected_volatility="0.0800",
                sharpe_ratio="1.5000",
                robustness_score="0.9100",
                sentiment_score="0.2000",
            )
        )
    )

    response = _post_analysis(client, token, portfolio_id)

    assert response.status_code == 200
    persisted = db_session.scalar(
        select(AiAnalysis).where(AiAnalysis.id == response.json()["analysis_id"])
    )
    assert persisted is not None
    assert fake_ai.response["expected_return"] == "0.1200"
    assert persisted.result_payload == {
        "optimal_weights": {"AAL": "1.0"},
        "expected_return": "0.1200",
        "expected_volatility": "0.0800",
        "sharpe_ratio": "1.5000",
        "robustness_score": "0.9100",
        "scenario_impacts": {"stress": -0.02},
        "correlation_matrix": {"AAL": {"AAL": 1}},
        "sentiment_score": "0.2000",
        "sentiment_label": "neutral",
    }

def test_second_successful_analysis_appends_second_row(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-append@example.com",
        username="ai-append",
    )
    _install_ai_client(FakeAiClient())

    first = _post_analysis(client, token, portfolio_id)
    second = _post_analysis(client, token, portfolio_id)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["analysis_id"] != second.json()["analysis_id"]
    assert db_session.query(AiAnalysis).count() == 2


def test_request_rejects_frontend_supplied_ssot_fields(client, db_session: Session) -> None:
    token, portfolio_id, _asset = _prepare_supported_portfolio(
        client,
        db_session,
        email="ai-ssot-fields@example.com",
        username="ai-ssot-fields",
    )
    fake_ai = _install_ai_client(FakeAiClient())

    response = client.post(
        _analysis_url(portfolio_id),
        json={"as_of_date": AS_OF_DATE.isoformat(), "holdings": []},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422
    assert fake_ai.calls == []


def test_no_migration_added_for_ai_portfolio_analysis_slice() -> None:
    assert not (PROJECT_ROOT / "alembic" / "versions" / "20260907_0024_create_ai_portfolio_analysis.py").exists()


def test_daily_repository_latest_on_or_before_ordering_is_deterministic(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="ORD")
    older = TefasFundDailyData(asset_id=asset.id, data_date=date(2026, 8, 24), price=Decimal("1.00000000"))
    first_same_day = TefasFundDailyData(asset_id=asset.id, data_date=date(2026, 8, 25), price=Decimal("2.00000000"))
    second_same_day = TefasFundDailyData(asset_id=asset.id, data_date=date(2026, 8, 25), price=Decimal("3.00000000"))
    # This repository method supports deterministic ordering; duplicate dates are possible in tests before DB uniqueness is flushed separately per object.
    db_session.add(older)
    db_session.flush()
    db_session.add(first_same_day)
    db_session.flush()
    first_same_day.data_date = date(2026, 8, 23)
    db_session.flush()
    db_session.add(second_same_day)
    db_session.flush()

    result = TefasFundDailyDataRepository(db_session).list_latest_on_or_before(
        asset_id=asset.id,
        data_date=date(2026, 8, 25),
        limit=2,
    )

    assert result == [second_same_day, older]


def test_allocation_repository_uses_latest_snapshot_on_or_before(db_session: Session) -> None:
    asset = _create_asset(db_session, asset_code="ALO")
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 20), allocation_percentage=Decimal("10.000000"))
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 25), allocation_percentage=Decimal("85.000000"))
    _add_allocation(db_session, asset_id=asset.id, data_date=date(2026, 8, 27), allocation_percentage=Decimal("99.000000"))

    result = TefasFundAllocationDataRepository(db_session).list_latest_on_or_before(
        asset_id=asset.id,
        data_date=AS_OF_DATE,
    )

    assert len(result) == 1
    assert result[0].data_date == date(2026, 8, 25)
    assert result[0].allocation_percentage == Decimal("85.000000")