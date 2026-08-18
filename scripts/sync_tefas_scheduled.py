from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from pathlib import Path
import argparse
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import sync_tefas_daily


def previous_business_day(reference_date: date) -> date:
    selected_date = reference_date - timedelta(days=1)
    while selected_date.weekday() >= 5:
        selected_date -= timedelta(days=1)
    return selected_date



def current_date() -> date:
    return date.today()



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run scheduled TEFAS synchronization.")
    parser.add_argument("--kind", default=None, choices=sync_tefas_daily.SYNC_FUND_KINDS)
    parser.add_argument("--fund-code", dest="fund_code", default=None)
    parser.add_argument(
        "--date-mode",
        choices=("previous-business-day", "today"),
        default="previous-business-day",
    )
    parser.add_argument("--reference-date", dest="reference_date", type=sync_tefas_daily.parse_iso_date)
    return parser



def select_data_date(*, reference_date: date, date_mode: str) -> date:
    if date_mode == "previous-business-day":
        return previous_business_day(reference_date)
    if date_mode == "today":
        return reference_date
    raise ValueError(f"Unsupported date mode: {date_mode}")



def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.fund_code is not None and args.kind is None:
        parser.error("--fund-code requires --kind")

    reference_date = args.reference_date or current_date()
    selected_data_date = select_data_date(
        reference_date=reference_date,
        date_mode=args.date_mode,
    )
    selected_fund_kinds = (args.kind,) if args.kind is not None else sync_tefas_daily.SYNC_FUND_KINDS

    print("TEFAS scheduled sync")
    print(f"reference date: {reference_date.isoformat()}")
    print(f"selected data date: {selected_data_date.isoformat()}")
    print(f"date mode: {args.date_mode}")
    print(f"fund kinds: {', '.join(selected_fund_kinds)}")
    print(f"fund code: {args.fund_code}")

    final_exit_code = 0
    for fund_kind in selected_fund_kinds:
        daily_arguments = [
            "--kind",
            fund_kind,
            "--date",
            selected_data_date.isoformat(),
        ]
        if args.fund_code is not None:
            daily_arguments.extend(["--fund-code", args.fund_code])

        exit_code = sync_tefas_daily.main(daily_arguments)
        if exit_code != 0:
            final_exit_code = 1

    return final_exit_code


if __name__ == "__main__":
    sys.exit(main())
