"""Deterministic, offset-preserving text chunker.

Pure functions only: no files, no HTTP. Offsets index into the *cleaned* page
text (see `clean_text`), so a chunk can always be located again later.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_WHITESPACE = re.compile(r"\s")


@dataclass(frozen=True)
class TextChunk:
    index: int
    start: int
    end: int
    text: str


def clean_text(text: str) -> str:
    """Normalize spacing but keep paragraph breaks (blank lines)."""
    text = text.replace("\x00", "")  # Postgres text cannot hold NUL; some PDFs emit it
    text = re.sub(r"[ \t\f\v\r]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, *, chunk_size: int = 950, overlap: int = 170) -> list[TextChunk]:
    """Split `text` (already cleaned) into overlapping chunks.

    Each window prefers to end at a paragraph break, then at whitespace, and
    only cuts mid-word when the window has no whitespace at all. The next
    window starts `overlap` characters back, snapped forward to a word start.
    """
    if chunk_size <= 0 or not 0 <= overlap < chunk_size // 2:
        raise ValueError("need chunk_size > 0 and 0 <= overlap < chunk_size / 2")
    n = len(text)
    chunks: list[TextChunk] = []
    start = 0
    while start < n:
        end = min(start + chunk_size, n)
        if end < n:
            floor = start + chunk_size // 2
            cut = text.rfind("\n\n", floor, end)
            if cut == -1:
                cut = max(text.rfind(" ", floor, end), text.rfind("\n", floor, end))
            if cut > start:
                end = cut
        piece = text[start:end]
        lead = len(piece) - len(piece.lstrip())
        s, e = start + lead, end - (len(piece) - len(piece.rstrip()))
        if e > s:
            chunks.append(TextChunk(len(chunks), s, e, text[s:e]))
        if end >= n:
            break
        nxt = end - overlap  # > start because overlap < chunk_size / 2
        if nxt > 0 and not text[nxt - 1].isspace():
            gap = _WHITESPACE.search(text, nxt, end)
            if gap:
                nxt = gap.end()
        start = nxt
    return chunks
