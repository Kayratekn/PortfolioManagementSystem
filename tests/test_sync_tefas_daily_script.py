from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from scripts import sync_tefas_daily
from src.services.tefas_sync_service import TefasSyncResult


STARTED_AT = datetime(2026, 4, 24, 9, 30, tzinfo=timezone.utc)
COMPLETED_AT = datetime(2026, 4, 24, 10, 0, tzinfo=timezone.utc)


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


class FakeSyncService:
    instances: list[FakeSyncService] = []
    result = TefasSyncResult(
        fetched_rows=1,
        assets_created=1,
        assets_updated=0,
        daily_rows_created=1,
        daily_rows_updated=0,
    )
    error: Exception | None = None

    def __init__(self, db: FakeSession) -> None:
        self.db = db
        self.calls: list[dict[str, object]] = []
        FakeSyncService.instances.append(self)

    def sync_general_info(
        self,
        *,
        start_date: date,
        end_date: date,
        fund_kind: str,
        fund_code: str | None,
    ) -> TefasSyncResult:
        self.calls.append(
            {
                "start_date": start_date,
                "end_date": end_date,
                "fund_kind": fund_kind,
                "fund_code": fund_code,
            }
        )
        if FakeSyncService.error is not None:
            raise FakeSyncService.error
        return FakeSyncService.result


class FakeTefasFetchLogService:
    instances: list[FakeTefasFetchLogService] = []
    fetch_log_id = 123
    start_error: Exception | None = None
    mark_success_error: Exception | None = None
    mark_failed_error: Exception | None = None

    def __init__(self, db: FakeSession) -> None:
        self.db = db
        self.start_calls: list[dict[str, object]] = []
        self.mark_success_calls: list[dict[str, object]] = []
        self.mark_failed_calls: list[dict[str, object]] = []
        FakeTefasFetchLogService.instances.append(self)

    def start(
        self,
        *,
        fund_kind: str,
        fund_code: str | None,
        start_date: date,
        end_date: date,
        started_at: datetime,
    ) -> int:
        self.start_calls.append(
            {
                "fund_kind": fund_kind,
                "fund_code": fund_code,
                "start_date": start_date,
                "end_date": end_date,
                "started_at": started_at,
            }
        )
        if FakeTefasFetchLogService.start_error is not None:
            raise FakeTefasFetchLogService.start_error
        return FakeTefasFetchLogService.fetch_log_id

    def mark_success(
        self,
        *,
        fetch_log_id: int,
        fetched_rows: int,
        assets_created: int,
        assets_updated: int,
        daily_rows_created: int,
        daily_rows_updated: int,
        completed_at: datetime,
    ) -> None:
        self.mark_success_calls.append(
            {
                "fetch_log_id": fetch_log_id,
                "fetched_rows": fetched_rows,
                "assets_created": assets_created,
                "assets_updated": assets_updated,
                "daily_rows_created": daily_rows_created,
                "daily_rows_updated": daily_rows_updated,
                "completed_at": completed_at,
            }
        )
        if FakeTefasFetchLogService.mark_success_error is not None:
            raise FakeTefasFetchLogService.mark_success_error

    def mark_failed(
        self,
        *,
        fetch_log_id: int,
        error_message: str,
        completed_at: datetime,
    ) -> None:
        self.mark_failed_calls.append(
            {
                "fetch_log_id": fetch_log_id,
                "error_message": error_message,
                "completed_at": completed_at,
            }
        )
        if FakeTefasFetchLogService.mark_failed_error is not None:
            raise FakeTefasFetchLogService.mark_failed_error


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeSyncService.instances = []
    FakeSyncService.result = TefasSyncResult(
        fetched_rows=1,
        assets_created=1,
        assets_updated=0,
        daily_rows_created=1,
        daily_rows_updated=0,
    )
    FakeSyncService.error = None
    FakeTefasFetchLogService.instances = []
    FakeTefasFetchLogService.fetch_log_id = 123
    FakeTefasFetchLogService.start_error = None
    FakeTefasFetchLogService.mark_success_error = None
    FakeTefasFetchLogService.mark_failed_error = None



def _install_common_patches(monkeypatch: pytest.MonkeyPatch, session_factory: SessionFactory) -> None:
    timestamps = [STARTED_AT, COMPLETED_AT]

    def fake_utc_now() -> datetime:
        return timestamps.pop(0)

    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)
    monkeypatch.setattr(sync_tefas_daily, "TefasFetchLogService", FakeTefasFetchLogService)
    monkeypatch.setattr(sync_tefas_daily, "utc_now", fake_utc_now)



