from __future__ import annotations

import json
import sys
from pathlib import Path
from time import perf_counter

import httpx


TEFAS_URL = "https://www.tefas.gov.tr/api/funds/fonGnlBlgSiraliGetir"

# İlk test: AAK fonu, 30 Temmuz 2026
FUND_CODE = "AAL"
START_DATE = "20260401"
END_DATE = "20260424"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_ROOT / "docs" / "sample_tefas_aal_date_range.json"


def main() -> int:
    headers = {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://www.tefas.gov.tr",
        "Referer": "https://www.tefas.gov.tr/tr/fon-verileri",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/146.0.0.0 Safari/537.36"
        ),
    }

    payload = {
        "fonTipi": "YAT",
        "fonKodu": FUND_CODE,
        "aramaMetni": None,
        "fonTurKod": None,
        "fonGrubu": None,
        "sfonTurKod": None,
        "fonTurAciklama": None,
        "kurucuKod": None,
        "basTarih": START_DATE,
        "bitTarih": END_DATE,
        "basSira": 1,
        "bitSira": 100000,
        "dil": "TR",
        "sFonTurKod": "",
        "fonKod": "",
        "fonGrup": "",
        "fonUnvanTip": "",
    }

    started_at = perf_counter()

    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.post(
                TEFAS_URL,
                headers=headers,
                json=payload,
            )

        duration_seconds = perf_counter() - started_at

        print(f"HTTP status: {response.status_code}")
        print(f"Duration: {duration_seconds:.2f} seconds")

        response.raise_for_status()
        response_data = response.json()

    except httpx.HTTPError as exc:
        print(f"HTTP request failed: {exc}")
        return 1

    except ValueError as exc:
        print(f"Response is not valid JSON: {exc}")
        return 1

    if not isinstance(response_data, dict):
        print("Unexpected response format: JSON object was expected.")
        return 1

    result_list = response_data.get("resultList") or []

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(response_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Record count: {len(result_list)}")
    print(f"Raw response saved to: {OUTPUT_PATH}")

    error_code = response_data.get("errorCode")
    error_message = response_data.get("errorMessage")

    if error_code or error_message:
        print(f"TEFAS error code: {error_code}")
        print(f"TEFAS error message: {error_message}")

    if result_list and isinstance(result_list[0], dict):
        field_names = sorted(result_list[0].keys())
        print("First record fields:")
        print(", ".join(field_names))
    else:
        print("No records were returned.")

    return 0


if __name__ == "__main__":
    sys.exit(main())