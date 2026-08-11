from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from typing import Any

from src.integrations.tefas_client import CustomTefasClient, FundKind


FUND_KINDS: tuple[FundKind, ...] = ("YAT", "EMK", "BYF", "GYF", "GSYF")
METADATA_FIELDS: set[str] = {"fonKodu", "fonUnvan", "tarih", "bilFiyat"}
RESOLVED_FIELDS: set[str] = {
    "hs",
    "gyy",
    "gsyy",
    "yyf",
    "tr",
    "vmtl",
    "dt",
    "fb",
    "vdm",
    "ost",
    "tpp",
    "kkstl",
    "osks",
    "gsykb",
    "gykb",
    "byf",
    "d",
    "kba",
    "khd",
    "kksd",
    "kibd",
    "vmd",
    "ybosb",
    "osdb",
    "km",
    "kmbyf",
    "kmkba",
    "kmkks",
    "vint",
    "yhs",
    "btas",
    "khau",
    "khtl",
    "ybyf",
    "hb",
    "r",
    "oksyd",
    "gas",
    "bpp",
    "ybkb",
    "kksyd",
    "btaa",
    "vmau",
}


def configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid --date value '{value}'. Expected YYYY-MM-DD."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find TEFAS portfolio rows that are useful for mapping unresolved fields."
    )
    parser.add_argument(
        "--date",
        required=True,
        type=parse_date,
        help="Probe date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--top",
        required=True,
        type=int,
        help="Number of top candidate funds to print per fund kind.",
    )
    return parser.parse_args()


def is_non_helpful_zero(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return value == 0
    return False


def find_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result_list = payload.get("resultList")
    if isinstance(result_list, list):
        return [row for row in result_list if isinstance(row, dict)]

    for value in payload.values():
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    return []


def collect_unresolved_fields(row: dict[str, Any]) -> dict[str, Any]:
    unresolved_fields: dict[str, Any] = {}
    for key, value in row.items():
        if key in METADATA_FIELDS or key in RESOLVED_FIELDS:
            continue
        if value is None or is_non_helpful_zero(value):
            continue
        unresolved_fields[key] = value
    return unresolved_fields


def build_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        unresolved_fields = collect_unresolved_fields(row)
        if not unresolved_fields:
            continue
        candidates.append(
            {
                "fonKodu": row.get("fonKodu"),
                "fonUnvan": row.get("fonUnvan"),
                "unresolved_non_null_count": len(unresolved_fields),
                "unresolved_fields": unresolved_fields,
            }
        )

    return sorted(
        candidates,
        key=lambda item: (
            -item["unresolved_non_null_count"],
            str(item["fonKodu"] or ""),
        ),
    )


def print_candidates(*, fund_kind: FundKind, candidates: list[dict[str, Any]], top_n: int) -> None:
    print(f"fund_kind: {fund_kind}")
    if not candidates:
        print("no_candidates: true")
        print()
        return

    for candidate in candidates[:top_n]:
        print(f"fonKodu: {candidate['fonKodu']}")
        print(f"fonUnvan: {candidate['fonUnvan']}")
        print(f"unresolved_non_null_count: {candidate['unresolved_non_null_count']}")
        print("unresolved_fields:")
        print(json.dumps(candidate["unresolved_fields"], ensure_ascii=False, indent=2, default=str))
        print()


def main() -> int:
    configure_stdout()
    args = parse_args()
    if args.top <= 0:
        raise SystemExit("--top must be greater than 0.")

    client = CustomTefasClient()

    for fund_kind in FUND_KINDS:
        try:
            payload = client.fetch_portfolio_breakdown(
                start_date=args.date,
                end_date=args.date,
                fund_kind=fund_kind,
            )
        except Exception as exc:
            print(f"fund_kind: {fund_kind}")
            print("status: failed")
            print(f"error_message: {exc}")
            print()
            continue

        rows = find_rows(payload)
        candidates = build_candidates(rows)
        print_candidates(fund_kind=fund_kind, candidates=candidates, top_n=args.top)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
