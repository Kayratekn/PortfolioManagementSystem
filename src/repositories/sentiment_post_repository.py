from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.expert_source import ExpertSource
from src.model.sentiment_post import SentimentPost
from src.model.user_expert_source import UserExpertSource


@dataclass(frozen=True)
class SentimentPostFeedItem:
    id: int
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


class SentimentPostRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, post: SentimentPost) -> SentimentPost:
        self.db.add(post)
        self.db.flush()
        return post

    def list_for_user_enabled_sources(self, *, user_id: int, skip: int, limit: int) -> list[SentimentPostFeedItem]:
        statement = select(SentimentPost.id, SentimentPost.expert_source_id, SentimentPost.source_key, SentimentPost.title, SentimentPost.content, SentimentPost.author_name, SentimentPost.author_handle, SentimentPost.url, SentimentPost.published_at, SentimentPost.fetched_at, SentimentPost.content_type, SentimentPost.language).join(ExpertSource, ExpertSource.id == SentimentPost.expert_source_id).join(UserExpertSource, UserExpertSource.expert_source_id == ExpertSource.id).where(UserExpertSource.user_id == user_id, UserExpertSource.is_enabled.is_(True), ExpertSource.is_active.is_(True)).order_by(SentimentPost.published_at.desc(), SentimentPost.id.desc()).offset(skip).limit(limit)
        return [SentimentPostFeedItem(*row) for row in self.db.execute(statement).all()]

    def count_for_user_enabled_sources(self, *, user_id: int) -> int:
        statement = select(func.count(SentimentPost.id)).select_from(SentimentPost).join(ExpertSource, ExpertSource.id == SentimentPost.expert_source_id).join(UserExpertSource, UserExpertSource.expert_source_id == ExpertSource.id).where(UserExpertSource.user_id == user_id, UserExpertSource.is_enabled.is_(True), ExpertSource.is_active.is_(True))
        return int(self.db.scalar(statement) or 0)