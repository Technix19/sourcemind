"""Validate an upload and turn it into page-numbered chunks.

Knows nothing about HTTP: failures raise `IngestionError` with a status code
that the API layer maps onto the response. Uploaded content is untrusted data.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath

import pymupdf

from .chunking import chunk_text, clean_text
from .config import Settings

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}


class IngestionError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class PageChunk:
    page_number: int  # 1-based, matches the original PDF page
    chunk_index: int  # order within that page
    start: int
    end: int
    text: str


def content_type_for(filename: str) -> str:
    """The Content-Type WE choose for a stored file. Never taken from the client, so an uploaded
    file cannot make the storage server serve it as HTML or anything else active."""
    return "application/pdf" if PurePath(filename).suffix.lower() == ".pdf" else "text/plain"


def sanitize_filename(name: str | None) -> str:
    """Display-only name: no directories, no control characters, bounded length."""
    base = PurePath((name or "").replace("\\", "/")).name
    base = re.sub(r"[\x00-\x1f\x7f]", "", base).strip()
    suffix = PurePath(base).suffix
    if suffix.lower() not in ALLOWED_EXTENSIONS:
        raise IngestionError("Upload a PDF, TXT or MD file", 400)
    # Truncate the stem, not the end, so the extension survives.
    return base[: -len(suffix)][: 130 - len(suffix)] + suffix


def extract_pages(filename: str, data: bytes, settings: Settings) -> list[str]:
    """Return the raw text of each page (a TXT/MD file is a single page)."""
    if not data.strip():
        raise IngestionError("The file is empty", 422)
    if PurePath(filename).suffix.lower() == ".pdf":
        return _extract_pdf(data, settings)
    try:
        return [data.decode("utf-8-sig")]
    except UnicodeDecodeError:
        raise IngestionError("Text files must be UTF-8 encoded", 400) from None


def _extract_pdf(data: bytes, settings: Settings) -> list[str]:
    if not data.startswith(b"%PDF"):  # extension alone is not proof
        raise IngestionError("File has a .pdf extension but is not a PDF", 400)
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise IngestionError("Encrypted PDFs are not supported", 400)
            if pdf.page_count > settings.max_pdf_pages:
                raise IngestionError(f"PDF exceeds {settings.max_pdf_pages} pages", 413)
            return [page.get_text(sort=True) for page in pdf]
    except IngestionError:
        raise
    except Exception:
        raise IngestionError("Could not read this PDF", 400) from None


def build_chunks(pages: list[str], settings: Settings) -> list[PageChunk]:
    chunks: list[PageChunk] = []
    for page_number, raw in enumerate(pages, start=1):
        for piece in chunk_text(
            clean_text(raw), chunk_size=settings.chunk_size, overlap=settings.chunk_overlap
        ):
            chunks.append(PageChunk(page_number, piece.index, piece.start, piece.end, piece.text))
    if not chunks:
        raise IngestionError(
            "No readable text found. Scanned-image PDFs need OCR, which is not supported yet.",
            422,
        )
    return chunks
