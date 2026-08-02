from __future__ import annotations

from datetime import date

import pytest

from scripts import sync_tefas_scheduled


class FakeDailyMain:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.return_value = 0

    def __call__(self, argv: list[str]) -> int:
        self.calls.append(argv)
        return self.return_value



def test_previous_business_day_selects_monday_from_tuesday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 28)) == date(2026, 4, 27)



def test_previous_business_day_selects_friday_from_monday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 27)) == date(2026, 4, 24)



def test_previous_business_day_selects_friday_from_saturday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 25)) == date(2026, 4, 24)



def test_previous_business_day_selects_friday_from_sunday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 26)) == date(2026, 4, 24)



def test_today_mode_keeps_reference_date(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--date-mode", "today", "--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == [["--kind", "YAT", "--date", "2026-04-27"]]



def test_default_date_mode_uses_previous_business_day(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == [["--kind", "YAT", "--date", "2026-04-24"]]



def test_default_fund_kind_is_yat(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert "--kind" in fake_daily_main.calls[0]
    assert "YAT" in fake_daily_main.calls[0]



def test_supplied_fund_code_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--fund-code", "AAL"])

    assert fake_daily_main.calls[0] == ["--kind", "YAT", "--date", "2026-04-24", "--fund-code", "AAL"]



def test_missing_fund_code_is_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert "--fund-code" not in fake_daily_main.calls[0]



def test_exact_selected_date_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    sync_tefas_scheduled.main(["--date-mode", "previous-business-day", "--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == [["--kind", "YAT", "--date", "2026-04-24"]]


@pytest.mark.parametrize("daily_exit_code", [0, 1])
def test_exact_daily_exit_code_is_returned(monkeypatch: pytest.MonkeyPatch, daily_exit_code: int) -> None:
    fake_daily_main = FakeDailyMain()
    fake_daily_main.return_value = daily_exit_code
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)

    exit_code = sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert exit_code == daily_exit_code



def test_omitted_reference_date_uses_current_date(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main = FakeDailyMain()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)
    monkeypatch.setattr(sync_tefas_scheduled, "current_date", lambda: date(2026, 4, 27))

    sync_tefas_scheduled.main([])

    assert fake_daily_main.calls == [["--kind", "YAT", "--date", "2026-04-24"]]



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
    assert "fund kind: YAT" in captured.out
    assert "fund code: None" in captured.out
