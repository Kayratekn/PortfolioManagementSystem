from __future__ import annotations

import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_PATH = PROJECT_ROOT / "docs" / "sample_tefas_aal_single_day.json"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "sample_tefas_aal_single_day.csv"


FIELD_MAPPING = {
    "fonKodu": "fund_code",
    "fonUnvan": "fund_name",
    "tarih": "data_date",
    "fiyat": "price",
    "tedPaySayisi": "shares_outstanding",
    "kisiSayisi": "investor_count",
    "portfoyBuyukluk": "portfolio_size",
    "borsaBultenFiyat": "exchange_bulletin_price",
}


def main() -> None:
    response = json.loads(INPUT_PATH.read_text(encoding="utf-8"))
    rows = response.get("resultList") or []

    normalized_rows = []

    for row in rows:
        normalized = {
            normalized_field: row.get(tefas_field)
            for tefas_field, normalized_field in FIELD_MAPPING.items()
        }
        normalized["fund_kind"] = "YAT"
        normalized_rows.append(normalized)

    fieldnames = [
        "fund_code",
        "fund_name",
        "fund_kind",
        "data_date",
        "price",
        "shares_outstanding",
        "investor_count",
        "portfolio_size",
        "exchange_bulletin_price",
    ]

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(normalized_rows)

    print(f"Record count: {len(normalized_rows)}")
    print(f"CSV saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()