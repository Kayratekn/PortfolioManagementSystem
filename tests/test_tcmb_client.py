from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import ValidationError

from src.config.settings import Settings, get_settings
from src.integrations import tcmb_client as tcmb_client_module
from src.integrations.tcmb_client import TcmbClient, TcmbClientError


class FakeHttpxClient:
    def __init__(self, outcomes: list[Any], calls: list[dict[str, Any]], **kwargs: Any) -> None:
        self.outcomes = outcomes
        self.calls = calls
        self.kwargs = kwargs

    def __enter__(self) -> FakeHttpxClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def get(self, url: str, **kwargs: Any) -> Any:
        self.calls.append(
            {
                "url": url,
                **kwargs,
                "client_kwargs": self.kwargs,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _make_text_response(status_code: int, text: str) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("GET", "https://example.test/kurlar/today.xml"),
    )


def _install_fake_client(monkeypatch: pytest.MonkeyPatch, outcomes: list[Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_client_factory(**kwargs: Any) -> FakeHttpxClient:
        return FakeHttpxClient(outcomes, calls, **kwargs)

    monkeypatch.setattr(tcmb_client_module.httpx, "Client", fake_client_factory)
    return calls


def _install_fake_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(tcmb_client_module.time, "sleep", fake_sleep)
    return sleep_calls


def _currency_xml(
    currency_code: str,
    *,
    unit: str = "1",
    forex_buying: str = "40.12345678",
    forex_selling: str = "40.87654321",
) -> str:
    return f"""
    <Currency CurrencyCode="{currency_code}">
        <Unit>{unit}</Unit>
        <ForexBuying>{forex_buying}</ForexBuying>
        <ForexSelling>{forex_selling}</ForexSelling>
        <BanknoteBuying>1.00</BanknoteBuying>
        <BanknoteSelling>1.00</BanknoteSelling>
        <CrossRateUSD>1.00</CrossRateUSD>
        <CrossRateOther>1.00</CrossRateOther>
    </Currency>
    """


def _rates_xml(
    *,
    root_date: str = "25.08.2026",
    usd_xml: str | None = None,
    eur_xml: str | None = None,
    gbp_xml: str | None = None,
) -> str:
    rows = [
        usd_xml if usd_xml is not None else _currency_xml("USD"),
        eur_xml
        if eur_xml is not None
        else _currency_xml("EUR", forex_buying="47.11111111", forex_selling="47.22222222"),
        gbp_xml
        if gbp_xml is not None
        else _currency_xml("GBP", unit="100", forex_buying="5400.67890000", forex_selling="5500.12340000"),
    ]
    return f'<Tarih_Date Tarih="{root_date}">{"".join(rows)}</Tarih_Date>'


def test_constructor_stores_explicit_values_and_trims_trailing_slash() -> None:
    client = TcmbClient(
        base_url="https://example.test/",
        timeout_seconds=12.5,
        max_retries=0,
        retry_wait_seconds=0,
    )

    assert client.base_url == "https://example.test"
    assert client.timeout_seconds == 12.5
    assert client.max_retries == 0
    assert client.retry_wait_seconds == 0


def test_settings_defaults_for_tcmb_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TCMB_BASE_URL", raising=False)
    monkeypatch.delenv("TCMB_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("TCMB_MAX_RETRIES", raising=False)
    monkeypatch.delenv("TCMB_RETRY_WAIT_SECONDS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.tcmb_base_url == "https://www.tcmb.gov.tr"
    assert settings.tcmb_timeout_seconds == 30.0
    assert settings.tcmb_max_retries == 3
    assert settings.tcmb_retry_wait_seconds == 10.0


def test_constructor_loads_tcmb_overrides_from_settings_when_arguments_are_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("TCMB_BASE_URL", "https://example.test/")
    monkeypatch.setenv("TCMB_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("TCMB_MAX_RETRIES", "2")
    monkeypatch.setenv("TCMB_RETRY_WAIT_SECONDS", "4")

    try:
        client = TcmbClient(
            base_url=None,
            timeout_seconds=None,
            max_retries=None,
            retry_wait_seconds=None,
        )

        assert client.base_url == "https://example.test"
        assert client.timeout_seconds == 12.0
        assert client.max_retries == 2
        assert client.retry_wait_seconds == 4.0
    finally:
        get_settings.cache_clear()


def test_current_rates_gets_today_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_text_response(200, _rates_xml())])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)

    client.fetch_current_rates()

    assert len(calls) == 1
    assert calls[0]["url"] == "https://example.test/kurlar/today.xml"
    assert calls[0]["client_kwargs"] == {"timeout": 5, "follow_redirects": True}


def test_historical_rates_gets_formatted_exact_date_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_text_response(200, _rates_xml())])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)

    client.fetch_historical_rates(rate_date=date(2026, 8, 26))

    assert len(calls) == 1
    assert calls[0]["url"] == "https://example.test/kurlar/202608/26082026.xml"


