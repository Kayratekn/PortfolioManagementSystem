from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.model.user import User
from src.model.user_expert_source import UserExpertSource
from src.repositories.expert_source_repository import ExpertSourceRepository
from src.repositories.user_expert_source_repository import UserExpertSourceRepository
from src.response.expert_source_response import UserExpertSourceListResponse, UserExpertSourceResponse


class UserExpertSourceService:
    def __init__(self, *, db: Session, expert_source_repository: ExpertSourceRepository, repository: UserExpertSourceRepository) -> None:
        self.db = db
        self.expert_source_repository = expert_source_repository
        self.repository = repository

    def create(self, *, expert_source_id: int, current_user: User) -> UserExpertSourceResponse:
        source = self.expert_source_repository.get_active_by_id(expert_source_id=expert_source_id)
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expert source not found.")
        if self.repository.get_by_user_and_expert_source(user_id=current_user.id, expert_source_id=source.id) is not None:
            self._duplicate()
        try:
            relation = self.repository.add(UserExpertSource(user_id=current_user.id, expert_source_id=source.id, is_enabled=True))
            self.db.commit()
            self.db.refresh(relation)
        except IntegrityError:
            self.db.rollback()
            self._duplicate()
        except Exception:
            self.db.rollback()
            raise
        return self._response(relation, source)

    def list_by_user(self, *, current_user: User, skip: int, limit: int) -> UserExpertSourceListResponse:
        rows = self.repository.list_by_user_with_expert_source(user_id=current_user.id, skip=skip, limit=limit)
        return UserExpertSourceListResponse(total=self.repository.count_by_user(user_id=current_user.id), skip=skip, limit=limit, items=[UserExpertSourceResponse(user_expert_source_id=row.id, expert_source_id=row.expert_source_id, source_key=row.source_key, author_name=row.author_name, author_handle=row.author_handle, profile_url=row.profile_url, is_enabled=row.is_enabled, created_at=row.created_at, updated_at=row.updated_at) for row in rows])

    def update(self, *, user_expert_source_id: int, is_enabled: bool, current_user: User) -> UserExpertSourceResponse:
        relation = self.repository.get_by_id_for_user(user_expert_source_id=user_expert_source_id, user_id=current_user.id)
        if relation is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User expert source not found.")
        source = self.expert_source_repository.get_by_id(expert_source_id=relation.expert_source_id)
        if is_enabled and (source is None or not source.is_active):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expert source not found.")
        if source is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Expert source not found.")
        try:
            updated = self.repository.update(relation, is_enabled=is_enabled)
            self.db.commit()
            self.db.refresh(updated)
        except Exception:
            self.db.rollback()
            raise
        return self._response(updated, source)

    @staticmethod
    def _response(relation: UserExpertSource, source) -> UserExpertSourceResponse:
        return UserExpertSourceResponse(user_expert_source_id=relation.id, expert_source_id=source.id, source_key=source.source_key, author_name=source.author_name, author_handle=source.author_handle, profile_url=source.profile_url, is_enabled=relation.is_enabled, created_at=relation.created_at, updated_at=relation.updated_at)

    @staticmethod
    def _duplicate() -> None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Expert source is already configured for user.")