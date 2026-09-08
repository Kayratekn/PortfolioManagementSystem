from datetime import datetime

from pydantic import BaseModel


class ExpertSourceResponse(BaseModel):
    expert_source_id: int
    source_key: str
    author_name: str | None
    author_handle: str
    profile_url: str | None


class ExpertSourceListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[ExpertSourceResponse]


class UserExpertSourceResponse(ExpertSourceResponse):
    user_expert_source_id: int
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class UserExpertSourceListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[UserExpertSourceResponse]


class SentimentPostResponse(BaseModel):
    post_id: int
    expert_source_id: int
    source_key: str
    title: str | None
    content: str
    author_name: str | None
    author_handle: str | None
    url: str | None
    published_at: datetime
    fetched_at: datetime
    content_type: str
    language: str


class SentimentPostListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[SentimentPostResponse]