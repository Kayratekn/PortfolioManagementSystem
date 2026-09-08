from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.expert_source import ExpertSource


class ExpertSourceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, *, expert_source_id: int) -> ExpertSource | None:
        return self.db.get(ExpertSource, expert_source_id)

    def get_active_by_id(self, *, expert_source_id: int) -> ExpertSource | None:
        return self.db.scalar(select(ExpertSource).where(ExpertSource.id == expert_source_id, ExpertSource.is_active.is_(True)))

    def get_by_source_and_handle(self, *, source_key: str, author_handle: str) -> ExpertSource | None:
        return self.db.scalar(select(ExpertSource).where(ExpertSource.source_key == source_key, ExpertSource.author_handle == author_handle))

    def list_active(self, *, skip: int, limit: int) -> list[ExpertSource]:
        statement = select(ExpertSource).where(ExpertSource.is_active.is_(True)).order_by(ExpertSource.source_key.asc(), ExpertSource.author_handle.asc(), ExpertSource.id.asc()).offset(skip).limit(limit)
        return list(self.db.scalars(statement))

    def count_active(self) -> int:
        return int(self.db.scalar(select(func.count(ExpertSource.id)).where(ExpertSource.is_active.is_(True))) or 0)