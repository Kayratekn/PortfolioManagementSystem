from datetime import date
from decimal import Decimal

import httpx
import pytest

from src.integrations.borsa_istanbul_current_reference_prices_client import (
    BorsaIstanbulCurrentReferencePricesClient,
    BorsaIstanbulCurrentReferencePricesClientError,
)


def xml(*, day="08.09.2026", gold="6.830.296,91", silver="103.103,93", platinum="2.800.000,00", extra="<paladyumdeger>2.413.521,01</paladyumdeger>"):
    return f'''<?xml version="1.0" encoding="utf-8"?>
<IGE><IGE_GUN><gun>{day}</gun></IGE_GUN><TL><altindeger>{gold}</altindeger><gumusdeger>{silver}</gumusdeger><platindeger>{platinum}</platindeger>{extra}</TL></IGE>'''.encode()


def client(handler, *, retries=0):
    return BorsaIstanbulCurrentReferencePricesClient(
        transport=httpx.MockTransport(handler),
        max_retries=retries,
        sleep=lambda _: None,
    )


def test_exact_get_contract_and_exact_turkish_decimal_mapping():
    seen = {}
    def handler(request):
        seen["method"] = request.method
        seen["url"] = request.url
        seen["headers"] = request.headers
        return httpx.Response(200, headers={"content-type": "application/xml; charset=utf-8"}, content=xml())

    snapshot = client(handler).fetch_current()

    assert seen["method"] == "GET"
    assert str(seen["url"]).startswith(BorsaIstanbulCurrentReferencePricesClient.ENDPOINT)
    assert dict(seen["url"].params) == {"op": "generateReferansFiyatlariXML"}
    assert seen["headers"]["accept"] == "application/xml"
    assert "authorization" not in seen["headers"] and "cookie" not in seen["headers"]
    assert snapshot.effective_date == date(2026, 9, 8)
    assert snapshot.gold_raw_try_per_kg == Decimal("6830296.91")
    assert snapshot.silver_raw_try_per_kg == Decimal("103103.93")
    assert snapshot.platinum_raw_try_per_kg == Decimal("2800000.00")
    assert all(isinstance(value, Decimal) for value in (snapshot.gold_raw_try_per_kg, snapshot.silver_raw_try_per_kg, snapshot.platinum_raw_try_per_kg))


def test_ungrouped_turkish_decimal_is_accepted_exactly():
    def handler(_): return httpx.Response(200, headers={"content-type": "text/xml"}, content=xml(gold="6830296,91", silver="103103,93", platinum="2800000,00"))
    snapshot = client(handler).fetch_current()
    assert snapshot.gold_raw_try_per_kg == Decimal("6830296.91")


@pytest.mark.parametrize("value", ["", " ", "6.83.296,91", "6.830.296.91", "6,830,296.91", "6830296.91", "6.830,296,91", "0,00", "-1,00", "NaN", "Infinity"])
def test_malformed_or_nonpositive_turkish_decimal_is_rejected(value):
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml(gold=value))
    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError):
        client(handler).fetch_current()


@pytest.mark.parametrize("body", [b"bad xml", b"<OTHER/>", b"<!DOCTYPE IGE [<!ENTITY x 'x'>]><IGE/>"])
def test_malformed_unsafe_or_wrong_root_xml_is_rejected(body):
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml"}, content=body)
    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError):
        client(handler).fetch_current()


@pytest.mark.parametrize("change", [
    lambda value: value.replace(b"<altindeger>6.830.296,91</altindeger>", b""),
    lambda value: value.replace(b"</altindeger>", b"</altindeger><altindeger>1,00</altindeger>"),
    lambda value: value.replace(b"<IGE_GUN><gun>08.09.2026</gun></IGE_GUN>", b"<IGE_GUN><gun>08.09.2026</gun></IGE_GUN><IGE_GUN><gun>08.09.2026</gun></IGE_GUN>"),
    lambda value: value.replace(b"08.09.2026", b"2026-09-08"),
    lambda value: value.replace(b"<TL>", b"").replace(b"</TL>", b""),
])
def test_required_xml_elements_are_exactly_one_and_date_is_strict(change):
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml"}, content=change(xml()))
    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError):
        client(handler).fetch_current()


def test_palladium_and_unrelated_elements_are_ignored():
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml(extra="<paladyumdeger>2.413.521,01</paladyumdeger><futureField>ignored</futureField>"))
    assert client(handler).fetch_current().platinum_raw_try_per_kg == Decimal("2800000.00")


def test_non_2xx_network_and_content_type_failures_and_retries_are_bounded():
    attempts = []
    def failing(request):
        attempts.append(request)
        return httpx.Response(503, headers={"content-type": "application/xml"})
    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError):
        client(failing, retries=1).fetch_current()
    assert len(attempts) == 2

    def network(_): raise httpx.ReadTimeout("timeout")
    def non_xml(_): return httpx.Response(200, headers={"content-type": "text/html"}, content=b"x")
    for handler in (network, non_xml):
        with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError):
            client(handler).fetch_current()

