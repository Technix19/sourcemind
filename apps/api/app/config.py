"""Environment-based configuration, read per call so tests can override it.

Only non-secret settings live here for now. Secrets (API keys, etc.) are added
in later milestones and must only ever come from the environment, never code.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse

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
    supabase_url: str
    supabase_anon_key: str = field(repr=False)  # public key, but still kept out of logs


def _base_url(raw: str) -> str:
    """Scheme + host only, so a pasted '.../rest/v1/' still works."""
    parsed = urlparse(raw.strip())
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""


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
        supabase_url=_base_url(os.getenv("SUPABASE_URL", "")),
        supabase_anon_key=(os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY", "")).strip(),
    )