def test_effective_date_comes_from_xml_root_not_requested_date(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_client(monkeypatch, [_make_text_response(200, _rates_xml(root_date="25.08.2026"))])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)

    result = client.fetch_historical_rates(rate_date=date(2026, 8, 26))

    assert [item.rate_date for item in result] == [date(2026, 8, 25)] * 3


def test_usd_eur_gbp_parsing_decimal_preservation_unit_normalization_and_ordering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    xml_text = _rates_xml(
        usd_xml=_currency_xml("USD", forex_buying="40.12345678", forex_selling="40.87654321"),
        eur_xml=_currency_xml("EUR", forex_buying="47.11111111", forex_selling="47.22222222"),
        gbp_xml=_currency_xml("GBP", unit="100", forex_buying="5400.67890000", forex_selling="5500.12340000"),
    )
    _install_fake_client(monkeypatch, [_make_text_response(200, xml_text)])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)

    result = client.fetch_current_rates()

    assert [item.base_currency for item in result] == ["USD", "EUR", "GBP"]
    assert [item.quote_currency for item in result] == ["TRY", "TRY", "TRY"]
    assert result[0].forex_buying == Decimal("40.12345678")
    assert result[0].forex_selling == Decimal("40.87654321")
    assert result[1].forex_buying == Decimal("47.11111111")
    assert result[1].forex_selling == Decimal("47.22222222")
    assert result[2].forex_buying == Decimal("54.0067890000")
    assert result[2].forex_selling == Decimal("55.0012340000")


def test_observation_result_is_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_client(monkeypatch, [_make_text_response(200, _rates_xml())])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)
    observation = client.fetch_current_rates()[0]

    with pytest.raises(FrozenInstanceError):
        observation.base_currency = "EUR"


def test_request_error_followed_by_success_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("GET", "https://example.test/kurlar/today.xml")
    outcomes = [
        httpx.RequestError("temporary network error", request=request),
        _make_text_response(200, _rates_xml()),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=2, retry_wait_seconds=7)

    result = client.fetch_current_rates()

    assert len(result) == 3
    assert len(calls) == 2
    assert sleep_calls == [7]


def test_http_500_followed_by_success_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = [
        _make_text_response(500, "server error"),
        _make_text_response(200, _rates_xml()),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=1, retry_wait_seconds=2)

    result = client.fetch_current_rates()

    assert len(result) == 3
    assert len(calls) == 2
    assert sleep_calls == [2]


def test_http_429_followed_by_success_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = [
        _make_text_response(429, "rate limited"),
        _make_text_response(200, _rates_xml()),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=1, retry_wait_seconds=6)

    result = client.fetch_current_rates()

    assert len(result) == 3
    assert len(calls) == 2
    assert sleep_calls == [6]


def test_http_400_is_not_retried_and_raises_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_text_response(400, "bad request")])
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=3, retry_wait_seconds=6)

    with pytest.raises(TcmbClientError, match="400"):
        client.fetch_current_rates()

    assert len(calls) == 1
    assert sleep_calls == []