def _internal_dtd_xml() -> bytes:
    return b'''<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE IGE [<!ENTITY snapshotDate "08.09.2026">]>
<IGE><IGE_GUN><gun>&snapshotDate;</gun></IGE_GUN><TL><altindeger>6.830.296,91</altindeger><gumusdeger>103.103,93</gumusdeger><platindeger>2.800.000,00</platindeger></TL></IGE>'''


def test_utf8_dtd_entity_is_rejected_before_elementtree_parsing(monkeypatch):
    import src.integrations.borsa_istanbul_current_reference_prices_client as module

    called = False
    def forbidden_parse(_):
        nonlocal called
        called = True
        raise AssertionError("ElementTree must not receive a DTD/entity document")
    monkeypatch.setattr(module.ElementTree, "fromstring", forbidden_parse)
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml; charset=utf-8"}, content=_internal_dtd_xml())

    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError, match="DTD or entity"):
        client(handler).fetch_current()
    assert called is False


def test_utf8_external_doctype_is_rejected_before_elementtree_parsing(monkeypatch):
    import src.integrations.borsa_istanbul_current_reference_prices_client as module

    monkeypatch.setattr(module.ElementTree, "fromstring", lambda _: (_ for _ in ()).throw(AssertionError()))
    external = b'<?xml version="1.0" encoding="utf-8"?><!DOCTYPE IGE SYSTEM "https://example.invalid/bist.dtd"><IGE/>'
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml; charset=utf-8"}, content=external)

    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError, match="DTD or entity"):
        client(handler).fetch_current()


def test_utf16_dtd_blocker_and_benign_utf16_are_rejected_before_elementtree(monkeypatch):
    import src.integrations.borsa_istanbul_current_reference_prices_client as module

    called = False
    def forbidden_parse(_):
        nonlocal called
        called = True
        raise AssertionError("ElementTree must not receive UTF-16 input")
    monkeypatch.setattr(module.ElementTree, "fromstring", forbidden_parse)
    utf16_dtd = '''<?xml version="1.0" encoding="UTF-16"?>
<!DOCTYPE IGE [<!ENTITY snapshotDate "08.09.2026">]>
<IGE><IGE_GUN><gun>&snapshotDate;</gun></IGE_GUN><TL><altindeger>6.830.296,91</altindeger><gumusdeger>103.103,93</gumusdeger><platindeger>2.800.000,00</platindeger></TL></IGE>'''.encode("utf-16")
    benign_utf16 = xml().decode("utf-8").replace("utf-8", "UTF-16").encode("utf-16")
    for body in (utf16_dtd, benign_utf16):
        def handler(_, response_body=body):
            return httpx.Response(200, headers={"content-type": "application/xml; charset=utf-8"}, content=response_body)
        with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError, match="UTF-8"):
            client(handler).fetch_current()
    assert called is False


def test_invalid_utf8_bytes_are_rejected_cleanly():
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml; charset=utf-8"}, content=b"\xff\xfe\x00")
    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError, match="valid UTF-8"):
        client(handler).fetch_current()


@pytest.mark.parametrize("content_type", ["application/xml; charset=utf-8", "Application/XML; Charset=UTF-8", "text/xml; charset=UtF-8"])
def test_utf8_content_type_variants_are_accepted(content_type):
    def handler(_): return httpx.Response(200, headers={"content-type": content_type}, content=xml())
    assert client(handler).fetch_current().effective_date == date(2026, 9, 8)


@pytest.mark.parametrize("content_type", ["application/xml; charset=utf-16", "application/xml; charset=iso-8859-9"])
def test_non_utf8_content_type_charset_is_rejected(content_type):
    def handler(_): return httpx.Response(200, headers={"content-type": content_type}, content=xml())
    with pytest.raises(BorsaIstanbulCurrentReferencePricesClientError, match="charset must be UTF-8"):
        client(handler).fetch_current()


def test_missing_content_type_charset_is_accepted_only_with_strict_utf8_body():
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml"}, content=xml())
    assert client(handler).fetch_current().effective_date == date(2026, 9, 8)

def test_verified_utf8_payload_with_xml_stylesheet_processing_instruction_is_accepted():
    body = b'''<?xml version="1.0" encoding="utf-8"?>
<?xml-stylesheet type="text/xsl" href="/xsl/kmtpRfrns.xsl"?>
<IGE><IGE_GUN><gun>08.09.2026</gun></IGE_GUN><TL><altindeger>6.830.296,91</altindeger><gumusdeger>103.103,93</gumusdeger><platindeger>2.800.000,00</platindeger><paladyumdeger>2.413.521,01</paladyumdeger></TL></IGE>'''
    def handler(_): return httpx.Response(200, headers={"content-type": "application/xml; charset=utf-8"}, content=body)
    snapshot = client(handler).fetch_current()
    assert snapshot.effective_date == date(2026, 9, 8)
    assert snapshot.gold_raw_try_per_kg == Decimal("6830296.91")