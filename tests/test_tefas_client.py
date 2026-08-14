from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from src.config.settings import get_settings
from src.integrations import tefas_client as tefas_client_module
from src.integrations.tefas_client import CustomTefasClient, TefasClientError


class FakeHttpxClient:
    def __init__(self, outcomes: list[Any], calls: list[dict[str, Any]], **kwargs: Any) -> None:
        self.outcomes = outcomes
        self.calls = calls
        self.kwargs = kwargs

    def __enter__(self) -> FakeHttpxClient:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    def post(self, url: str, *, headers: dict[str, str], json: dict[str, Any]) -> Any:
        self.calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "client_kwargs": self.kwargs,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

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


class FakeJsonErrorResponse:
    def __init__(self) -> None:
        self.status_code = 200
        self.request = httpx.Request("POST", "https://example.test/api")

    def json(self) -> Any:
        raise ValueError("invalid json")


def _make_response(status_code: int, json_data: Any) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("POST", "https://example.test/api"),
    )


def _install_fake_client(monkeypatch: pytest.MonkeyPatch, outcomes: list[Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_client_factory(**kwargs: Any) -> FakeHttpxClient:
        return FakeHttpxClient(outcomes, calls, **kwargs)

    monkeypatch.setattr(tefas_client_module.httpx, "Client", fake_client_factory)
    return calls


def _install_fake_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleep_calls: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(tefas_client_module.time, "sleep", fake_sleep)
    return sleep_calls


def test_constructor_stores_explicit_values_and_trims_trailing_slash() -> None:
    client = CustomTefasClient(
        base_url="https://example.test/",
        timeout_seconds=12.5,
        max_retries=0,
        retry_wait_seconds=0,
    )

    assert client.base_url == "https://example.test"
    assert client.timeout_seconds == 12.5
    assert client.max_retries == 0
    assert client.retry_wait_seconds == 0
    assert client.headers["Origin"] == "https://example.test"
    assert client.headers["Referer"] == "https://example.test/tr/fon-verileri"



def test_constructor_loads_defaults_from_settings_when_arguments_are_none(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("TEFAS_BASE_URL", "https://example.test/")
    monkeypatch.setenv("TEFAS_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("TEFAS_MAX_RETRIES", "2")
    monkeypatch.setenv("TEFAS_RETRY_WAIT_SECONDS", "4")

    try:
        client = CustomTefasClient(
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



def test_successful_first_request_performs_one_post_and_does_not_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_response(200, {"ok": True})])
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=2, retry_wait_seconds=3)

    result = client.fetch_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    assert result == {"ok": True}
    assert len(calls) == 1
    assert sleep_calls == []



def test_request_error_followed_by_success_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.test/api")
    outcomes = [
        httpx.RequestError("temporary network error", request=request),
        _make_response(200, {"ok": True}),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=2, retry_wait_seconds=7)

    result = client.fetch_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    assert result == {"ok": True}
    assert len(calls) == 2
    assert sleep_calls == [7]



def test_http_500_followed_by_success_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = [
        _make_response(500, {"error": "server"}),
        _make_response(200, {"ok": True}),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=1, retry_wait_seconds=2)

    result = client.fetch_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    assert result == {"ok": True}
    assert len(calls) == 2
    assert sleep_calls == [2]



def test_http_429_followed_by_success_is_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    outcomes = [
        _make_response(429, {"error": "rate limited"}),
        _make_response(200, {"ok": True}),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=1, retry_wait_seconds=6)

    result = client.fetch_general_info(
        start_date=date(2026, 4, 24),
        end_date=date(2026, 4, 24),
    )

    assert result == {"ok": True}
    assert len(calls) == 2
    assert sleep_calls == [6]



def test_http_400_is_not_retried_and_raises_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_response(400, {"error": "bad request"})])
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=3, retry_wait_seconds=6)

    with pytest.raises(TefasClientError, match="400"):
        client.fetch_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )

    assert len(calls) == 1
    assert sleep_calls == []