def test_successful_execution_uses_two_sessions_and_updates_fetch_log(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert len(session_factory.sessions) == 2
    assert session_factory.sessions[0] is not session_factory.sessions[1]
    assert len(FakeSyncService.instances) == 1
    assert len(FakeTefasFetchLogService.instances) == 1
    assert FakeSyncService.instances[0].db is session_factory.sessions[0]
    assert FakeTefasFetchLogService.instances[0].db is session_factory.sessions[1]
    assert FakeTefasFetchLogService.instances[0].start_calls == [
        {
            "fund_kind": "YAT",
            "fund_code": None,
            "start_date": date(2026, 4, 24),
            "end_date": date(2026, 4, 24),
            "started_at": STARTED_AT,
        }
    ]
    assert FakeSyncService.instances[0].calls == [
        {
            "start_date": date(2026, 4, 24),
            "end_date": date(2026, 4, 24),
            "fund_kind": "YAT",
            "fund_code": None,
        }
    ]
    assert FakeTefasFetchLogService.instances[0].mark_success_calls == [
        {
            "fetch_log_id": 123,
            "fetched_rows": 1,
            "assets_created": 1,
            "assets_updated": 0,
            "daily_rows_created": 1,
            "daily_rows_updated": 0,
            "completed_at": COMPLETED_AT,
        }
    ]
    assert FakeTefasFetchLogService.instances[0].mark_failed_calls == []
    assert session_factory.sessions[0].closed is True
    assert session_factory.sessions[1].closed is True
    assert "TEFAS sync completed successfully" in captured.out
    assert "fetched_rows: 1" in captured.out
    assert "assets_created: 1" in captured.out
    assert "assets_updated: 0" in captured.out
    assert "daily_rows_created: 1" in captured.out
    assert "daily_rows_updated: 0" in captured.out



def test_fund_code_is_passed_to_fetch_log_start_and_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = SessionFactory()
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24", "--fund-code", "AAL"])

    assert exit_code == 0
    assert FakeTefasFetchLogService.instances[0].start_calls[0]["fund_code"] == "AAL"
    assert FakeSyncService.instances[0].calls[0]["fund_code"] == "AAL"



def test_default_kind_is_used_for_fetch_log_start_and_sync(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = SessionFactory()
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--date", "2026-04-24"])

    assert exit_code == 0
    assert FakeTefasFetchLogService.instances[0].start_calls[0]["fund_kind"] == "YAT"
    assert FakeSyncService.instances[0].calls[0]["fund_kind"] == "YAT"



def test_invalid_date_raises_system_exit_without_creating_sessions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)
    monkeypatch.setattr(sync_tefas_daily, "TefasFetchLogService", FakeTefasFetchLogService)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-31"])

    assert exc_info.value.code == 2
    assert session_factory.sessions == []
    assert FakeSyncService.instances == []
    assert FakeTefasFetchLogService.instances == []



def test_sync_failure_marks_fetch_log_failed_and_preserves_error_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeSyncService.error = RuntimeError("boom")
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert FakeTefasFetchLogService.instances[0].mark_success_calls == []
    assert FakeTefasFetchLogService.instances[0].mark_failed_calls == [
        {
            "fetch_log_id": 123,
            "error_message": "boom",
            "completed_at": COMPLETED_AT,
        }
    ]
    assert "TEFAS sync failed: boom" in captured.err
    assert session_factory.sessions[0].closed is True
    assert session_factory.sessions[1].closed is True



def test_zero_count_success_passes_zero_result_to_mark_success(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeSyncService.result = TefasSyncResult(
        fetched_rows=0,
        assets_created=0,
        assets_updated=0,
        daily_rows_created=0,
        daily_rows_updated=0,
    )
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert FakeTefasFetchLogService.instances[0].mark_success_calls == [
        {
            "fetch_log_id": 123,
            "fetched_rows": 0,
            "assets_created": 0,
            "assets_updated": 0,
            "daily_rows_created": 0,
            "daily_rows_updated": 0,
            "completed_at": COMPLETED_AT,
        }
    ]
    assert "fetched_rows: 0" in captured.out
    assert "assets_created: 0" in captured.out
    assert "assets_updated: 0" in captured.out
    assert "daily_rows_created: 0" in captured.out
    assert "daily_rows_updated: 0" in captured.out



def test_fetch_log_start_failure_prevents_synchronization(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeTefasFetchLogService.start_error = RuntimeError("log start failed")
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "TEFAS fetch log start failed: log start failed" in captured.err
    assert FakeSyncService.instances[0].calls == []
    assert session_factory.sessions[0].closed is True
    assert session_factory.sessions[1].closed is True



def test_failed_log_update_failure_prints_both_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeSyncService.error = RuntimeError("boom")
    FakeTefasFetchLogService.mark_failed_error = RuntimeError("log update failed")
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "TEFAS fetch log update failed: log update failed" in captured.err
    assert "TEFAS sync failed: boom" in captured.err
    assert session_factory.sessions[0].closed is True
    assert session_factory.sessions[1].closed is True



def test_success_log_update_failure_does_not_call_mark_failed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeTefasFetchLogService.mark_success_error = RuntimeError("log update failed")
    _install_common_patches(monkeypatch, session_factory)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert FakeTefasFetchLogService.instances[0].mark_failed_calls == []
    assert "TEFAS fetch log update failed: log update failed" in captured.err
    assert "TEFAS sync completed successfully" not in captured.out
    assert session_factory.sessions[0].closed is True
    assert session_factory.sessions[1].closed is True
