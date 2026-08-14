from __future__ import annotations

import pytest

from scripts import backfill_tefas_fund_types
from src.services.tefas_fund_type_backfill_service import (
    TefasFundTypeBackfillFailure,
    TefasFundTypeBackfillResult,
)


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


class FakeBackfillService:
    instances: list[FakeBackfillService] = []
    result = TefasFundTypeBackfillResult(
        fund_kind="YAT",
        limit=2,
        attempted_count=2,
        succeeded_count=2,
        failed_count=0,
        created_count=2,
        unchanged_count=0,
        changed_count=0,
        failures=(),
    )
    error: Exception | None = None

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        FakeBackfillService.instances.append(self)

    def backfill_missing_active_tefas_funds(
        self,
        *,
        fund_kind: str,
        limit: int,
        delay_seconds: float,
    ) -> TefasFundTypeBackfillResult:
        self.calls.append(
            {
                "fund_kind": fund_kind,
                "limit": limit,
                "delay_seconds": delay_seconds,
            }
        )
        if FakeBackfillService.error is not None:
            raise FakeBackfillService.error
        return FakeBackfillService.result


@pytest.fixture(autouse=True)
def reset_fakes() -> None:
    FakeBackfillService.instances = []
    FakeBackfillService.result = TefasFundTypeBackfillResult(
        fund_kind="YAT",
        limit=2,
        attempted_count=2,
        succeeded_count=2,
        failed_count=0,
        created_count=2,
        unchanged_count=0,
        changed_count=0,
        failures=(),
    )
    FakeBackfillService.error = None


def _install_common_patches(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: SessionFactory,
) -> None:
    def fake_build_backfill_service(db: FakeSession) -> FakeBackfillService:
        assert db is session_factory.sessions[0]
        return FakeBackfillService()

    monkeypatch.setattr(backfill_tefas_fund_types, "SessionLocal", session_factory)
    monkeypatch.setattr(
        backfill_tefas_fund_types,
        "build_backfill_service",
        fake_build_backfill_service,
    )


def test_successful_execution_passes_required_kind_limit_and_default_delay(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    _install_common_patches(monkeypatch, session_factory)

    exit_code = backfill_tefas_fund_types.main(["--kind", "YAT", "--limit", "2"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert len(session_factory.sessions) == 1
    assert session_factory.sessions[0].closed is True
    assert FakeBackfillService.instances[0].calls == [
        {"fund_kind": "YAT", "limit": 2, "delay_seconds": 1.0}
    ]
    assert "TEFAS fund-type backfill completed" in captured.out
    assert "fund_kind: YAT" in captured.out
    assert "limit: 2" in captured.out
    assert "attempted_count: 2" in captured.out


def test_delay_seconds_argument_is_forwarded(monkeypatch: pytest.MonkeyPatch) -> None:
    session_factory = SessionFactory()
    _install_common_patches(monkeypatch, session_factory)

    exit_code = backfill_tefas_fund_types.main(
        ["--kind", "YAT", "--limit", "2", "--delay-seconds", "0.25"]
    )

    assert exit_code == 0
    assert FakeBackfillService.instances[0].calls[0]["delay_seconds"] == 0.25


def test_failures_are_printed_and_return_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeBackfillService.result = TefasFundTypeBackfillResult(
        fund_kind="YAT",
        limit=3,
        attempted_count=3,
        succeeded_count=2,
        failed_count=1,
        created_count=2,
        unchanged_count=0,
        changed_count=0,
        failures=(
            TefasFundTypeBackfillFailure(
                fund_code="BLH",
                error_type="RuntimeError",
                message="profile failed",
            ),
        ),
    )
    _install_common_patches(monkeypatch, session_factory)

    exit_code = backfill_tefas_fund_types.main(["--kind", "YAT", "--limit", "3"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "failed_count: 1" in captured.out
    assert "failure: fund_code=BLH error_type=RuntimeError message=profile failed" in captured.out
    assert session_factory.sessions[0].closed is True


@pytest.mark.parametrize(
    "arguments",
    [
        ["--limit", "10"],
        ["--kind", "YAT"],
        ["--kind", "ABC", "--limit", "10"],
        ["--kind", "YAT", "--limit", "0"],
        ["--kind", "YAT", "--limit", "-1"],
        ["--kind", "YAT", "--limit", "10", "--delay-seconds", "-0.1"],
    ],
)
def test_validation_failures_happen_before_session_creation(
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = SessionFactory()
    monkeypatch.setattr(backfill_tefas_fund_types, "SessionLocal", session_factory)

    with pytest.raises(SystemExit) as exc_info:
        backfill_tefas_fund_types.main(arguments)

    assert exc_info.value.code == 2
    assert session_factory.sessions == []
    assert FakeBackfillService.instances == []


def test_service_exception_returns_failure_and_closes_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session_factory = SessionFactory()
    FakeBackfillService.error = RuntimeError("backfill failed")
    _install_common_patches(monkeypatch, session_factory)

    exit_code = backfill_tefas_fund_types.main(["--kind", "YAT", "--limit", "2"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "TEFAS fund-type backfill failed: backfill failed" in captured.err
    assert session_factory.sessions[0].closed is True


def test_no_live_tefas_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_custom_tefas_client() -> None:
        raise AssertionError("live TEFAS client should not be built")

    session_factory = SessionFactory()
    _install_common_patches(monkeypatch, session_factory)
    monkeypatch.setattr(backfill_tefas_fund_types, "CustomTefasClient", fail_custom_tefas_client)

    assert backfill_tefas_fund_types.main(["--kind", "YAT", "--limit", "2"]) == 0
