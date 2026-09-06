from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BenchmarkCatalogItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    benchmark_type: str
    native_currency: str
    index_owner: str
    return_type: str


class BenchmarkCatalogResponse(BaseModel):
    items: list[BenchmarkCatalogItemResponse]
    total: int