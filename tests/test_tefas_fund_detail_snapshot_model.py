from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_detail_snapshot import TefasFundDetailSnapshot


def _build_asset() -> Asset:
    return Asset(
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        data_source="TEFAS",
    )


def _observed_at() -> datetime:
    return datetime(2026, 8, 14, 9, 0, tzinfo=timezone.utc)


def test_tefas_fund_detail_snapshot_table_name() -> None:
    assert TefasFundDetailSnapshot.__tablename__ == "tefas_fund_detail_snapshots"


def test_tefas_fund_detail_snapshot_columns_types_and_nullability() -> None:
    columns = TefasFundDetailSnapshot.__table__.c

    assert isinstance(columns.id.type, Integer)
    assert columns.id.primary_key is True
    assert columns.id.autoincrement is True

    assert isinstance(columns.asset_id.type, Integer)
    assert columns.asset_id.nullable is False

    assert isinstance(columns.fund_category.type, String)
    assert columns.fund_category.type.length == 255
    assert columns.fund_category.nullable is False

    assert isinstance(columns.category_rank.type, Integer)
    assert columns.category_rank.nullable is True

    assert isinstance(columns.category_fund_count.type, Integer)
    assert columns.category_fund_count.nullable is True

    assert isinstance(columns.market_share_raw.type, Numeric)
    assert columns.market_share_raw.type.precision == 20
    assert columns.market_share_raw.type.scale == 10
    assert columns.market_share_raw.nullable is True

    assert isinstance(columns.risk_value.type, Integer)
    assert columns.risk_value.nullable is True

    assert isinstance(columns.tefas_status.type, String)
    assert columns.tefas_status.type.length == 255
    assert columns.tefas_status.nullable is True

    assert isinstance(columns.transaction_start_time.type, String)
    assert columns.transaction_start_time.type.length == 20
    assert columns.transaction_start_time.nullable is True

    assert isinstance(columns.transaction_end_time.type, String)
    assert columns.transaction_end_time.type.length == 20
    assert columns.transaction_end_time.nullable is True

    assert isinstance(columns.entry_commission_raw.type, Numeric)
    assert columns.entry_commission_raw.type.precision == 20
    assert columns.entry_commission_raw.type.scale == 10
    assert columns.entry_commission_raw.nullable is True

    assert isinstance(columns.exit_commission_raw.type, Numeric)
    assert columns.exit_commission_raw.type.precision == 20
    assert columns.exit_commission_raw.type.scale == 10
    assert columns.exit_commission_raw.nullable is True

    assert isinstance(columns.interest_content.type, String)
    assert columns.interest_content.type.length == 255
    assert columns.interest_content.nullable is True

    assert isinstance(columns.fund_sale_valor.type, Integer)
    assert columns.fund_sale_valor.nullable is True

    assert isinstance(columns.fund_redemption_valor.type, Integer)
    assert columns.fund_redemption_valor.nullable is True

    assert isinstance(columns.source_page.type, String)
    assert columns.source_page.type.length == 100
    assert columns.source_page.nullable is False

    assert isinstance(columns.observed_at.type, DateTime)
    assert columns.observed_at.type.timezone is True
    assert columns.observed_at.nullable is False


def test_tefas_fund_detail_snapshot_foreign_key_targets_assets_id() -> None:
    foreign_keys = TefasFundDetailSnapshot.__table__.c.asset_id.foreign_keys

    assert len(foreign_keys) == 1
    foreign_key = next(iter(foreign_keys))
    assert foreign_key.target_fullname == "assets.id"
    assert foreign_key.ondelete is None


def test_tefas_fund_detail_snapshot_source_page_default_matches_source_page() -> None:
    column = TefasFundDetailSnapshot.__table__.c.source_page

    assert column.default is not None
    assert column.default.arg == "fon-detayli-analiz"
    assert column.server_default is not None
    assert "fon-detayli-analiz" in str(column.server_default.arg)


