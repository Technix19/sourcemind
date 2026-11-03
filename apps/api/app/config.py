"""Environment-based configuration, read per call so tests can override it.

Only non-secret settings live here for now. Secrets (API keys, etc.) are added
in later milestones and must only ever come from the environment, never code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str
    frontend_origin: str
    max_upload_bytes: int
    max_pdf_pages: int
    max_documents: int
    chunk_size: int
    chunk_overlap: int
    min_relevance_score: float
    chat_model: str
    max_context_chars: int
    max_answer_tokens: int


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        max_upload_bytes=int(os.getenv("MAX_UPLOAD_BYTES", str(12 * 1024 * 1024))),
        max_pdf_pages=int(os.getenv("MAX_PDF_PAGES", "150")),
        max_documents=int(os.getenv("MAX_DOCUMENTS", "12")),
        chunk_size=int(os.getenv("CHUNK_SIZE", "950")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "170")),
        # Initial heuristic, NOT tuned on labeled data yet (that is M7).
        min_relevance_score=float(os.getenv("MIN_RELEVANCE_SCORE", "0.05")),
        # No default model on purpose: the user picks one their account supports.
        chat_model=os.getenv("OPENAI_CHAT_MODEL", "").strip(),
        max_context_chars=int(os.getenv("MAX_CONTEXT_CHARS", "8000")),
        max_answer_tokens=int(os.getenv("MAX_ANSWER_TOKENS", "500")),
    )
