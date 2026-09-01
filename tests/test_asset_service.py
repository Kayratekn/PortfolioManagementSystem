from __future__ import annotations

from types import SimpleNamespace

from src.services.asset_service import AssetService


class FakeAssetRepository:
    def __init__(self) -> None:
        self.list_calls: list[dict[str, object]] = []
        self.count_calls: list[dict[str, object]] = []
        self.assets = [
            SimpleNamespace(
                id=7,
                asset_code="AAL",
                asset_name="Example Fund",
                asset_type="FUND",
                fund_kind="YAT",
                isin=None,
                currency=None,
                data_source="TEFAS",
            )
        ]

    def list_active_catalog(
        self,
        *,
        skip: int,
        limit: int,
        search: str | None = None,
    ) -> list[SimpleNamespace]:
        self.list_calls.append({"skip": skip, "limit": limit, "search": search})
        return self.assets

    def count_active_catalog(self, *, search: str | None = None) -> int:
        self.count_calls.append({"search": search})
        return 3


def test_list_assets_returns_catalog_response_and_forwards_query() -> None:
    repository = FakeAssetRepository()
    service = AssetService(repository)

    result = service.list_assets(skip=1, limit=2, search="aal")

    assert repository.list_calls == [{"skip": 1, "limit": 2, "search": "aal"}]
    assert repository.count_calls == [{"search": "aal"}]
    assert result.total == 3
    assert result.skip == 1
    assert result.limit == 2
    assert len(result.items) == 1
    assert result.items[0].asset_code == "AAL"
    assert result.items[0].isin is None
    assert result.items[0].currency is None
