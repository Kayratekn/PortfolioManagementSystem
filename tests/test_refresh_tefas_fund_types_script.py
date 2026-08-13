from __future__ import annotations

import pytest

from scripts import refresh_tefas_fund_types
from src.services.tefas_fund_type_refresh_service import (
    TefasFundTypeRefreshFailure,
    TefasFundTypeRefreshResult,
)


class FakeSession:
    def __init__(self) -> None:
        self.closed = False
        self.commit_calls = 0

    def close(self) -> None:
        self.closed = True

    def commit(self) -> None:
        self.commit_calls += 1


class SessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


class FakeRefreshService:
    instances: list[FakeRefreshService] = []

    def __init__(self, result: TefasFundTypeRefreshResult | None = None, error: Exception | None = None) -> None:
        self.result = result or _result()
        self.error = error
        self.calls = 0
        FakeRefreshService.instances.append(self)

    def refresh_active_tefas_funds(self) -> TefasFundTypeRefreshResult:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.result


def _result(
    *,
    attempted_count: int = 1,
    succeeded_count: int = 1,
    failed_count: int = 0,
    created_count: int = 0,
    unchanged_count: int = 1,
    changed_count: int = 0,
    failures: tuple[TefasFundTypeRefreshFailure, ...] = (),
) -> TefasFundTypeRefreshResult:
    return TefasFundTypeRefreshResult(
        attempted_count=attempted_count,
        succeeded_count=succeeded_count,
        failed_count=failed_count,
        created_count=created_count,
        unchanged_count=unchanged_count,
        changed_count=changed_count,
        failures=failures,
    )


def _install_patches(
    monkeypatch: pytest.MonkeyPatch,
    *,
    result: TefasFundTypeRefreshResult | None = None,
    error: Exception | None = None,
) -> SessionFactory:
    session_factory = SessionFactory()
    service = FakeRefreshService(result=result, error=error)

    def fake_build_refresh_service(db: FakeSession) -> FakeRefreshService:
        assert db is session_factory.sessions[0]
        return service

    monkeypatch.setattr(refresh_tefas_fund_types, "SessionLocal", session_factory)
    monkeypatch.setattr(refresh_tefas_fund_types, "build_refresh_service", fake_build_refresh_service)
    return session_factory


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeRefreshService.instances = []


def test_refresh_service_called_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_patches(monkeypatch)

    exit_code = refresh_tefas_fund_types.main()

    assert exit_code == 0
    assert len(FakeRefreshService.instances) == 1
    assert FakeRefreshService.instances[0].calls == 1


def test_successful_result_prints_summary_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _result(
        attempted_count=4,
        succeeded_count=4,
        failed_count=0,
        created_count=1,
        unchanged_count=2,
        changed_count=1,
    )
    _install_patches(monkeypatch, result=result)

    exit_code = refresh_tefas_fund_types.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "TEFAS fund-type refresh completed" in captured.out
    assert "attempted_count: 4" in captured.out
    assert "succeeded_count: 4" in captured.out
    assert "failed_count: 0" in captured.out
    assert "created_count: 1" in captured.out
    assert "unchanged_count: 2" in captured.out
    assert "changed_count: 1" in captured.out


def test_zero_assets_result_prints_zero_summary_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_patches(monkeypatch, result=_result(attempted_count=0, succeeded_count=0, unchanged_count=0))

    exit_code = refresh_tefas_fund_types.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "attempted_count: 0" in captured.out
    assert "succeeded_count: 0" in captured.out
    assert "failed_count: 0" in captured.out
    assert "created_count: 0" in captured.out
    assert "unchanged_count: 0" in captured.out
    assert "changed_count: 0" in captured.out


