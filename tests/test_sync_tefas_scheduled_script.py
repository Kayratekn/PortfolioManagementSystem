from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from scripts import sync_tefas_scheduled
from src.services.data_sync_run_service import SYNC_TYPE_TEFAS_DAILY


STARTED_AT = datetime(2026, 4, 27, 7, 0, tzinfo=timezone.utc)
COMPLETED_AT = datetime(2026, 4, 27, 7, 5, tzinfo=timezone.utc)


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


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class SessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


class FakeAuditService:
    instances: list["FakeAuditService"] = []

    def __init__(self, db: FakeSession) -> None:
        self.db = db
        self.started: list[dict[str, object]] = []
        self.successes: list[dict[str, object]] = []
        self.failures: list[dict[str, object]] = []
        FakeAuditService.instances.append(self)

    def start(self, sync_type: str, started_at: datetime) -> int:
        self.started.append({"sync_type": sync_type, "started_at": started_at})
        return 123

    def mark_success(self, run_id: int, completed_at: datetime) -> None:
        self.successes.append({"run_id": run_id, "completed_at": completed_at})

    def mark_failed(self, run_id: int, error_message: str, completed_at: datetime) -> None:
        self.failures.append(
            {"run_id": run_id, "error_message": error_message, "completed_at": completed_at}
        )


@pytest.fixture(autouse=True)
def reset_audit() -> None:
    FakeAuditService.instances = []


def expected_daily_calls(fund_kinds: tuple[str, ...], data_date: str) -> list[list[str]]:
    return [["--kind", fund_kind, "--date", data_date] for fund_kind in fund_kinds]


def install_common(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeDailyMain, SessionFactory]:
    fake_daily_main = FakeDailyMain()
    session_factory = SessionFactory()
    monkeypatch.setattr(sync_tefas_scheduled.sync_tefas_daily, "main", fake_daily_main)
    monkeypatch.setattr(sync_tefas_scheduled, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_scheduled, "build_data_sync_run_service", FakeAuditService)
    times = iter([STARTED_AT, COMPLETED_AT])
    monkeypatch.setattr(sync_tefas_scheduled, "utc_now", lambda: next(times))
    return fake_daily_main, session_factory


def test_previous_business_day_selects_monday_from_tuesday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 28)) == date(2026, 4, 27)


def test_previous_business_day_selects_friday_from_monday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 27)) == date(2026, 4, 24)


def test_previous_business_day_selects_friday_from_saturday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 25)) == date(2026, 4, 24)


def test_previous_business_day_selects_friday_from_sunday() -> None:
    assert sync_tefas_scheduled.previous_business_day(date(2026, 4, 26)) == date(2026, 4, 24)


def test_today_mode_keeps_reference_date_for_every_default_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main, _ = install_common(monkeypatch)

    sync_tefas_scheduled.main(["--date-mode", "today", "--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-27",
    )


def test_default_date_mode_uses_previous_business_day_for_every_default_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main, _ = install_common(monkeypatch)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-24",
    )


def test_omitted_kind_runs_every_supported_fund_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main, _ = install_common(monkeypatch)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    called_kinds = [call[1] for call in fake_daily_main.calls]
    assert called_kinds == list(sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS)


def test_explicit_kind_runs_only_that_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main, _ = install_common(monkeypatch)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--kind", "EMK"])

    assert fake_daily_main.calls == [["--kind", "EMK", "--date", "2026-04-24"]]


def test_supplied_fund_code_requires_kind_and_does_not_create_audit_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main, session_factory = install_common(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--fund-code", "AAL"])

    assert exc_info.value.code == 2
    assert fake_daily_main.calls == []
    assert session_factory.sessions == []
    assert FakeAuditService.instances == []


def test_supplied_fund_code_is_forwarded_for_explicit_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main, _ = install_common(monkeypatch)

    sync_tefas_scheduled.main(
        ["--reference-date", "2026-04-27", "--kind", "YAT", "--fund-code", "AAL"]
    )

    assert fake_daily_main.calls == [["--kind", "YAT", "--date", "2026-04-24", "--fund-code", "AAL"]]


def test_missing_fund_code_is_omitted(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main, _ = install_common(monkeypatch)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--kind", "YAT"])

    assert "--fund-code" not in fake_daily_main.calls[0]


def test_all_successful_kinds_return_zero_and_mark_one_audit_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main, session_factory = install_common(monkeypatch)
    fake_daily_main.return_value = 0

    exit_code = sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    audit = FakeAuditService.instances[0]
    assert exit_code == 0
    assert len(FakeAuditService.instances) == 1
    assert audit.started == [{"sync_type": SYNC_TYPE_TEFAS_DAILY, "started_at": STARTED_AT}]
    assert audit.successes == [{"run_id": 123, "completed_at": COMPLETED_AT}]
    assert audit.failures == []
    assert session_factory.sessions[0].closed is True


def test_non_zero_kind_continues_remaining_kinds_marks_failed_and_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main, session_factory = install_common(monkeypatch)
    fake_daily_main.return_values = [0, 1, 0, 0, 0]

    exit_code = sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    audit = FakeAuditService.instances[0]
    assert exit_code == 1
    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-24",
    )
    assert audit.successes == []
    assert audit.failures == [
        {
            "run_id": 123,
            "error_message": "One or more TEFAS syncs failed.",
            "completed_at": COMPLETED_AT,
        }
    ]
    assert "unavailable" not in audit.failures[0]["error_message"]
    assert session_factory.sessions[0].closed is True


def test_explicit_kind_non_zero_exit_code_is_returned_as_one(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_daily_main, _ = install_common(monkeypatch)
    fake_daily_main.return_value = 2

    exit_code = sync_tefas_scheduled.main(["--reference-date", "2026-04-27", "--kind", "BYF"])

    assert exit_code == 1
    assert fake_daily_main.calls == [["--kind", "BYF", "--date", "2026-04-24"]]


def test_omitted_reference_date_uses_current_date_for_every_default_kind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_daily_main, _ = install_common(monkeypatch)
    monkeypatch.setattr(sync_tefas_scheduled, "current_date", lambda: date(2026, 4, 27))

    sync_tefas_scheduled.main([])

    assert fake_daily_main.calls == expected_daily_calls(
        sync_tefas_scheduled.sync_tefas_daily.SYNC_FUND_KINDS,
        "2026-04-24",
    )


@pytest.mark.parametrize(
    "argv",
    [
        ["--reference-date", "2026-04-31"],
        ["--date-mode", "unsupported"],
        ["--kind", "unsupported", "--reference-date", "2026-04-27"],
    ],
)
def test_invalid_arguments_raise_system_exit_and_do_not_create_audit_run(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
) -> None:
    fake_daily_main, session_factory = install_common(monkeypatch)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_scheduled.main(argv)

    assert exc_info.value.code == 2
    assert fake_daily_main.calls == []
    assert session_factory.sessions == []
    assert FakeAuditService.instances == []


def test_summary_output_is_printed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_common(monkeypatch)

    sync_tefas_scheduled.main(["--reference-date", "2026-04-27"])

    captured = capsys.readouterr()
    assert "TEFAS scheduled sync" in captured.out
    assert "reference date: 2026-04-27" in captured.out
    assert "selected data date: 2026-04-24" in captured.out
    assert "date mode: previous-business-day" in captured.out
    assert "fund kinds: YAT, EMK, BYF, GYF, GSYF" in captured.out
    assert "fund code: None" in captured.out
