from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class PdfExtractionError(RuntimeError):
    pass


class EncryptedPdfError(PdfExtractionError):
    pass


@dataclass(frozen=True)
class ExtractedPdfPage:
    page_number: int
    text: str


class PdfTextExtractor:
    def extract(self, path: Path) -> list[ExtractedPdfPage]:
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            if reader.is_encrypted:
                raise EncryptedPdfError("Encrypted PDF files are not supported.")

            return [
                ExtractedPdfPage(
                    page_number=page_number,
                    text=page.extract_text() or "",
                )
                for page_number, page in enumerate(reader.pages, start=1)
            ]
        except EncryptedPdfError:
            raise
        except Exception as exc:
            raise PdfExtractionError("PDF file could not be read.") from exc
