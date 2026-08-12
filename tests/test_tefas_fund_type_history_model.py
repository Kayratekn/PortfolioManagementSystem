from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import DateTime, Integer, String

from src.model.tefas_fund_type_history import TefasFundTypeHistory


def test_tefas_fund_type_history_table_name() -> None:
    assert TefasFundTypeHistory.__tablename__ == "tefas_fund_type_history"


def test_tefas_fund_type_history_required_fields_and_nullability() -> None:
    columns = TefasFundTypeHistory.__table__.c

    assert isinstance(columns.id.type, Integer)
    assert columns.id.primary_key is True
    assert columns.id.autoincrement is True

    assert isinstance(columns.asset_id.type, Integer)
    assert columns.asset_id.nullable is False

    assert isinstance(columns.fund_type_name.type, String)
    assert columns.fund_type_name.type.length == 255
    assert columns.fund_type_name.nullable is False

    assert isinstance(columns.source_endpoint.type, String)
    assert columns.source_endpoint.type.length == 100
    assert columns.source_endpoint.nullable is False

    assert isinstance(columns.source_field_name.type, String)
    assert columns.source_field_name.type.length == 50
    assert columns.source_field_name.nullable is False

    assert columns.first_observed_at.nullable is False
    assert columns.last_observed_at.nullable is False
    assert columns.closed_at.nullable is True


def test_tefas_fund_type_history_foreign_key_targets_assets_id() -> None:
    foreign_keys = TefasFundTypeHistory.__table__.c.asset_id.foreign_keys

    assert len(foreign_keys) == 1
    foreign_key = next(iter(foreign_keys))
    assert foreign_key.target_fullname == "assets.id"
    assert foreign_key.ondelete is None


def test_source_defaults_match_fon_profil_dty_getir_source() -> None:
    columns = TefasFundTypeHistory.__table__.c

    assert columns.source_endpoint.default is not None
    assert columns.source_endpoint.default.arg == "fonProfilDtyGetir"
    assert columns.source_endpoint.server_default is not None
    assert "fonProfilDtyGetir" in str(columns.source_endpoint.server_default.arg)

    assert columns.source_field_name.default is not None
    assert columns.source_field_name.default.arg == "fonTuru"
    assert columns.source_field_name.server_default is not None
    assert "fonTuru" in str(columns.source_field_name.server_default.arg)


def test_observation_timestamp_columns_are_timezone_aware_datetime_columns() -> None:
    columns = TefasFundTypeHistory.__table__.c

    for column_name in ("first_observed_at", "last_observed_at", "closed_at"):
        column_type = columns[column_name].type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True


def test_timestamp_mixin_fields_are_present() -> None:
    columns = TefasFundTypeHistory.__table__.c

    assert "created_at" in columns
    assert "updated_at" in columns
    assert isinstance(columns.created_at.type, DateTime)
    assert isinstance(columns.updated_at.type, DateTime)
    assert columns.created_at.type.timezone is True
    assert columns.updated_at.type.timezone is True


def test_model_declares_expected_non_unique_indexes() -> None:
    indexes = {index.name: index for index in TefasFundTypeHistory.__table__.indexes}

    assert set(indexes) == {
        "ix_tefas_fund_type_history_asset_first_observed_at",
        "ix_tefas_fund_type_history_type_closed_at",
    }
    assert [column.name for column in indexes["ix_tefas_fund_type_history_asset_first_observed_at"].columns] == [
        "asset_id",
        "first_observed_at",
    ]
    assert [column.name for column in indexes["ix_tefas_fund_type_history_type_closed_at"].columns] == [
        "fund_type_name",
        "closed_at",
    ]
    assert indexes["ix_tefas_fund_type_history_asset_first_observed_at"].unique is False
    assert indexes["ix_tefas_fund_type_history_type_closed_at"].unique is False


def test_postgresql_partial_unique_index_is_defined_in_migration_only() -> None:
    migration_text = Path(
        "alembic/versions/20260812_0006_create_tefas_fund_type_history.py"
    ).read_text()

    assert "uq_tefas_fund_type_history_one_open_per_asset" in migration_text
    assert "unique=True" in migration_text
    assert "postgresql_where=sa.text(\"closed_at IS NULL\")" in migration_text
    assert "uq_tefas_fund_type_history_one_open_per_asset" not in {
        index.name for index in TefasFundTypeHistory.__table__.indexes
    }


def test_observation_timestamp_semantics_example_can_be_represented() -> None:
    first_seen = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    last_seen = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)
    closed_at = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)

    history = TefasFundTypeHistory(
        asset_id=1,
        fund_type_name="Type A",
        first_observed_at=first_seen,
        last_observed_at=last_seen,
        closed_at=closed_at,
    )

    assert history.first_observed_at == first_seen
    assert history.last_observed_at == last_seen
    assert history.closed_at == closed_at