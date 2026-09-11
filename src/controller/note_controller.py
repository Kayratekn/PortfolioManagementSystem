from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from src.config.dependencies import get_current_user, get_note_service
from src.model.user import User
from src.request.note_request import NoteCreateRequest, NoteUpdateRequest
from src.response.note_response import NoteListResponse, NoteResponse
from src.services.note_service import NoteService


router = APIRouter(prefix="/api/v1/notes", tags=["notes"])


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    payload: NoteCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    note_service: Annotated[NoteService, Depends(get_note_service)],
) -> NoteResponse:
    return note_service.create_note(
        portfolio_id=payload.portfolio_id,
        note_text=payload.note_text,
        current_user=current_user,
    )


@router.get("", response_model=NoteListResponse)
def list_notes(
    current_user: Annotated[User, Depends(get_current_user)],
    note_service: Annotated[NoteService, Depends(get_note_service)],
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
) -> NoteListResponse:
    return note_service.list_notes(current_user=current_user, skip=skip, limit=limit)


@router.patch("/{note_id}", response_model=NoteResponse)
def update_note(
    note_id: int,
    payload: NoteUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    note_service: Annotated[NoteService, Depends(get_note_service)],
) -> NoteResponse:
    return note_service.update_note(
        note_id=note_id,
        note_text=payload.note_text,
        current_user=current_user,
    )


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    note_service: Annotated[NoteService, Depends(get_note_service)],
) -> Response:
    note_service.delete_note(note_id=note_id, current_user=current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
