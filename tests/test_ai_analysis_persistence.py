from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import CheckConstraint, Index, JSON, Text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import src.model as model_package
from src.config import dependencies
from src.model.ai_analysis import AiAnalysis
from src.model.base import Base
from src.model.portfolio import Portfolio
from src.model.user import User
from src.repositories.ai_analysis_repository import AiAnalysisRepository
from src.services.ai_analysis_persistence_service import AiAnalysisPersistenceService


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_0023 = PROJECT_ROOT / "alembic" / "versions" / "20260907_0023_create_ai_analyses.py"
ALEMBIC_ENV = PROJECT_ROOT / "alembic" / "env.py"
REPOSITORY_SOURCE = PROJECT_ROOT / "src" / "repositories" / "ai_analysis_repository.py"
SERVICE_SOURCE = PROJECT_ROOT / "src" / "services" / "ai_analysis_persistence_service.py"


def _add_user(db_session: Session, *, email: str = "user@example.com") -> User:
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password="hashed",
        preferred_currency="TRY",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()
    return user


def _add_portfolio(
    db_session: Session,
    *,
    user_id: int,
    name: str = "Portfolio",
) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, name=name, base_currency="TRY")
    db_session.add(portfolio)
    db_session.flush()
    return portfolio


def _analysis(
    *,
    user_id: int,
    portfolio_id: int | None = None,
    analysis_type: str = "portfolio-analysis",
    result_payload: dict[str, Any] | None = None,
    model_version: str = "ai-model-1",
    formula_version: str | None = "formula-1",
    created_at: datetime | None = None,
) -> AiAnalysis:
    kwargs: dict[str, Any] = {
        "user_id": user_id,
        "portfolio_id": portfolio_id,
        "analysis_type": analysis_type,
        "result_payload": result_payload if result_payload is not None else {"score": "1.25"},
        "explanation_text": "explanation",
        "disclaimer": "disclaimer",
        "model_version": model_version,
        "formula_version": formula_version,
    }
    if created_at is not None:
        kwargs["created_at"] = created_at
    return AiAnalysis(**kwargs)


