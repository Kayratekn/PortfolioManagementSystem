from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import httpx
import pytest
from pydantic import ValidationError

from src.config import dependencies
from src.config.settings import Settings, get_settings
from src.integrations import ai_client as ai_client_module
from src.integrations.ai_client import (
    AiClient,
    AiServiceRequestError,
    AiServiceResponseError,
    AiServiceUnavailableError,
)


Handler = Callable[[httpx.Request], httpx.Response]


def _install_mock_transport(
    monkeypatch: pytest.MonkeyPatch,
    handler: Handler,
) -> tuple[list[httpx.Request], list[dict[str, Any]]]:
    requests: list[httpx.Request] = []
    client_kwargs: list[dict[str, Any]] = []
    transport = httpx.MockTransport(lambda request: _handle_request(requests, handler, request))
    real_client = httpx.Client

    def fake_client_factory(**kwargs: Any) -> httpx.Client:
        client_kwargs.append(kwargs)
        return real_client(transport=transport, **kwargs)

    monkeypatch.setattr(ai_client_module.httpx, "Client", fake_client_factory)
    return requests, client_kwargs


def _handle_request(
    requests: list[httpx.Request],
    handler: Handler,
    request: httpx.Request,
) -> httpx.Response:
    requests.append(request)
    return handler(request)


def _json_response(status_code: int, value: Any) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(value).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


def test_settings_defaults_for_ai_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AI_SERVICE_URL", raising=False)
    monkeypatch.delenv("AI_TIMEOUT_SECONDS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ai_service_url == "http://127.0.0.1:8001"
    assert settings.ai_timeout_seconds == 15.0


def test_constructor_loads_ai_overrides_from_settings_when_arguments_are_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("AI_SERVICE_URL", "https://ai.example.test/")
    monkeypatch.setenv("AI_TIMEOUT_SECONDS", "9.5")

    try:
        client = AiClient(base_url=None, timeout_seconds=None)

        assert client.base_url == "https://ai.example.test"
        assert client.timeout_seconds == 9.5
    finally:
        get_settings.cache_clear()


def test_base_url_trailing_slash_is_normalized() -> None:
    client = AiClient(base_url="https://ai.example.test/", timeout_seconds=5)

    assert client.base_url == "https://ai.example.test"


@pytest.mark.parametrize("base_url", ["", "   "])
def test_blank_base_url_is_rejected(base_url: str) -> None:
    with pytest.raises(ValueError, match="base_url"):
        AiClient(base_url=base_url, timeout_seconds=5)


@pytest.mark.parametrize("timeout_seconds", [0, -1])
def test_non_positive_timeout_is_rejected(timeout_seconds: float) -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        AiClient(base_url="https://ai.example.test", timeout_seconds=timeout_seconds)


@pytest.mark.parametrize("timeout_seconds", [0, -1])
def test_invalid_ai_settings_timeout_is_rejected(timeout_seconds: float) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, ai_timeout_seconds=timeout_seconds)


def test_successful_post_sends_expected_url_payload_headers_and_returns_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, {"ok": True, "score": "1.25"})

    requests, client_kwargs = _install_mock_transport(monkeypatch, handler)
    client = AiClient(base_url="https://ai.example.test/", timeout_seconds=7)

    result = client.post_json("/analyze", {"portfolio_id": 123})

    assert result == {"ok": True, "score": "1.25"}
    assert len(requests) == 1
    assert str(requests[0].url) == "https://ai.example.test/analyze"
    assert requests[0].method == "POST"
    assert requests[0].headers["content-type"] == "application/json"
    assert requests[0].headers["accept"] == "application/json"
    assert requests[0].read() == b'{"portfolio_id":123}'
    assert client_kwargs == [{"timeout": 7}]


@pytest.mark.parametrize(
    "error",
    [
        httpx.ReadTimeout("AI timeout"),
        httpx.ConnectError("AI unavailable"),
    ],
)
def test_timeout_and_network_errors_raise_unavailable_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    error: httpx.RequestError,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        error.request = request
        raise error

    requests, _ = _install_mock_transport(monkeypatch, handler)
    client = AiClient(base_url="https://ai.example.test", timeout_seconds=5)

    with pytest.raises(AiServiceUnavailableError):
        client.post_json("/analyze", {"x": 1})

    assert len(requests) == 1


@pytest.mark.parametrize("status_code", [500, 503])
def test_server_errors_raise_unavailable_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    requests, _ = _install_mock_transport(
        monkeypatch,
        lambda request: httpx.Response(status_code=status_code, text="server failure"),
    )
    client = AiClient(base_url="https://ai.example.test", timeout_seconds=5)

    with pytest.raises(AiServiceUnavailableError):
        client.post_json("/analyze", {"x": 1})

    assert len(requests) == 1


@pytest.mark.parametrize("status_code", [400, 422])
def test_client_errors_raise_request_error_with_status_code_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
) -> None:
    requests, _ = _install_mock_transport(
        monkeypatch,
        lambda request: httpx.Response(status_code=status_code, text="bad request"),
    )
    client = AiClient(base_url="https://ai.example.test", timeout_seconds=5)

    with pytest.raises(AiServiceRequestError) as exc_info:
        client.post_json("/analyze", {"x": 1})

    assert exc_info.value.status_code == status_code
    assert len(requests) == 1


def test_invalid_json_raises_response_error_without_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    requests, _ = _install_mock_transport(
        monkeypatch,
        lambda request: httpx.Response(status_code=200, content=b"not-json"),
    )
    client = AiClient(base_url="https://ai.example.test", timeout_seconds=5)

    with pytest.raises(AiServiceResponseError, match="invalid JSON"):
        client.post_json("/analyze", {"x": 1})

    assert len(requests) == 1


@pytest.mark.parametrize("response_value", [["not", "dict"], "text", 1, None])
def test_non_object_json_raises_response_error_without_retry(
    monkeypatch: pytest.MonkeyPatch,
    response_value: Any,
) -> None:
    requests, _ = _install_mock_transport(
        monkeypatch,
        lambda request: _json_response(200, response_value),
    )
    client = AiClient(base_url="https://ai.example.test", timeout_seconds=5)

    with pytest.raises(AiServiceResponseError, match="unexpected JSON response"):
        client.post_json("/analyze", {"x": 1})

    assert len(requests) == 1


def test_dependency_returns_configured_ai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        _env_file=None,
        ai_service_url="https://dependency-ai.example.test/",
        ai_timeout_seconds=6.5,
    )
    monkeypatch.setattr(dependencies, "get_settings", lambda: settings)

    client = dependencies.get_ai_client()

    assert isinstance(client, AiClient)
    assert client.base_url == "https://dependency-ai.example.test"
    assert client.timeout_seconds == 6.5


def test_ai_client_source_does_not_use_fastapi_http_exception() -> None:
    source = Path("src/integrations/ai_client.py").read_text(encoding="utf-8")

    assert "HTTPException" not in source
    assert "fastapi" not in source.lower()