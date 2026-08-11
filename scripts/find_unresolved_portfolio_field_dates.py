from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from numbers import Real
from typing import Any

from src.integrations.tefas_client import CustomTefasClient, FundKind


FUND_KINDS: tuple[FundKind, ...] = ("YAT", "EMK", "BYF", "GYF", "GSYF")
UNRESOLVED_FIELDS: tuple[str, ...] = (
    "bb",
    "db",
    "dot",
    "eut",
    "fkb",
    "kh",
    "kks",
    "t",
    "vm",
    "yba",
    "ymk",
)


def configure_stdout() -> None:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        reconfigure(encoding="utf-8")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid date value '{value}'. Expected YYYY-MM-DD."
        ) from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find dates and funds with non-zero values for unresolved TEFAS portfolio fields."
    )
    parser.add_argument("--start-date", required=True, type=parse_date)
    parser.add_argument("--end-date", required=True, type=parse_date)
    parser.add_argument("--step-days", required=True, type=int)
    parser.add_argument("--max-results-per-field", required=True, type=int)
    return parser.parse_args()


def iter_scan_dates(*, start_date: date, end_date: date, step_days: int) -> list[date]:
    scan_dates: list[date] = []
    current_date = start_date
    while current_date <= end_date:
        scan_dates.append(current_date)
        current_date += timedelta(days=step_days)
    return scan_dates


def find_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result_list = payload.get("resultList")
    if isinstance(result_list, list):
        return [row for row in result_list if isinstance(row, dict)]

    for value in payload.values():
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]

    return []


def is_numeric_non_zero(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if not isinstance(value, Real):
        return False
    return value != 0


def record_examples(
    *,
    examples_by_field: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
    scan_date: date,
    fund_kind: FundKind,
    max_results_per_field: int,
) -> None:
    for row in rows:
        for field in UNRESOLVED_FIELDS:
            if len(examples_by_field[field]) >= max_results_per_field:
                continue

            value = row.get(field)
            if not is_numeric_non_zero(value):
                continue

            examples_by_field[field].append(
                {
                    "field": field,
                    "value": value,
                    "date": scan_date.isoformat(),
                    "fund_kind": fund_kind,
                    "fonKodu": row.get("fonKodu"),
                    "fonUnvan": row.get("fonUnvan"),
                }
            )


def all_fields_satisfied(*, examples_by_field: dict[str, list[dict[str, Any]]], max_results_per_field: int) -> bool:
    return all(len(examples_by_field[field]) >= max_results_per_field for field in UNRESOLVED_FIELDS)


def print_results(*, examples_by_field: dict[str, list[dict[str, Any]]], failures: list[dict[str, str]]) -> None:
    for field in UNRESOLVED_FIELDS:
        print(f"field: {field}")
        examples = examples_by_field[field]
        if not examples:
            print("examples: []")
            print()
            continue

        print("examples:")
        print(json.dumps(examples, ensure_ascii=False, indent=2, default=str))
        print()

    print("failures:")
    if not failures:
        print("[]")
    else:
        print(json.dumps(failures, ensure_ascii=False, indent=2))


def main() -> int:
    configure_stdout()
    args = parse_args()

    if args.start_date > args.end_date:
        raise SystemExit("--start-date cannot be later than --end-date.")
    if args.step_days <= 0:
        raise SystemExit("--step-days must be greater than 0.")
    if args.max_results_per_field <= 0:
        raise SystemExit("--max-results-per-field must be greater than 0.")

    client = CustomTefasClient()
    examples_by_field: dict[str, list[dict[str, Any]]] = {field: [] for field in UNRESOLVED_FIELDS}
    failures: list[dict[str, str]] = []

    for scan_date in iter_scan_dates(
        start_date=args.start_date,
        end_date=args.end_date,
        step_days=args.step_days,
    ):
        for fund_kind in FUND_KINDS:
            try:
                payload = client.fetch_portfolio_breakdown(
                    start_date=scan_date,
                    end_date=scan_date,
                    fund_kind=fund_kind,
                )
            except Exception as exc:
                failures.append(
                    {
                        "date": scan_date.isoformat(),
                        "fund_kind": fund_kind,
                        "error_message": str(exc),
                    }
                )
                continue

            rows = find_rows(payload)
            record_examples(
                examples_by_field=examples_by_field,
                rows=rows,
                scan_date=scan_date,
                fund_kind=fund_kind,
                max_results_per_field=args.max_results_per_field,
            )

        if all_fields_satisfied(
            examples_by_field=examples_by_field,
            max_results_per_field=args.max_results_per_field,
        ):
            break

    print_results(examples_by_field=examples_by_field, failures=failures)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