def test_tefas_fund_detail_snapshot_timestamp_mixin_fields_are_present() -> None:
    columns = TefasFundDetailSnapshot.__table__.c

    assert "created_at" in columns
    assert "updated_at" in columns
    assert isinstance(columns.created_at.type, DateTime)
    assert isinstance(columns.updated_at.type, DateTime)
    assert columns.created_at.type.timezone is True
    assert columns.updated_at.type.timezone is True


def test_tefas_fund_detail_snapshot_constraints_are_named() -> None:
    constraints = {constraint.name: constraint for constraint in TefasFundDetailSnapshot.__table__.constraints}

    assert isinstance(
        constraints["uq_tefas_fund_detail_snapshots_asset_observed_at"],
        UniqueConstraint,
    )
    assert [
        column.name
        for column in constraints["uq_tefas_fund_detail_snapshots_asset_observed_at"].columns
    ] == ["asset_id", "observed_at"]

    assert isinstance(
        constraints["ck_tefas_fund_detail_snapshots_category_rank_nonnegative"],
        CheckConstraint,
    )
    assert isinstance(
        constraints["ck_tefas_fund_detail_snapshots_category_fund_count_nonnegative"],
        CheckConstraint,
    )
    assert isinstance(
        constraints["ck_tefas_fund_detail_snapshots_risk_value_range"],
        CheckConstraint,
    )


def test_tefas_fund_detail_snapshot_declares_only_category_observed_at_index() -> None:
    indexes = {index.name: index for index in TefasFundDetailSnapshot.__table__.indexes}

    assert set(indexes) == {"ix_tefas_fund_detail_snapshots_category_observed_at"}
    assert [
        column.name
        for column in indexes["ix_tefas_fund_detail_snapshots_category_observed_at"].columns
    ] == ["fund_category", "observed_at"]
    assert indexes["ix_tefas_fund_detail_snapshots_category_observed_at"].unique is False


def test_tefas_fund_detail_snapshot_semantics_can_be_represented(db_session: Session) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.commit()

    snapshot = TefasFundDetailSnapshot(
        asset_id=asset.id,
        fund_category="Serbest Fon",
        category_rank=0,
        category_fund_count=None,
        market_share_raw=Decimal("0.0100000000"),
        risk_value=3,
        tefas_status="TEFAS'ta Islem Gormektedir",
        transaction_start_time="09:00",
        transaction_end_time="13:30",
        entry_commission_raw=Decimal("3"),
        exit_commission_raw=Decimal("2.5"),
        interest_content="Faiz icermez",
        fund_sale_valor=0,
        fund_redemption_valor=3,
        observed_at=_observed_at(),
    )

    db_session.add(snapshot)
    db_session.commit()
    db_session.refresh(snapshot)

    assert snapshot.id is not None
    assert snapshot.fund_category == "Serbest Fon"
    assert snapshot.category_rank == 0
    assert snapshot.category_fund_count is None
    assert snapshot.market_share_raw == Decimal("0.0100000000")
    assert snapshot.risk_value == 3
    assert snapshot.tefas_status == "TEFAS'ta Islem Gormektedir"
    assert snapshot.transaction_start_time == "09:00"
    assert snapshot.transaction_end_time == "13:30"
    assert snapshot.entry_commission_raw == Decimal("3.0000000000")
    assert snapshot.exit_commission_raw == Decimal("2.5000000000")
    assert snapshot.interest_content == "Faiz icermez"
    assert snapshot.fund_sale_valor == 0
    assert snapshot.fund_redemption_valor == 3
    assert snapshot.source_page == "fon-detayli-analiz"
    assert snapshot.observed_at == _observed_at().replace(tzinfo=None)