def test_transient_failures_exceeding_max_retries_raise_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    request = httpx.Request("POST", "https://example.test/api")
    outcomes = [
        httpx.RequestError("temporary failure 1", request=request),
        httpx.RequestError("temporary failure 2", request=request),
        httpx.RequestError("temporary failure 3", request=request),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=2, retry_wait_seconds=9)

    with pytest.raises(TefasClientError, match="temporary failure 3"):
        client.fetch_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )

    assert len(calls) == 3
    assert sleep_calls == [9, 9]



def test_invalid_json_raises_client_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [FakeJsonErrorResponse()])
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=3, retry_wait_seconds=1)

    with pytest.raises(TefasClientError, match="invalid JSON"):
        client.fetch_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )

    assert len(calls) == 1
    assert sleep_calls == []



def test_unexpected_json_response_type_raises_client_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_response(200, ["unexpected", "list"])])
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(base_url="https://example.test", timeout_seconds=5, max_retries=3, retry_wait_seconds=1)

    with pytest.raises(TefasClientError, match="Unexpected TEFAS response format"):
        client.fetch_general_info(
            start_date=date(2026, 4, 24),
            end_date=date(2026, 4, 24),
        )

    assert len(calls) == 1
    assert sleep_calls == []


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
        CustomTefasClient(**constructor_kwargs)


def test_fetch_fund_profile_detail_posts_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_response(200, {"ok": True})])
    client = CustomTefasClient(
        base_url="https://example.test",
        timeout_seconds=5,
        max_retries=0,
        retry_wait_seconds=0,
    )

    result = client.fetch_fund_profile_detail(fund_code=" aal ")

    assert result == {"ok": True}
    assert len(calls) == 1
    assert calls[0]["url"] == "https://example.test/api/funds/fonProfilDtyGetir"
    assert calls[0]["json"] == {
        "dil": "TR",
        "fonKodu": "AAL",
        "periyod": "12",
    }

def _make_text_response(status_code: int, text: str) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        text=text,
        request=httpx.Request("GET", "https://example.test/tr/fon-detayli-analiz/AAL"),
    )


def test_fetch_fund_detail_analysis_page_gets_expected_url(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_fake_client(monkeypatch, [_make_text_response(200, "<html>ok</html>")])
    client = CustomTefasClient(
        base_url="https://example.test",
        timeout_seconds=5,
        max_retries=0,
        retry_wait_seconds=0,
    )

    result = client.fetch_fund_detail_analysis_page(fund_code=" aal ")

    assert result == "<html>ok</html>"
    assert len(calls) == 1
    assert calls[0]["url"] == "https://example.test/tr/fon-detayli-analiz/AAL"
    assert "headers" not in calls[0]
    assert "json" not in calls[0]


def test_fetch_fund_detail_analysis_page_retries_transient_get_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = httpx.Request("GET", "https://example.test/tr/fon-detayli-analiz/AAL")
    outcomes = [
        httpx.RequestError("temporary network error", request=request),
        _make_text_response(200, "<html>ok</html>"),
    ]
    calls = _install_fake_client(monkeypatch, outcomes)
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(
        base_url="https://example.test",
        timeout_seconds=5,
        max_retries=1,
        retry_wait_seconds=2,
    )

    result = client.fetch_fund_detail_analysis_page(fund_code="AAL")

    assert result == "<html>ok</html>"
    assert len(calls) == 2
    assert sleep_calls == [2]


def test_fetch_fund_detail_analysis_page_http_404_is_not_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = _install_fake_client(monkeypatch, [_make_text_response(404, "not found")])
    sleep_calls = _install_fake_sleep(monkeypatch)
    client = CustomTefasClient(
        base_url="https://example.test",
        timeout_seconds=5,
        max_retries=2,
        retry_wait_seconds=2,
    )

    with pytest.raises(TefasClientError, match="404"):
        client.fetch_fund_detail_analysis_page(fund_code="AAL")

    assert len(calls) == 1
    assert sleep_calls == []
