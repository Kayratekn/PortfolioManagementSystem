from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from src.model.asset import Asset
from src.model.tefas_fund_allocation_data import TefasFundAllocationData
from src.repositories.asset_repository import AssetRepository
from src.repositories.tefas_fund_allocation_data_repository import (
    TefasFundAllocationDataRepository,
    TefasFundAllocationRowCreate,
)
from src.services.tefas_fund_allocation_read_service import TefasFundAllocationReadService


def _create_asset(
    db_session: Session,
    *,
    asset_code: str = "AB1",
    asset_name: str = "AB1 GAYRIMENKUL YATIRIM FONU",
) -> Asset:
    asset = Asset(
        asset_code=asset_code,
        asset_name=asset_name,
        asset_type="FUND",
        fund_kind="GYF",
        currency=None,
        data_source="TEFAS",
        is_active=True,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _create_service(db_session: Session) -> TefasFundAllocationReadService:
    return TefasFundAllocationReadService(
        asset_repository=AssetRepository(db_session),
        allocation_repository=TefasFundAllocationDataRepository(db_session),
    )


def _replace_allocations(
    db_session: Session,
    *,
    asset_id: int,
    rows: list[tuple[str, Decimal]],
    data_date: date = date(2026, 8, 11),
) -> None:
    repository = TefasFundAllocationDataRepository(db_session)
    repository.replace_for_asset_and_date(
        asset_id=asset_id,
        data_date=data_date,
        rows=[
            TefasFundAllocationRowCreate(
                asset_id=asset_id,
                data_date=data_date,
                raw_field_name=raw_field_name,
                allocation_percentage=allocation_percentage,
            )
            for raw_field_name, allocation_percentage in rows
        ],
    )
    db_session.commit()


def test_successful_ab1_like_read_returns_verified_label_and_decimal(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert response.fund_code == "AB1"
    assert response.fund_name == "AB1 GAYRIMENKUL YATIRIM FONU"
    assert response.data_date == date(2026, 8, 11)
    assert len(response.allocations) == 1
    allocation = response.allocations[0]
    assert allocation.label == "Gayrimenkul Yatırımları"
    assert allocation.raw_field_name is None
    assert allocation.mapping_status == "VERIFIED"
    assert allocation.percentage == Decimal("100.000000")
    assert isinstance(allocation.percentage, Decimal)


def test_fund_code_is_normalized_for_lookup(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code=" ab1 ",
        data_date=date(2026, 8, 11),
    )

    assert response.fund_code == "AB1"


def test_verified_mapping_does_not_expose_raw_abbreviation(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("hs", Decimal("10.000000"))],
    )
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert response.allocations[0].label == "Hisse Senedi"
    assert response.allocations[0].raw_field_name is None
    assert response.allocations[0].mapping_status == "VERIFIED"


def test_unresolved_mapping_preserves_raw_field_name(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("bb", Decimal("5.500000"))],
    )
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert response.allocations[0].label is None
    assert response.allocations[0].raw_field_name == "bb"
    assert response.allocations[0].mapping_status == "UNRESOLVED"
    assert response.allocations[0].percentage == Decimal("5.500000")


def test_mixed_rows_preserve_repository_raw_field_order(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[
            ("gyy", Decimal("100.000000")),
            ("bb", Decimal("5.500000")),
        ],
    )
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert [item.raw_field_name for item in response.allocations] == ["bb", None]
    assert [item.mapping_status for item in response.allocations] == ["UNRESOLVED", "VERIFIED"]


def test_decimal_zero_remains_decimal_zero(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("0.000000"))],
    )
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert response.allocations[0].percentage == Decimal("0.000000")
    assert isinstance(response.allocations[0].percentage, Decimal)


def test_negative_decimal_remains_negative(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("r", Decimal("-1.250000"))],
    )
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert response.allocations[0].percentage == Decimal("-1.250000")


def test_missing_tefas_asset_raises_not_found(db_session: Session) -> None:
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_fund_allocation(
            fund_code="AB1",
            data_date=date(2026, 8, 11),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "TEFAS fund not found."


def test_empty_normalized_fund_code_raises_not_found(db_session: Session) -> None:
    service = _create_service(db_session)

    with pytest.raises(HTTPException) as exc_info:
        service.get_fund_allocation(
            fund_code="   ",
            data_date=date(2026, 8, 11),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "TEFAS fund not found."


def test_existing_asset_with_no_allocation_rows_returns_empty_allocations(db_session: Session) -> None:
    _create_asset(db_session)
    service = _create_service(db_session)

    response = service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert response.fund_code == "AB1"
    assert response.allocations == []


def test_labels_and_statuses_are_response_only_and_do_not_mutate_rows(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )
    persisted_row = TefasFundAllocationDataRepository(db_session).list_by_asset_and_date(
        asset_id=asset.id,
        data_date=date(2026, 8, 11),
    )[0]
    service = _create_service(db_session)

    service.get_fund_allocation(
        fund_code="AB1",
        data_date=date(2026, 8, 11),
    )

    assert not hasattr(persisted_row, "label")
    assert not hasattr(persisted_row, "mapping_status")
    assert persisted_row.raw_field_name == "gyy"


def test_unknown_raw_field_fails_clearly(db_session: Session) -> None:
    asset = _create_asset(db_session)
    db_session.add(
        TefasFundAllocationData(
            asset_id=asset.id,
            data_date=date(2026, 8, 11),
            raw_field_name="unknown",
            allocation_percentage=Decimal("1.000000"),
        )
    )
    db_session.commit()
    service = _create_service(db_session)

    with pytest.raises(ValueError, match="Unknown TEFAS allocation raw field: unknown"):
        service.get_fund_allocation(
            fund_code="AB1",
            data_date=date(2026, 8, 11),
        )


def test_input_fund_code_string_is_not_mutated(db_session: Session) -> None:
    asset = _create_asset(db_session)
    _replace_allocations(
        db_session,
        asset_id=asset.id,
        rows=[("gyy", Decimal("100.000000"))],
    )
    service = _create_service(db_session)
    fund_code = " ab1 "

    service.get_fund_allocation(
        fund_code=fund_code,
        data_date=date(2026, 8, 11),
    )

    assert fund_code == " ab1 "