def test_ai_analysis_model_defines_fields_constraints_indexes_and_no_updated_at() -> None:
    table = AiAnalysis.__table__
    constraints = {
        constraint.name: str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    indexes = {
        index.name: tuple(index.columns.keys())
        for index in table.indexes
        if isinstance(index, Index)
    }

    assert table.name == "ai_analyses"
    assert table.c.id.primary_key is True
    assert table.c.user_id.nullable is False
    assert table.c.portfolio_id.nullable is True
    assert table.c.analysis_type.nullable is False
    assert table.c.analysis_type.type.length == 50
    assert table.c.result_payload.nullable is False
    assert isinstance(table.c.result_payload.type, JSON)
    assert table.c.explanation_text.nullable is True
    assert isinstance(table.c.explanation_text.type, Text)
    assert table.c.disclaimer.nullable is True
    assert isinstance(table.c.disclaimer.type, Text)
    assert table.c.model_version.nullable is False
    assert table.c.model_version.type.length == 100
    assert table.c.formula_version.nullable is True
    assert table.c.formula_version.type.length == 100
    assert table.c.created_at.nullable is False
    assert table.c.created_at.type.timezone is True
    assert "updated_at" not in table.c
    assert next(iter(table.c.user_id.foreign_keys)).target_fullname == "users.id"
    assert next(iter(table.c.portfolio_id.foreign_keys)).target_fullname == "portfolios.id"
    assert constraints["ck_ai_analyses_analysis_type_nonblank"] == "length(trim(analysis_type)) > 0"
    assert constraints["ck_ai_analyses_model_version_nonblank"] == "length(trim(model_version)) > 0"
    assert constraints["ck_ai_analyses_formula_version_null_or_nonblank"] == (
        "formula_version IS NULL OR length(trim(formula_version)) > 0"
    )
    assert indexes["ix_ai_analyses_user_created_id"] == ("user_id", "created_at", "id")
    assert indexes["ix_ai_analyses_portfolio_created_id"] == (
        "portfolio_id",
        "created_at",
        "id",
    )
    assert not any(getattr(constraint, "columns", None) for constraint in table.constraints if constraint.__class__.__name__ == "UniqueConstraint")


def test_ai_analysis_migration_revision_schema_indexes_and_downgrade() -> None:
    migration_text = MIGRATION_0023.read_text(encoding="utf-8")

    assert 'revision = "20260907_0023"' in migration_text
    assert 'down_revision = "20260907_0022"' in migration_text
    assert '"ai_analyses"' in migration_text
    assert 'sa.Column("user_id", sa.Integer(), nullable=False)' in migration_text
    assert 'sa.Column("portfolio_id", sa.Integer(), nullable=True)' in migration_text
    assert 'sa.Column("analysis_type", sa.String(length=50), nullable=False)' in migration_text
    assert 'sa.Column("result_payload", sa.JSON(), nullable=False)' in migration_text
    assert 'sa.Column("explanation_text", sa.Text(), nullable=True)' in migration_text
    assert 'sa.Column("disclaimer", sa.Text(), nullable=True)' in migration_text
    assert 'sa.Column("model_version", sa.String(length=100), nullable=False)' in migration_text
    assert 'sa.Column("formula_version", sa.String(length=100), nullable=True)' in migration_text
    assert 'sa.DateTime(timezone=True)' in migration_text
    assert 'server_default=sa.func.now()' in migration_text
    assert 'name="ck_ai_analyses_analysis_type_nonblank"' in migration_text
    assert 'name="ck_ai_analyses_model_version_nonblank"' in migration_text
    assert 'name="ck_ai_analyses_formula_version_null_or_nonblank"' in migration_text
    assert 'sa.ForeignKeyConstraint(["user_id"], ["users.id"])' in migration_text
    assert 'sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"])' in migration_text
    assert '"ix_ai_analyses_user_created_id"' in migration_text
    assert '["user_id", "created_at", "id"]' in migration_text
    assert '"ix_ai_analyses_portfolio_created_id"' in migration_text
    assert '["portfolio_id", "created_at", "id"]' in migration_text
    assert "UniqueConstraint" not in migration_text
    assert 'op.drop_table("ai_analyses")' in migration_text


def test_ai_analysis_model_is_registered_in_metadata_and_alembic_env() -> None:
    alembic_env_text = ALEMBIC_ENV.read_text(encoding="utf-8")

    assert "ai_analyses" in Base.metadata.tables
    assert "ai_analysis" in model_package.__all__
    assert "from src.model import ai_analysis" in alembic_env_text


def test_create_persists_one_row_and_preserves_versions(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    service = AiAnalysisPersistenceService(
        db=db_session,
        repository=AiAnalysisRepository(db_session),
    )

    created = service.persist_analysis(
        user_id=user.id,
        portfolio_id=portfolio.id,
        analysis_type=" portfolio-analysis ",
        result_payload={"score": "1.25"},
        explanation_text=None,
        disclaimer=None,
        model_version=" model-v1 ",
        formula_version=" formula-v1 ",
    )

    assert created.id is not None
    assert created.analysis_type == "portfolio-analysis"
    assert created.result_payload == {"score": "1.25"}
    assert created.explanation_text is None
    assert created.disclaimer is None
    assert created.model_version == "model-v1"
    assert created.formula_version == "formula-v1"
    assert db_session.query(AiAnalysis).count() == 1


def test_repeated_same_user_portfolio_and_type_appends_two_rows(db_session: Session) -> None:
    user = _add_user(db_session)
    portfolio = _add_portfolio(db_session, user_id=user.id)
    service = AiAnalysisPersistenceService(db=db_session, repository=AiAnalysisRepository(db_session))

    first = service.persist_analysis(
        user_id=user.id,
        portfolio_id=portfolio.id,
        analysis_type="portfolio-analysis",
        result_payload={"run": 1},
        model_version="model-v1",
        formula_version="formula-v1",
    )
    second = service.persist_analysis(
        user_id=user.id,
        portfolio_id=portfolio.id,
        analysis_type="portfolio-analysis",
        result_payload={"run": 2},
        model_version="model-v1",
        formula_version="formula-v1",
    )

    assert first.id != second.id
    assert db_session.query(AiAnalysis).count() == 2


def test_formula_version_can_be_null_and_non_null_value_is_preserved(db_session: Session) -> None:
    user = _add_user(db_session)
    service = AiAnalysisPersistenceService(db=db_session, repository=AiAnalysisRepository(db_session))

    nullable_formula = service.persist_analysis(
        user_id=user.id,
        portfolio_id=None,
        analysis_type="chat",
        result_payload={"answer": "ok"},
        model_version="model-v1",
        formula_version=None,
    )
    formula_value = service.persist_analysis(
        user_id=user.id,
        portfolio_id=None,
        analysis_type="robustness",
        result_payload={"score": "0.9"},
        model_version="model-v1",
        formula_version="formula-v2",
    )

    assert nullable_formula.formula_version is None
    assert formula_value.formula_version == "formula-v2"


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"analysis_type": "   "}, "analysis_type"),
        ({"model_version": "   "}, "model_version"),
        ({"formula_version": "   "}, "formula_version"),
    ],
)
def test_service_rejects_blank_version_and_type_fields(
    db_session: Session,
    kwargs: dict[str, Any],
    expected_message: str,
) -> None:
    user = _add_user(db_session)
    service = AiAnalysisPersistenceService(db=db_session, repository=AiAnalysisRepository(db_session))
    payload = {
        "user_id": user.id,
        "portfolio_id": None,
        "analysis_type": "chat",
        "result_payload": {"ok": True},
        "model_version": "model-v1",
        "formula_version": None,
    }
    payload.update(kwargs)

    with pytest.raises(ValueError, match=expected_message):
        service.persist_analysis(**payload)


