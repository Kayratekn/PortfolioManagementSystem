from pydantic import BaseModel, ConfigDict, Field


class UserExpertSourceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expert_source_id: int = Field(strict=True, gt=0)


class UserExpertSourceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_enabled: bool = Field(strict=True)