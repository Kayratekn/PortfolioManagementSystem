from __future__ import annotations

from src.model.asset import Asset
from src.response.asset_response import AssetListResponse, AssetResponse


def _build_asset() -> Asset:
    return Asset(
        id=11,
        asset_code="AAL",
        asset_name="Example Fund",
        asset_type="FUND",
        fund_kind="YAT",
        isin=None,
        currency=None,
        data_source="TEFAS",
        is_active=True,
    )


def test_asset_response_exposes_catalog_fields_only() -> None:
    response = AssetResponse.model_validate(_build_asset())

    body = response.model_dump()

    assert body == {
        "id": 11,
        "asset_code": "AAL",
        "asset_name": "Example Fund",
        "asset_type": "FUND",
        "fund_kind": "YAT",
        "isin": None,
        "currency": None,
        "data_source": "TEFAS",
    }
    assert "is_active" not in body
    assert "created_at" not in body
    assert "updated_at" not in body


def test_asset_list_response_preserves_pagination_metadata() -> None:
    item = AssetResponse.model_validate(_build_asset())

    response = AssetListResponse(items=[item], total=1, skip=0, limit=50)

    assert response.items == [item]
    assert response.total == 1
    assert response.skip == 0
    assert response.limit == 50
