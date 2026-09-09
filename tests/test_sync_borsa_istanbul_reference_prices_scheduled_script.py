from dataclasses import dataclass
from datetime import date, datetime, timezone

import pytest

from scripts import sync_borsa_istanbul_reference_prices_scheduled as script
from src.services.data_sync_run_service import SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY


STARTED = datetime(2026, 9, 9, 7, 0, tzinfo=timezone.utc)
COMPLETED = datetime(2026, 9, 9, 7, 5, tzinfo=timezone.utc)


class FakeSession:
    def __init__(self): self.closed = False
    def close(self): self.closed = True


class SessionFactory:
    def __init__(self): self.sessions = []
    def __call__(self):
        session = FakeSession()
        self.sessions.append(session)
        return session


@dataclass(frozen=True)
class FakeResult:
    effective_date: date = date(2026, 9, 8)
    provider_observations: int = 3
    rows_inserted: int = 3
    rows_skipped: int = 0


class FakeDailySyncService:
    fail = False
    instances = []
    def __init__(self, db, client):
        self.db, self.client = db, client
        FakeDailySyncService.instances.append(self)
    def sync(self):
        if self.fail: raise RuntimeError("provider unavailable")
        return FakeResult()


class FakeAuditService:
    instances = []
    def __init__(self, db):
        self.started, self.successes, self.failures = [], [], []
        FakeAuditService.instances.append(self)
    def start(self, sync_type, started_at):
        self.started.append((sync_type, started_at))
        return 9
    def mark_success(self, run_id, completed_at): self.successes.append((run_id, completed_at))
    def mark_failed(self, run_id, error_message, completed_at): self.failures.append((run_id, error_message, completed_at))


@pytest.fixture(autouse=True)
def reset(monkeypatch):
    FakeDailySyncService.fail = False
    FakeDailySyncService.instances = []
    FakeAuditService.instances = []
    monkeypatch.setattr(script, "BorsaIstanbulDailyReferencePriceSyncService", FakeDailySyncService)
    monkeypatch.setattr(script, "build_data_sync_run_service", FakeAuditService)
    monkeypatch.setattr(script, "current_date", lambda: date(2026, 9, 9))
    times = iter([STARTED, COMPLETED])
    monkeypatch.setattr(script, "utc_now", lambda: next(times))


def test_help_exits_before_sessions_provider_or_audit_work(capsys):
    factory = SessionFactory()
    with pytest.raises(SystemExit) as exc_info:
        script.main(["--help"], session_factory=factory, client_factory=lambda: (_ for _ in ()).throw(AssertionError()))
    assert exc_info.value.code == 0
    assert factory.sessions == []
    assert FakeDailySyncService.instances == []
    assert FakeAuditService.instances == []
    assert "Sync the current Borsa Istanbul" in capsys.readouterr().out


def test_success_starts_and_completes_audit_and_prints_result(capsys):
    factory = SessionFactory()
    assert script.main([], session_factory=factory, client_factory=object) == 0
    audit = FakeAuditService.instances[0]
    assert audit.started == [(SYNC_TYPE_BIST_REFERENCE_PRICES_DAILY, STARTED)]
    assert audit.successes == [(9, COMPLETED)]
    assert audit.failures == []
    assert all(session.closed for session in factory.sessions)
    output = capsys.readouterr().out
    assert "effective_date: 2026-09-08" in output
    assert "provider_observations: 3" in output
    assert "rows_inserted: 3" in output
    assert "rows_skipped: 0" in output


def test_failure_marks_failed_closes_sessions_and_returns_one(capsys):
    FakeDailySyncService.fail = True
    factory = SessionFactory()
    assert script.main([], session_factory=factory, client_factory=object) == 1
    audit = FakeAuditService.instances[0]
    assert audit.successes == []
    assert audit.failures == [(9, "BIST current reference-price sync failed.", COMPLETED)]
    assert all(session.closed for session in factory.sessions)
    assert "provider unavailable" in capsys.readouterr().err


def test_idempotent_result_is_still_success(monkeypatch):
    factory = SessionFactory()
    monkeypatch.setattr(script, "BorsaIstanbulDailyReferencePriceSyncService", lambda db, client: type("Service", (), {"sync": lambda self: FakeResult(rows_inserted=0, rows_skipped=3)})())
    assert script.main([], session_factory=factory, client_factory=object) == 0
    assert FakeAuditService.instances[0].successes == [(9, COMPLETED)]