def test_transient_failures_exceeding_max_retries_raise_client_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "https://example.test/kurlar/today.xml")
    outcomes = [
        httpx.RequestError("temporary failure 1", request=request),
        httpx.RequestError("temporary failure 2", request=request),
        httpx.RequestError("temporary failure 3", request=request),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=2, retry_wait_seconds=9)

    with pytest.raises(TcmbClientError, match="temporary failure 3"):
        client.fetch_current_rates()

    assert len(calls) == 3
    assert sleep_calls == [9, 9]


def test_malformed_xml_raises_client_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_text_response(200, "<Tarih_Date>")])
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=3, retry_wait_seconds=1)

    with pytest.raises(TcmbClientError, match="malformed XML"):
        client.fetch_current_rates()

    assert len(calls) == 1
    assert sleep_calls == []


@pytest.mark.parametrize("xml_text", ["<Tarih_Date></Tarih_Date>", '<Tarih_Date Tarih="2026-08-25"></Tarih_Date>'])
def test_missing_or_invalid_root_tarih_raises_client_error(
    monkeypatch: pytest.MonkeyPatch,
    xml_text: str,
) -> None:
    _install_fake_client(monkeypatch, [_make_text_response(200, xml_text)])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)

    with pytest.raises(TcmbClientError, match="Tarih"):
        client.fetch_current_rates()


def test_missing_supported_currency_raises_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    xml_text = _rates_xml(gbp_xml="")
    _install_fake_client(monkeypatch, [_make_text_response(200, xml_text)])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)

    with pytest.raises(TcmbClientError, match="GBP"):
        client.fetch_current_rates()


@pytest.mark.parametrize(
    ("usd_xml", "expected_message"),
    [
        (_currency_xml("USD", unit=""), "Unit"),
        (_currency_xml("USD", unit="abc"), "Unit"),
        (_currency_xml("USD", unit="0"), "Unit"),
        (_currency_xml("USD", forex_buying=""), "ForexBuying"),
        (_currency_xml("USD", forex_buying="abc"), "ForexBuying"),
        (_currency_xml("USD", forex_buying="0"), "ForexBuying"),
        (_currency_xml("USD", forex_buying="-1.00000000"), "ForexBuying"),
        (_currency_xml("USD", forex_selling=""), "ForexSelling"),
        (_currency_xml("USD", forex_selling="abc"), "ForexSelling"),
        (_currency_xml("USD", forex_selling="0"), "ForexSelling"),
        (_currency_xml("USD", forex_selling="-1.00000000"), "ForexSelling"),
    ],
)
def test_missing_invalid_or_non_positive_supported_currency_data_raises_client_error(
    monkeypatch: pytest.MonkeyPatch,
    usd_xml: str,
    expected_message: str,
) -> None:
    _install_fake_client(monkeypatch, [_make_text_response(200, _rates_xml(usd_xml=usd_xml))])
    client = TcmbClient(base_url="https://example.test", timeout_seconds=5, max_retries=0, retry_wait_seconds=0)

    with pytest.raises(TcmbClientError, match=expected_message):
        client.fetch_current_rates()


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"base_url": ""}, "base_url"),
        ({"base_url": "   "}, "base_url"),
        ({"timeout_seconds": 0}, "timeout_seconds"),
        ({"timeout_seconds": -1}, "timeout_seconds"),
        ({"max_retries": -1}, "max_retries"),
        ({"retry_wait_seconds": -0.1}, "retry_wait_seconds"),
    ],
)
def test_invalid_constructor_values_raise_value_error(kwargs: dict[str, Any], expected_message: str) -> None:
    constructor_kwargs = {
        "base_url": "https://example.test",
        "timeout_seconds": 5,
        "max_retries": 1,
        "retry_wait_seconds": 1,
    }
    constructor_kwargs.update(kwargs)

    with pytest.raises(ValueError, match=expected_message):
        TcmbClient(**constructor_kwargs)


def test_invalid_tcmb_settings_values_raise_validation_error() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, tcmb_timeout_seconds=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, tcmb_max_retries=-1)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, tcmb_retry_wait_seconds=-1)