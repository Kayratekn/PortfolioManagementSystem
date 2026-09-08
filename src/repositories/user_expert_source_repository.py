from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.expert_source import ExpertSource
from src.model.user_expert_source import UserExpertSource


@dataclass(frozen=True)
class UserExpertSourceWithExpert:
    id: int
    expert_source_id: int
    source_key: str
    author_name: str | None
    author_handle: str
    profile_url: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


class UserExpertSourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, relation: UserExpertSource) -> UserExpertSource:
        self.db.add(relation)
        self.db.flush()
        return relation

    def get_by_user_and_expert_source(self, *, user_id: int, expert_source_id: int) -> UserExpertSource | None:
        return self.db.scalar(select(UserExpertSource).where(UserExpertSource.user_id == user_id, UserExpertSource.expert_source_id == expert_source_id))

    def get_by_id_for_user(self, *, user_expert_source_id: int, user_id: int) -> UserExpertSource | None:
        return self.db.scalar(select(UserExpertSource).where(UserExpertSource.id == user_expert_source_id, UserExpertSource.user_id == user_id))

    def list_by_user_with_expert_source(self, *, user_id: int, skip: int, limit: int) -> list[UserExpertSourceWithExpert]:
        statement = select(UserExpertSource.id, UserExpertSource.expert_source_id, ExpertSource.source_key, ExpertSource.author_name, ExpertSource.author_handle, ExpertSource.profile_url, UserExpertSource.is_enabled, UserExpertSource.created_at, UserExpertSource.updated_at).join(ExpertSource, ExpertSource.id == UserExpertSource.expert_source_id).where(UserExpertSource.user_id == user_id).order_by(ExpertSource.source_key.asc(), ExpertSource.author_handle.asc(), UserExpertSource.id.asc()).offset(skip).limit(limit)
        return [UserExpertSourceWithExpert(*row) for row in self.db.execute(statement).all()]

    def count_by_user(self, *, user_id: int) -> int:
        return int(self.db.scalar(select(func.count(UserExpertSource.id)).where(UserExpertSource.user_id == user_id)) or 0)

    def update(self, relation: UserExpertSource, *, is_enabled: bool) -> UserExpertSource:
        relation.is_enabled = is_enabled
        self.db.flush()
        return relation