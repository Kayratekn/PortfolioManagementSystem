from __future__ import annotations

from datetime import date

import pytest

from scripts import sync_tefas_scheduled


class FakeDailyMain:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.return_value = 0
        self.return_values: list[int] | None = None

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(argv)
        if self.return_values is not None:
            return self.return_values[len(self.calls) - 1]
        return self.return_value


def expected_daily_calls(fund_kinds: tuple[str, ...], data_date: str) -> list[list[str]]:
    return [["--kind", fund_kind, "--date", data_date] for fund_kind in fund_kinds]


def test_previous_business_day_selects_monday_from_tuesday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 28)) == date(2026, 4, 27)


def test_previous_business_day_selects_friday_from_monday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 27)) == date(2026, 4, 24)


def test_previous_business_day_selects_friday_from_saturday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 25)) == date(2026, 4, 24)


def test_previous_business_day_selects_friday_from_sunday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 26)) == date(2026, 4, 24)


def test_today_mode_keeps_reference_date_for_every_default_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--date-mode", "today", "--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-27",
    )


def test_default_date_mode_uses_previous_business_day_for_every_default_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-24",
    )


def test_omitted_kind_runs_every_supported_fund_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    called_kinds = [call[1] for call in fake_daily_main.calls]
    assert called_kinds == list(sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS)


def test_explicit_kind_runs_only_that_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--kind", "EMK"])

    assert fake_daily_main.calls == [["--kind", "EMK", "--date", "2026-04-24"]]


def test_supplied_fund_code_requires_kind_and_does_not_call_daily_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--fund-code", "AAL"])

    assert exc_info.value.code == 2
    assert fake_daily_main.calls == []


def test_supplied_fund_code_is_forwarded_for_explicit_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(
        ["--reference-date", "2026-04-27", "--kind", "YAT", "--fund-code", "AAL"]
    )

    assert fake_daily_main.calls == [["--kind", "YAT", "--date", "2026-04-24", "--fund-code", "AAL"]]


def test_missing_fund_code_is_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--kind", "YAT"])

    assert "--fund-code" not in fake_daily_main.calls[0]


def test_exact_selected_date_is_forwarded_to_every_default_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--date-mode", "previous-business-day", "--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-24",
    )


def test_all_successful_kinds_return_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    fake_daily_main.return_value = 0
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    exit_code = sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert exit_code == 0


def test_non_zero_kind_continues_remaining_kinds_and_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    fake_daily_main.return_values = [0, 1, 0, 0, 0]
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    exit_code = sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert exit_code == 1
    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-24",
    )


def test_explicit_kind_non_zero_exit_code_is_returned_as_one(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    fake_daily_main.return_value = 2
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    exit_code = sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--kind", "BYF"])

    assert exit_code == 1
    assert fake_daily_main.calls == [["--kind", "BYF", "--date", "2026-04-24"]]


def test_omitted_reference_date_uses_current_date_for_every_default_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)
    monkeypatch.setattr(sync_tefas_scheduled, "current_date", lambda: date(2026, 4, 27))

    sync_tefas_scheduled.main([])

    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-24",
    )


def test_invalid_reference_date_raises_system_exit_and_does_not_call_daily_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_scheduled.main(["--reference-date", "2026-04-31"])

    assert exc_info.value.code == 2
    assert fake_daily_main.calls == []


def test_invalid_date_mode_raises_system_exit_and_does_not_call_daily_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_scheduled.main(["--date-mode", "unsupported"])

    assert exc_info.value.code == 2
    assert fake_daily_main.calls == []


def test_invalid_kind_raises_system_exit_and_does_not_call_daily_main(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_scheduled.main(["--kind", "unsupported", "--reference-date", "2026-04-27"])

    assert exc_info.value.code == 2
    assert fake_daily_main.calls == []


def test_summary_output_is_printed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    captured = capsys.readouterr()
    assert "TEFAS scheduled sync" in captured.out
    assert "reference date: 2026-04-27" in captured.out
    assert "selected data date: 2026-04-24" in captured.out
    assert "date mode: previous-business-day" in captured.out
    assert "fund kinds: YAT, EMK, BYF, GYF, GSYF" in captured.out
    assert "fund code: None" in captured.out
