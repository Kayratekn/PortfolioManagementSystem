from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReportQaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(strict=True)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("Query must not be blank.")
        if len(normalized_value) > 2000:
            raise ValueError("Query must not exceed 2000 characters.")
        return normalized_value
