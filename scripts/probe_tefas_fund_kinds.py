from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import date
from typing import Any

from src.integrations.tefas_client import CustomTefasClient, FundKind


FUND_KINDS: tuple[FundKind, ...] = ("YAT", "EMK", "BYF", "GYF", "GSYF")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Probe raw TEFAS responses for currently supported fund kinds."
    )
    parser.add_argument(
        "--date",
        required=True,
        type=parse_date,
        help="Probe date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--fund-code",
        help="Optional TEFAS fund code filter.",
    )
    return parser.parse_args()


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid --date value '{value}'. Expected YYYY-MM-DD."
        ) from exc


def find_rows(payload: dict[str, Any]) -> list[Any]:
    result_list = payload.get("resultList")
    if isinstance(result_list, list):
        return result_list

    for value in payload.values():
        if isinstance(value, list):
            return value

    return []


def collect_field_names(rows: list[Any]) -> list[str]:
    field_names: set[str] = set()
    for row in rows:
        if isinstance(row, dict):
            field_names.update(str(key) for key in row.keys())
    return sorted(field_names)


def get_sample_row(rows: list[Any]) -> Any | None:
    for row in rows:
        return row
    return None


def print_probe_result(
    *,
    fund_kind: FundKind,
    method_name: str,
    success: bool,
    payload: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    print(f"fund_kind: {fund_kind}")
    print(f"method: {method_name}")
    print(f"status: {'success' if success else 'failed'}")

    if success and payload is not None:
        top_level_keys = sorted(str(key) for key in payload.keys())
        rows = find_rows(payload)
        field_names = collect_field_names(rows)
        sample_row = get_sample_row(rows)

        print(f"top_level_keys: {json.dumps(top_level_keys, ensure_ascii=False)}")
        print(f"detected_row_count: {len(rows)}")
        print(f"raw_field_names: {json.dumps(field_names, ensure_ascii=False)}")
        print(
            "sample_raw_row: "
            f"{json.dumps(sample_row, ensure_ascii=False, default=str) if sample_row is not None else 'null'}"
        )
    else:
        print("top_level_keys: []")
        print("detected_row_count: 0")
        print("raw_field_names: []")
        print("sample_raw_row: null")
        print(f"error_message: {error_message or 'Unknown error'}")

    print()


def run_probe(
    *,
    client: CustomTefasClient,
    method_name: str,
    method: Callable[..., dict[str, Any]],
    probe_date: date,
    fund_kind: FundKind,
    fund_code: str | None,
) -> None:
    try:
        payload = method(
            start_date=probe_date,
            end_date=probe_date,
            fund_kind=fund_kind,
            fund_code=fund_code,
        )
    except Exception as exc:
        print_probe_result(
            fund_kind=fund_kind,
            method_name=method_name,
            success=False,
            error_message=str(exc),
        )
        return

    print_probe_result(
        fund_kind=fund_kind,
        method_name=method_name,
        success=True,
        payload=payload,
    )


def main() -> int:
    args = parse_args()
    client = CustomTefasClient()

    probe_methods: tuple[tuple[str, Callable[..., dict[str, Any]]], ...] = (
        ("fetch_general_info", client.fetch_general_info),
        ("fetch_portfolio_breakdown", client.fetch_portfolio_breakdown),
    )

    for fund_kind in FUND_KINDS:
        for method_name, method in probe_methods:
            run_probe(
                client=client,
                method_name=method_name,
                method=method,
                probe_date=args.date,
                fund_kind=fund_kind,
                fund_code=args.fund_code,
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
