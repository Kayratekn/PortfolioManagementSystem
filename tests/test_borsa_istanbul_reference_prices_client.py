from datetime import date
from decimal import Decimal
import json

import httpx
import pytest

from src.integrations.borsa_istanbul_reference_prices_client import BorsaIstanbulReferencePricesClient, BorsaIstanbulReferencePricesClientError


def payload(*, source="api", price_value=6830296.91, **changes):
    row = {"id": 61329, "priceDate": "2026-09-08", "priceRef": "REF", "priceType": "AU", "priceCurrency": "TRY", "priceWeight": "KG", "priceValue": price_value, "extra": "ignored"}
    row.update(changes)
    return json.dumps({"status": "success", "source": source, "data": [row]})


def client(handler):
    return BorsaIstanbulReferencePricesClient(transport=httpx.MockTransport(handler), max_retries=0, sleep=lambda _: None)


def test_exact_get_contract_and_decimal_json_number():
    seen = {}
    def handler(request):
        seen["url"], seen["headers"] = request.url, request.headers
        return httpx.Response(200, headers={"content-type": "application/json; charset=utf-8"}, content=payload())
    value = client(handler).fetch_historical(start_date=date(2026,9,8), end_date=date(2026,9,8), provider_metal_code="AU")[0]
    assert dict(seen["url"].params) == {"op":"fetchReferansFiyatlari", "startDate":"2026-09-08", "endDate":"2026-09-08", "priceType":"AU"}
    assert seen["headers"]["accept"] == "application/json"
    assert seen["headers"]["x-requested-with"] == "XMLHttpRequest"
    assert "cookie" not in seen["headers"] and "authorization" not in seen["headers"]
    assert value.raw_try_per_kg == Decimal("6830296.91") and isinstance(value.raw_try_per_kg, Decimal)


@pytest.mark.parametrize("code", ["AU", "AG", "PT"])
@pytest.mark.parametrize("source", ["api", "redis"])
def test_provider_codes_and_informational_source_are_accepted(code, source):
    def handler(_): return httpx.Response(200, headers={"content-type":"application/json"}, content=payload(source=source, priceType=code, price_value=2800000))
    result = client(handler).fetch_historical(start_date=date(2026,9,8), end_date=date(2026,9,8), provider_metal_code=code)
    assert result[0].provider_metal_code == code and result[0].raw_try_per_kg == 2800000


@pytest.mark.parametrize("changes", [{"priceRef":"X"}, {"priceType":"AG"}, {"priceCurrency":"USD"}, {"priceWeight":"GRAM"}, {"priceDate":"bad"}, {"priceDate":"20260908"}, {"priceDate":"2026-09-09"}, {"priceValue":True}, {"priceValue":0}, {"priceValue":-1}, {"priceValue":"1"}])
def test_invalid_observations_are_rejected(changes):
    def handler(_): return httpx.Response(200, headers={"content-type":"application/json"}, content=payload(**changes))
    with pytest.raises(BorsaIstanbulReferencePricesClientError):
        client(handler).fetch_historical(start_date=date(2026,9,8), end_date=date(2026,9,8), provider_metal_code="AU")


@pytest.mark.parametrize("body", ["bad json", "[]", '{"status":"failed","data":[]}', '{"status":"success","data":{}}'])
def test_invalid_response_is_rejected(body):
    def handler(_): return httpx.Response(200, headers={"content-type":"application/json"}, content=body)
    with pytest.raises(BorsaIstanbulReferencePricesClientError): client(handler).fetch_historical(start_date=date(2026,9,8), end_date=date(2026,9,8), provider_metal_code="AU")


def test_empty_non_json_network_timeout_and_non_2xx():
    def empty(_): return httpx.Response(200, headers={"content-type":"application/json"}, content='{"status":"success","data":[]}')
    assert client(empty).fetch_historical(start_date=date(2026,9,8), end_date=date(2026,9,8), provider_metal_code="AU") == []
    def non_json(_): return httpx.Response(200, headers={"content-type":"text/html"}, content="x")
    def failed(_): return httpx.Response(503, headers={"content-type":"application/json"})
    def timeout(_): raise httpx.ReadTimeout("timeout")
    for handler in (non_json, failed, timeout):
        with pytest.raises(BorsaIstanbulReferencePricesClientError): client(handler).fetch_historical(start_date=date(2026,9,8), end_date=date(2026,9,8), provider_metal_code="AU")