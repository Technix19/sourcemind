"""The evaluation corpus: the same extraction and chunking the product uses.

Reusing app.ingestion / app.chunking (not a copy) is what makes the evaluation measure the product.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.chunking import chunk_text, clean_text

DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "evaluation"
CORPUS_DIR = DATA_DIR / "corpus"
MANIFEST = DATA_DIR / "corpus.manifest.json"
QUESTION_FILES = (DATA_DIR / "questions.json", DATA_DIR / "blind_questions.json", DATA_DIR / "external_questions.json")


@dataclass(frozen=True)
class EvalChunk:
    doc_id: str
    page: int        # 1-based PDF page index, the same numbering the product uses
    index: int
    text: str


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text())


def corpus_available() -> bool:
    return MANIFEST.exists() and all((CORPUS_DIR / d["file"]).exists() for d in load_manifest()["documents"])


def extract_pages(pdf_path: Path) -> list[str]:
    """Raw page text, extracted exactly as the product's ingestion does (PyMuPDF, sort=True)."""
    import pymupdf

    with pymupdf.open(pdf_path) as pdf:
        return [page.get_text(sort=True) for page in pdf]


def load_pages(doc_ids: list[str] | None = None) -> dict[str, list[str]]:
    """doc id -> raw text of each page (index 0 = page 1)."""
    pages: dict[str, list[str]] = {}
    for doc in load_manifest()["documents"]:
        if doc_ids is None or doc["id"] in doc_ids:
            pages[doc["id"]] = extract_pages(CORPUS_DIR / doc["file"])
    return pages


def normalize(text: str) -> str:
    """Whitespace-collapsed, lower-cased text used to match answer phrases against pages."""
    return re.sub(r"\s+", " ", text).strip().lower()


def build_chunks(pages: dict[str, list[str]], chunk_size: int = 950, overlap: int = 170) -> list[EvalChunk]:
    chunks: list[EvalChunk] = []
    for doc_id, doc_pages in pages.items():
        for page_number, raw in enumerate(doc_pages, start=1):
            for piece in chunk_text(clean_text(raw), chunk_size=chunk_size, overlap=overlap):
                chunks.append(EvalChunk(doc_id, page_number, piece.index, piece.text))
    return chunks
