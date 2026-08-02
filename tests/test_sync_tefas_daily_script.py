from __future__ import annotations

from datetime import date

import pytest

from scripts import sync_tefas_daily
from src.services.tefas_sync_service import TefasSyncResult


class FakeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


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


class SessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


@pytest.fixture(autouse=True)
def reset_fake_service() -> None:
    FakeSyncService.instances = []
    FakeSyncService.result = TefasSyncResult(
        fetched_rows=1,
        assets_created=1,
        assets_updated=0,
        daily_rows_created=1,
        daily_rows_updated=0,
    )
    FakeSyncService.error = None



def test_successful_execution_uses_one_session_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert len(session_factory.sessions) == 1
    assert len(FakeSyncService.instances) == 1
    assert FakeSyncService.instances[0].db is session_factory.sessions[0]
    assert FakeSyncService.instances[0].calls == [
        {
            "start_date": date(2026, 4, 24),
            "end_date": date(2026, 4, 24),
            "fund_kind": "YAT",
            "fund_code": None,
        }
    ]
    assert session_factory.sessions[0].closed is True
    assert "fetched_rows: 1" in captured.out
    assert "assets_created: 1" in captured.out
    assert "assets_updated: 0" in captured.out
    assert "daily_rows_created: 1" in captured.out
    assert "daily_rows_updated: 0" in captured.out



def test_fund_code_is_passed_to_sync_general_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24", "--fund-code", "AAL"])

    assert exit_code == 0
    assert FakeSyncService.instances[0].calls[0]["fund_code"] == "AAL"



def test_default_kind_is_yat(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)

    exit_code = sync_tefas_daily.main(["--date", "2026-04-24"])

    assert exit_code == 0
    assert FakeSyncService.instances[0].calls[0]["fund_kind"] == "YAT"



def test_invalid_date_raises_system_exit_without_creating_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)

    with pytest.raises(SystemExit) as exc_info:
        sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-31"])

    assert exc_info.value.code == 2
    assert session_factory.sessions == []



def test_sync_failure_returns_one_and_prints_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeSyncService.error = RuntimeError("boom")
    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "TEFAS sync failed" in captured.err
    assert "boom" in captured.err
    assert len(session_factory.sessions) == 1
    assert session_factory.sessions[0].closed is True



def test_zero_count_result_prints_successfully(
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
    monkeypatch.setattr(sync_tefas_daily, "SessionLocal", session_factory)
    monkeypatch.setattr(sync_tefas_daily, "TefasSyncService", FakeSyncService)

    exit_code = sync_tefas_daily.main(["--kind", "YAT", "--date", "2026-04-24"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "fetched_rows: 0" in captured.out
    assert "assets_created: 0" in captured.out
    assert "assets_updated: 0" in captured.out
    assert "daily_rows_created: 0" in captured.out
    assert "daily_rows_updated: 0" in captured.out
