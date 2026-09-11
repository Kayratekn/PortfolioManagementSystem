from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.model.note import Note
from src.model.user import User
from src.repositories.note_repository import NoteRepository
from src.repositories.portfolio_repository import PortfolioRepository
from src.response.note_response import NoteListResponse, NoteResponse


class NoteService:
    def __init__(
        self,
        db: Session,
        note_repository: NoteRepository,
        portfolio_repository: PortfolioRepository,
    ) -> None:
        self.db = db
        self.note_repository = note_repository
        self.portfolio_repository = portfolio_repository

    def create_note(self, *, portfolio_id: int, note_text: str, current_user: User) -> NoteResponse:
        portfolio = self.portfolio_repository.get_by_id_for_user(portfolio_id, current_user.id)
        if portfolio is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")

        note = Note(user_id=current_user.id, portfolio_id=portfolio_id, note_text=note_text)
        try:
            created_note = self.note_repository.add(note)
            self.db.commit()
            self.db.refresh(created_note)
        except Exception:
            self.db.rollback()
            raise
        return NoteResponse.model_validate(created_note)

    def list_notes(self, *, current_user: User, skip: int, limit: int) -> NoteListResponse:
        notes = self.note_repository.list_by_user(user_id=current_user.id, skip=skip, limit=limit)
        total = self.note_repository.count_by_user(user_id=current_user.id)
        return NoteListResponse(
            items=[NoteResponse.model_validate(note) for note in notes],
            total=total,
            skip=skip,
            limit=limit,
        )

    def update_note(self, *, note_id: int, note_text: str, current_user: User) -> NoteResponse:
        note = self._get_owned_note(note_id=note_id, current_user=current_user)
        note.note_text = note_text
        try:
            updated_note = self.note_repository.update(note)
            self.db.commit()
            self.db.refresh(updated_note)
        except Exception:
            self.db.rollback()
            raise
        return NoteResponse.model_validate(updated_note)

    def delete_note(self, *, note_id: int, current_user: User) -> None:
        note = self._get_owned_note(note_id=note_id, current_user=current_user)
        try:
            self.note_repository.delete(note)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _get_owned_note(self, *, note_id: int, current_user: User) -> Note:
        note = self.note_repository.get_by_id_for_user(note_id=note_id, user_id=current_user.id)
        if note is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
        return note