def test_tefas_fund_detail_snapshot_unique_constraint_rejects_same_asset_and_observed_at(
    db_session: Session,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.commit()

    first_snapshot = TefasFundDetailSnapshot(
        asset_id=asset.id,
        fund_category="Serbest Fon",
        observed_at=_observed_at(),
    )
    second_snapshot = TefasFundDetailSnapshot(
        asset_id=asset.id,
        fund_category="Para Piyasas? Fonu",
        observed_at=_observed_at(),
    )

    db_session.add(first_snapshot)
    db_session.commit()

    db_session.add(second_snapshot)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize(
    "field_name",
    ["category_rank", "category_fund_count"],
)
def test_tefas_fund_detail_snapshot_rejects_negative_category_fields(
    db_session: Session,
    field_name: str,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.commit()

    values = {
        "asset_id": asset.id,
        "fund_category": "Serbest Fon",
        "observed_at": _observed_at(),
        field_name: -1,
    }
    db_session.add(TefasFundDetailSnapshot(**values))

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


@pytest.mark.parametrize("risk_value", [0, 8])
def test_tefas_fund_detail_snapshot_rejects_out_of_range_risk_value(
    db_session: Session,
    risk_value: int,
) -> None:
    asset = _build_asset()
    db_session.add(asset)
    db_session.commit()

    db_session.add(
        TefasFundDetailSnapshot(
            asset_id=asset.id,
            fund_category="Serbest Fon",
            risk_value=risk_value,
            observed_at=_observed_at(),
        )
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_tefas_fund_detail_snapshot_migration_uses_current_head_and_expected_names() -> None:
    migration_text = Path(
        "alembic/versions/20260814_0007_create_tefas_fund_detail_snapshots.py"
    ).read_text()

    assert 'revision = "20260814_0007"' in migration_text
    assert 'down_revision = "20260812_0006"' in migration_text
    assert "tefas_fund_detail_snapshots" in migration_text
    assert "uq_tefas_fund_detail_snapshots_asset_observed_at" in migration_text
    assert "ck_tefas_fund_detail_snapshots_category_rank_nonnegative" in migration_text
    assert "ck_tefas_fund_detail_snapshots_category_fund_count_nonnegative" in migration_text
    assert "ix_tefas_fund_detail_snapshots_category_observed_at" in migration_text
    assert "ix_tefas_fund_detail_snapshots_asset_observed_at" not in migration_text

def test_tefas_fund_detail_snapshot_risk_value_migration_uses_expected_names() -> None:
    migration_text = Path(
        "alembic/versions/20260817_0008_add_tefas_fund_detail_snapshot_risk_value.py"
    ).read_text()

    assert 'revision = "20260817_0008"' in migration_text
    assert 'down_revision = "20260814_0007"' in migration_text
    assert 'op.batch_alter_table("tefas_fund_detail_snapshots")' in migration_text
    assert "batch_op.add_column" in migration_text
    assert "batch_op.create_check_constraint" in migration_text
    assert "batch_op.drop_constraint" in migration_text
    assert "batch_op.drop_column" in migration_text
    assert "risk_value" in migration_text
    assert "ck_tefas_fund_detail_snapshots_risk_value_range" in migration_text


def test_tefas_fund_detail_snapshot_profile_metadata_migration_uses_expected_names() -> None:
    migration_text = Path(
        "alembic/versions/20260823_0011_add_tefas_profile_metadata_to_detail_snapshots.py"
    ).read_text()

    assert 'revision = "20260823_0011"' in migration_text
    assert 'down_revision = "20260820_0010"' in migration_text
    assert 'op.batch_alter_table("tefas_fund_detail_snapshots")' in migration_text
    assert migration_text.count("batch_op.add_column") == 8
    assert migration_text.count("batch_op.drop_column") == 8
    assert "tefas_status" in migration_text
    assert "transaction_start_time" in migration_text
    assert "transaction_end_time" in migration_text
    assert "entry_commission_raw" in migration_text
    assert "exit_commission_raw" in migration_text
    assert "interest_content" in migration_text
    assert "fund_sale_valor" in migration_text
    assert "fund_redemption_valor" in migration_text
