from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.model.note import Note


class NoteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, note: Note) -> Note:
        self.db.add(note)
        self.db.flush()
        return note

    def get_by_id_for_user(self, *, note_id: int, user_id: int) -> Note | None:
        statement = select(Note).where(Note.id == note_id, Note.user_id == user_id)
        return self.db.scalar(statement)

    def update(self, note: Note) -> Note:
        self.db.flush()
        return note

    def delete(self, note: Note) -> None:
        self.db.delete(note)
        self.db.flush()

    def list_by_user(self, *, user_id: int, skip: int, limit: int) -> list[Note]:
        statement = (
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.created_at.desc(), Note.id.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self.db.scalars(statement))

    def count_by_user(self, *, user_id: int) -> int:
        statement = select(func.count(Note.id)).where(Note.user_id == user_id)
        return int(self.db.scalar(statement) or 0)
