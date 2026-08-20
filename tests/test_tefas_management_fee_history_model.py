from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import DateTime, Integer, Numeric, String

from src.model.tefas_management_fee_history import TefasManagementFeeHistory


def test_tefas_management_fee_history_table_name() -> None:
    assert TefasManagementFeeHistory.__tablename__ == "tefas_management_fee_history"


def test_tefas_management_fee_history_required_fields_and_nullability() -> None:
    columns = TefasManagementFeeHistory.__table__.c

    assert isinstance(columns.id.type, Integer)
    assert columns.id.primary_key is True
    assert columns.id.autoincrement is True

    assert isinstance(columns.asset_id.type, Integer)
    assert columns.asset_id.nullable is False

    assert isinstance(columns.management_fee_percentage.type, Numeric)
    assert columns.management_fee_percentage.type.precision == 18
    assert columns.management_fee_percentage.type.scale == 6
    assert columns.management_fee_percentage.nullable is False

    assert isinstance(columns.source_endpoint.type, String)
    assert columns.source_endpoint.type.length == 100
    assert columns.source_endpoint.nullable is False

    assert isinstance(columns.source_field_name.type, String)
    assert columns.source_field_name.type.length == 50
    assert columns.source_field_name.nullable is False

    assert columns.first_observed_at.nullable is False
    assert columns.last_observed_at.nullable is False
    assert columns.closed_at.nullable is True


def test_tefas_management_fee_history_foreign_key_targets_assets_id() -> None:
    foreign_keys = TefasManagementFeeHistory.__table__.c.asset_id.foreign_keys

    assert len(foreign_keys) == 1
    foreign_key = next(iter(foreign_keys))
    assert foreign_key.target_fullname == "assets.id"
    assert foreign_key.ondelete is None


def test_observation_timestamp_columns_are_timezone_aware_datetime_columns() -> None:
    columns = TefasManagementFeeHistory.__table__.c

    for column_name in ("first_observed_at", "last_observed_at", "closed_at"):
        column_type = columns[column_name].type
        assert isinstance(column_type, DateTime)
        assert column_type.timezone is True


def test_timestamp_mixin_fields_are_present() -> None:
    columns = TefasManagementFeeHistory.__table__.c

    assert "created_at" in columns
    assert "updated_at" in columns
    assert isinstance(columns.created_at.type, DateTime)
    assert isinstance(columns.updated_at.type, DateTime)
    assert columns.created_at.type.timezone is True
    assert columns.updated_at.type.timezone is True


def test_model_declares_expected_indexes() -> None:
    indexes = {index.name: index for index in TefasManagementFeeHistory.__table__.indexes}

    assert set(indexes) == {
        "ix_tefas_management_fee_history_asset_first_observed_at",
        "ix_tefas_management_fee_history_fee_closed_at",
        "uq_tefas_management_fee_history_one_open_per_asset",
    }
    asset_index = indexes["ix_tefas_management_fee_history_asset_first_observed_at"]
    fee_index = indexes["ix_tefas_management_fee_history_fee_closed_at"]
    open_index = indexes["uq_tefas_management_fee_history_one_open_per_asset"]
    assert [column.name for column in asset_index.columns] == [
        "asset_id",
        "first_observed_at",
    ]
    assert [column.name for column in fee_index.columns] == [
        "management_fee_percentage",
        "closed_at",
    ]
    assert [column.name for column in open_index.columns] == ["asset_id"]
    assert asset_index.unique is False
    assert fee_index.unique is False
    assert open_index.unique is True
    assert str(open_index.dialect_options["postgresql"]["where"]) == "closed_at IS NULL"


def test_postgresql_partial_unique_index_is_defined_in_migration() -> None:
    migration_text = Path(
        "alembic/versions/20260820_0010_create_tefas_management_fee_history.py"
    ).read_text()

    assert 'down_revision = "20260819_0009"' in migration_text
    assert "uq_tefas_management_fee_history_one_open_per_asset" in migration_text
    assert "unique=True" in migration_text
    assert 'postgresql_where=sa.text("closed_at IS NULL")' in migration_text


def test_no_fund_kind_column_is_declared() -> None:
    assert "fund_kind" not in TefasManagementFeeHistory.__table__.c


def test_observation_timestamp_semantics_example_can_be_represented() -> None:
    first_seen = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
    last_seen = datetime(2026, 8, 8, 9, 0, tzinfo=timezone.utc)
    closed_at = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)

    history = TefasManagementFeeHistory(
        asset_id=1,
        management_fee_percentage=Decimal("1.000000"),
        source_endpoint="fonYonetimBazliBilgiGetir",
        source_field_name="uygulananYu1Y",
        first_observed_at=first_seen,
        last_observed_at=last_seen,
        closed_at=closed_at,
    )

    assert history.management_fee_percentage == Decimal("1.000000")
    assert history.first_observed_at == first_seen
    assert history.last_observed_at == last_seen
    assert history.closed_at == closed_at