def test_partial_failure_prints_summary_failures_and_returns_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failure = TefasFundTypeRefreshFailure(
        fund_code="BLH",
        error_type="RuntimeError",
        message="source failed",
    )
    result = _result(
        attempted_count=10,
        succeeded_count=9,
        failed_count=1,
        created_count=2,
        unchanged_count=6,
        changed_count=1,
        failures=(failure,),
    )
    _install_patches(monkeypatch, result=result)

    exit_code = refresh_tefas_fund_types.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "attempted_count: 10" in captured.out
    assert "succeeded_count: 9" in captured.out
    assert "failed_count: 1" in captured.out
    assert "failure: fund_code=BLH error_type=RuntimeError message=source failed" in captured.out


def test_all_failed_result_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _result(
        attempted_count=2,
        succeeded_count=0,
        failed_count=2,
        created_count=0,
        unchanged_count=0,
        changed_count=0,
        failures=(
            TefasFundTypeRefreshFailure("AAL", "RuntimeError", "failed one"),
            TefasFundTypeRefreshFailure("BLH", "RuntimeError", "failed two"),
        ),
    )
    _install_patches(monkeypatch, result=result)

    exit_code = refresh_tefas_fund_types.main()

    assert exit_code == 1


def test_fatal_exception_prints_to_stderr_and_returns_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_patches(monkeypatch, error=RuntimeError("database unavailable"))

    exit_code = refresh_tefas_fund_types.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "TEFAS fund-type refresh failed: database unavailable" in captured.err


@pytest.mark.parametrize(
    ("result", "error"),
    [
        (_result(), None),
        (_result(attempted_count=2, succeeded_count=1, failed_count=1), None),
        (None, RuntimeError("boom")),
    ],
)
def test_session_is_closed(
    monkeypatch: pytest.MonkeyPatch,
    result: TefasFundTypeRefreshResult | None,
    error: Exception | None,
) -> None:
    session_factory = _install_patches(monkeypatch, result=result, error=error)

    refresh_tefas_fund_types.main()

    assert len(session_factory.sessions) == 1
    assert session_factory.sessions[0].closed is True


def test_wrapper_does_not_explicitly_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = _install_patches(monkeypatch)

    refresh_tefas_fund_types.main()

    assert session_factory.sessions[0].commit_calls == 0


def test_no_live_tefas_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_custom_tefas_client() -> None:
        raise AssertionError("CustomTefasClient should not be constructed in this test")

    monkeypatch.setattr(refresh_tefas_fund_types, "CustomTefasClient", fail_custom_tefas_client)
    _install_patches(monkeypatch)

    assert refresh_tefas_fund_types.main() == 0


def test_no_dependency_on_mvp_fund_kinds_or_scheduler() -> None:
    imported_names = set(refresh_tefas_fund_types.__dict__)

    assert "MVP_FUND_KINDS" not in imported_names
    assert "sync_tefas_daily" not in imported_names
    assert "sync_tefas_scheduled" not in imported_names


def test_no_scheduling_library_dependency() -> None:
    imported_names = set(refresh_tefas_fund_types.__dict__)

    assert "schedule" not in imported_names
    assert "apscheduler" not in imported_names
    assert "APScheduler" not in imported_names


def test_summary_fields_use_actual_result_values(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = _result(
        attempted_count=17,
        succeeded_count=15,
        failed_count=2,
        created_count=3,
        unchanged_count=11,
        changed_count=1,
        failures=(
            TefasFundTypeRefreshFailure("AAL", "RuntimeError", "first failure"),
            TefasFundTypeRefreshFailure("BLH", "ValueError", "second failure"),
        ),
    )
    _install_patches(monkeypatch, result=result)

    refresh_tefas_fund_types.main()

    captured = capsys.readouterr()
    assert "attempted_count: 17" in captured.out
    assert "succeeded_count: 15" in captured.out
    assert "failed_count: 2" in captured.out
    assert "created_count: 3" in captured.out
    assert "unchanged_count: 11" in captured.out
    assert "changed_count: 1" in captured.out
    assert "failure: fund_code=AAL error_type=RuntimeError message=first failure" in captured.out
    assert "failure: fund_code=BLH error_type=ValueError message=second failure" in captured.out