@pytest.mark.parametrize("result_payload", [["list"], "text", 1, None])
def test_service_requires_result_payload_dict(
    db_session: Session,
    result_payload: Any,
) -> None:
    user = _add_user(db_session)
    service = AiAnalysisPersistenceService(db=db_session, repository=AiAnalysisRepository(db_session))

    with pytest.raises(ValueError, match="result_payload"):
        service.persist_analysis(
            user_id=user.id,
            portfolio_id=None,
            analysis_type="chat",
            result_payload=result_payload,
            model_version="model-v1",
        )


def test_db_rejects_blank_analysis_type_model_version_and_formula_version(db_session: Session) -> None:
    user = _add_user(db_session)
    for kwargs in (
        {"analysis_type": "   "},
        {"model_version": "   "},
        {"formula_version": "   "},
    ):
        db_session.add(_analysis(user_id=user.id, **kwargs))
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()
        user = _add_user(db_session, email=f"user{len(kwargs)}@example.com")


def test_repository_get_by_id_and_ordering_created_at_desc_then_id_desc(db_session: Session) -> None:
    user = _add_user(db_session)
    repository = AiAnalysisRepository(db_session)
    older = repository.add(
        _analysis(
            user_id=user.id,
            created_at=datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc),
        )
    )
    same_time_first = repository.add(
        _analysis(
            user_id=user.id,
            result_payload={"run": 1},
            created_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
        )
    )
    same_time_second = repository.add(
        _analysis(
            user_id=user.id,
            result_payload={"run": 2},
            created_at=datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc),
        )
    )

    result = repository.list_by_user(user_id=user.id)

    assert repository.get_by_id(same_time_first.id) is same_time_first
    assert same_time_second.id > same_time_first.id > older.id
    assert result == [same_time_second, same_time_first, older]


