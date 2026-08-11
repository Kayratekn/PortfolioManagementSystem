from __future__ import annotations

import re
from collections import defaultdict
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urljoin, urlparse

import httpx

from src.integrations.tefas_client import CustomTefasClient


PAGE_PATHS: tuple[str, ...] = (
    "/tr/fon-verileri",
    "/tr/fon-detayli-analiz/IAY",
)

ENDPOINT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?P<value>/api/[A-Za-z0-9_./?-]+)"),
    re.compile(r"(?P<value>api/[A-Za-z0-9_./?-]+)"),
)

INTERESTING_STRING_PATTERN = re.compile(
    r"(?P<quote>['\"])"
    r"(?P<value>[^'\"\r\n]*(?:Getir|getiri|fon|dagilim)[^'\"\r\n]*)"
    r"(?P=quote)",
    re.IGNORECASE,
)


class ScriptSrcParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.script_sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "script":
            return

        for name, value in attrs:
            if name.lower() == "src" and value:
                self.script_sources.append(value)
                return


def normalize_asset_url(*, base_url: str, asset_ref: str) -> str | None:
    absolute_url = urljoin(base_url, asset_ref)
    parsed_url = urlparse(absolute_url)
    parsed_base = urlparse(base_url)

    if parsed_url.scheme not in {"http", "https"}:
        return None

    if parsed_url.netloc != parsed_base.netloc:
        return None

    return absolute_url


def fetch_text(*, client: httpx.Client, url: str) -> tuple[bool, str]:
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        return False, str(exc)

    return True, response.text


def collect_script_urls(*, page_url: str, html: str) -> list[str]:
    parser = ScriptSrcParser()
    parser.feed(html)

    script_urls: list[str] = []
    seen: set[str] = set()
    for script_src in parser.script_sources:
        normalized_url = normalize_asset_url(base_url=page_url, asset_ref=script_src)
        if normalized_url is None or normalized_url in seen:
            continue
        seen.add(normalized_url)
        script_urls.append(normalized_url)

    return script_urls


def clean_match(value: str) -> str:
    return value.strip().rstrip(".,;:)\"]}'")


def collect_endpoint_matches(text: str) -> set[str]:
    matches: set[str] = set()
    for pattern in ENDPOINT_PATTERNS:
        for match in pattern.finditer(text):
            value = clean_match(match.group("value"))
            if value.startswith("api/"):
                value = f"/{value}"
            if value.startswith("/api/"):
                matches.add(value)
    return matches


def looks_like_interesting_string(value: str) -> bool:
    normalized_value = value.strip()
    if not normalized_value:
        return False
    if normalized_value.startswith("http://") or normalized_value.startswith("https://"):
        return False
    if normalized_value.startswith("/") and "/api/" in normalized_value:
        return False
    if normalized_value.startswith("api/"):
        return False
    return True


def collect_interesting_strings(text: str) -> set[str]:
    matches: set[str] = set()
    for match in INTERESTING_STRING_PATTERN.finditer(text):
        value = clean_match(match.group("value"))
        if looks_like_interesting_string(value):
            matches.add(value)
    return matches


def print_results(
    *,
    endpoints_by_source: dict[str, set[str]],
    interesting_by_source: dict[str, set[str]],
    failures: list[tuple[str, str]],
) -> None:
    print("Discovered endpoint-like paths:")
    if endpoints_by_source:
        for endpoint in sorted(endpoints_by_source):
            sources = ", ".join(sorted(endpoints_by_source[endpoint]))
            print(f"- {endpoint} | sources: {sources}")
    else:
        print("- None")

    print()
    print("Interesting API-like strings needing manual classification:")
    if interesting_by_source:
        for value in sorted(interesting_by_source):
            sources = ", ".join(sorted(interesting_by_source[value]))
            print(f"- {value} | sources: {sources}")
    else:
        print("- None")

    print()
    print("Fetch failures:")
    if failures:
        for source, error_message in failures:
            print(f"- {source}: {error_message}")
    else:
        print("- None")


def add_matches(
    *,
    text: str,
    source: str,
    endpoints_by_source: dict[str, set[str]],
    interesting_by_source: dict[str, set[str]],
) -> None:
    for endpoint in collect_endpoint_matches(text):
        endpoints_by_source[endpoint].add(source)

    for value in collect_interesting_strings(text):
        interesting_by_source[value].add(source)


def iter_sources(*, page_url: str, html: str, script_urls: Iterable[str]) -> Iterable[tuple[str, str]]:
    yield page_url, html
    for script_url in script_urls:
        yield script_url, script_url


def main() -> int:
    tefas_client = CustomTefasClient()
    endpoints_by_source: dict[str, set[str]] = defaultdict(set)
    interesting_by_source: dict[str, set[str]] = defaultdict(set)
    failures: list[tuple[str, str]] = []

    with httpx.Client(
        timeout=tefas_client.timeout_seconds,
        follow_redirects=True,
        headers=tefas_client.headers,
    ) as client:
        for page_path in PAGE_PATHS:
            page_url = f"{tefas_client.base_url}{page_path}"
            ok, html_or_error = fetch_text(client=client, url=page_url)
            if not ok:
                failures.append((page_url, html_or_error))
                continue

            html = html_or_error
            add_matches(
                text=html,
                source=page_url,
                endpoints_by_source=endpoints_by_source,
                interesting_by_source=interesting_by_source,
            )

            for script_url in collect_script_urls(page_url=page_url, html=html):
                ok, script_or_error = fetch_text(client=client, url=script_url)
                if not ok:
                    failures.append((script_url, script_or_error))
                    continue

                add_matches(
                    text=script_or_error,
                    source=script_url,
                    endpoints_by_source=endpoints_by_source,
                    interesting_by_source=interesting_by_source,
                )

    print_results(
        endpoints_by_source=endpoints_by_source,
        interesting_by_source=interesting_by_source,
        failures=failures,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
