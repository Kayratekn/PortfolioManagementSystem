from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.request.note_request import NoteCreateRequest, NoteUpdateRequest


def test_note_request_trims_note_text() -> None:
    payload = NoteCreateRequest(portfolio_id=1, note_text="  hello  ")

    assert payload.note_text == "hello"


@pytest.mark.parametrize("note_text", ["", "   "])
def test_note_request_rejects_blank_after_trimming(note_text: str) -> None:
    with pytest.raises(ValidationError):
        NoteCreateRequest(portfolio_id=1, note_text=note_text)


def test_note_request_accepts_2000_characters_after_trimming() -> None:
    payload = NoteCreateRequest(portfolio_id=1, note_text=" " + "a" * 2000 + " ")

    assert payload.note_text == "a" * 2000


def test_note_request_rejects_more_than_2000_characters() -> None:
    with pytest.raises(ValidationError):
        NoteCreateRequest(portfolio_id=1, note_text="a" * 2001)


def test_note_request_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        NoteCreateRequest(portfolio_id=1, note_text="hello", title="x")  # type: ignore[call-arg]


def test_note_update_request_trims_text_and_forbids_extra_fields() -> None:
    payload = NoteUpdateRequest(note_text="  updated  ")

    assert payload.note_text == "updated"
    with pytest.raises(ValidationError):
        NoteUpdateRequest(note_text="updated", portfolio_id=1)  # type: ignore[call-arg]


@pytest.mark.parametrize("note_text", ["", "   ", "a" * 2001])
def test_note_update_request_rejects_invalid_text(note_text: str) -> None:
    with pytest.raises(ValidationError):
        NoteUpdateRequest(note_text=note_text)


@pytest.mark.parametrize("portfolio_id", [0, -1])
def test_note_request_requires_positive_portfolio_id(portfolio_id: int) -> None:
    with pytest.raises(ValidationError):
        NoteCreateRequest(portfolio_id=portfolio_id, note_text="hello")