def test_repository_user_isolation_in_list_and_count(db_session: Session) -> None:
    selected_user = _add_user(db_session, email="selected@example.com")
    other_user = _add_user(db_session, email="other@example.com")
    repository = AiAnalysisRepository(db_session)
    selected = repository.add(_analysis(user_id=selected_user.id))
    repository.add(_analysis(user_id=other_user.id))

    assert repository.list_by_user(user_id=selected_user.id) == [selected]
    assert repository.count_by_user(user_id=selected_user.id) == 1


def test_repository_portfolio_and_user_isolation_in_list_and_count(db_session: Session) -> None:
    selected_user = _add_user(db_session, email="selected@example.com")
    other_user = _add_user(db_session, email="other@example.com")
    selected_portfolio = _add_portfolio(db_session, user_id=selected_user.id, name="Selected")
    other_portfolio = _add_portfolio(db_session, user_id=selected_user.id, name="Other")
    repository = AiAnalysisRepository(db_session)
    selected = repository.add(_analysis(user_id=selected_user.id, portfolio_id=selected_portfolio.id))
    repository.add(_analysis(user_id=selected_user.id, portfolio_id=other_portfolio.id))
    repository.add(_analysis(user_id=other_user.id, portfolio_id=selected_portfolio.id))

    assert repository.list_by_portfolio_for_user(
        portfolio_id=selected_portfolio.id,
        user_id=selected_user.id,
    ) == [selected]
    assert repository.count_by_portfolio_for_user(
        portfolio_id=selected_portfolio.id,
        user_id=selected_user.id,
    ) == 1


def test_repository_add_flushes_but_does_not_commit(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _add_user(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    created = AiAnalysisRepository(db_session).add(_analysis(user_id=user.id))

    assert created.id is not None
    assert commit_calls == 0


def test_service_commits_exactly_once(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _add_user(db_session)
    commit_calls = 0

    def counting_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1

    monkeypatch.setattr(db_session, "commit", counting_commit)

    created = AiAnalysisPersistenceService(
        db=db_session,
        repository=AiAnalysisRepository(db_session),
    ).persist_analysis(
        user_id=user.id,
        portfolio_id=None,
        analysis_type="chat",
        result_payload={"ok": True},
        model_version="model-v1",
    )

    assert created.id is not None
    assert commit_calls == 1


def test_service_rolls_back_on_failure(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    user = _add_user(db_session)
    rollback_calls = 0

    def failing_add(analysis: AiAnalysis) -> AiAnalysis:
        raise RuntimeError("db failure")

    def counting_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1

    repository = AiAnalysisRepository(db_session)
    monkeypatch.setattr(repository, "add", failing_add)
    monkeypatch.setattr(db_session, "rollback", counting_rollback)

    with pytest.raises(RuntimeError, match="db failure"):
        AiAnalysisPersistenceService(db=db_session, repository=repository).persist_analysis(
            user_id=user.id,
            portfolio_id=None,
            analysis_type="chat",
            result_payload={"ok": True},
            model_version="model-v1",
        )

    assert rollback_calls == 1


def test_dependency_factories_return_repository_and_persistence_service(db_session: Session) -> None:
    repository = dependencies.get_ai_analysis_repository(db_session)
    service = dependencies.get_ai_analysis_persistence_service(db_session, repository)

    assert isinstance(repository, AiAnalysisRepository)
    assert isinstance(service, AiAnalysisPersistenceService)
    assert service.db is db_session
    assert service.repository is repository


def test_repository_and_service_sources_expose_no_update_or_delete_api() -> None:
    repository_source = REPOSITORY_SOURCE.read_text(encoding="utf-8")
    service_source = SERVICE_SOURCE.read_text(encoding="utf-8")

    for source in (repository_source, service_source):
        assert "def update" not in source
        assert "def delete" not in source
        assert ".delete(" not in source
        assert ".update(" not in source


def test_no_raw_request_or_context_persistence_fields_are_introduced() -> None:
    forbidden_columns = {
        "request_payload",
        "input_payload",
        "recent_news",
        "report_chunks",
        "report_chunk",
        "context_payload",
        "prompt",
    }

    assert forbidden_columns.isdisjoint(set(AiAnalysis.__table__.c.keys()))