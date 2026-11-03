"""SourceMind API. M1 health, M2 upload/chunking, M3 retrieval/delete, M4 answers, M6b sign-in + per-user storage, M6c private files."""
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StringConstraints
from starlette.concurrency import run_in_threadpool

from .answering import (
    SYSTEM_PROMPT, build_user_prompt, check_citations, is_abstention, select_for_context,
)
from .auth import AuthGate
from .config import get_settings
from .ingestion import IngestionError, build_chunks, content_type_for, extract_pages, sanitize_filename
from .llm import generation_available, get_llm_client
from .repository import SIGNED_URL_SECONDS, Repository, RepositoryError, get_repository
from .retrieval import Hit, retrieve

API_VERSION = "0.6.0"
logger = logging.getLogger("sourcemind")

def check_configuration() -> None:
    """Fail closed: without Supabase settings nobody can be authenticated, so do not start."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set (see apps/api/.env.example). "
            "The API has no anonymous mode."
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    check_configuration()
    yield


app = FastAPI(title="SourceMind API", version=API_VERSION, docs_url="/api/docs", lifespan=lifespan)

# Middleware order matters: the LAST one added is the OUTERMOST. Auth is added first (inner),
# CORS last (outer), so even a 401 carries CORS headers and the browser can read it.
app.add_middleware(AuthGate)
# Only the configured frontend origin may call the API from a browser. No wildcard,
# and no cookies: the token travels in the Authorization header.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/v1/health")
def health() -> dict:
    """Readiness probe. Must never expose secrets or sensitive config."""
    return {
        "status": "ok",
        "version": API_VERSION,
        "environment": get_settings().app_env,
        "generation_available": generation_available(),  # a boolean, never the key
    }


def _process(filename: str, raw: bytes) -> tuple[int, list]:
    settings = get_settings()
    pages = extract_pages(filename, raw, settings)
    return len(pages), build_chunks(pages, settings)


async def storage_call(fn, *args, failure="Storage is unavailable right now. Try again shortly."):
    """Run a blocking storage call off the event loop and translate its failures safely."""
    try:
        return await run_in_threadpool(fn, *args)
    except RepositoryError as err:
        if err.unauthorized:
            raise HTTPException(401, "Your session has expired. Sign in again.") from None
        logger.warning("storage error status=%s", err.status)  # status only: never data, tokens or links
        raise HTTPException(502, failure) from None


@app.post("/api/v1/documents", status_code=201)
async def upload_document(file: UploadFile = File(...), repo: Repository = Depends(get_repository)) -> dict:
    settings = get_settings()
    try:
        filename = sanitize_filename(file.filename)
        # Read one byte past the limit so oversize files are rejected without
        # loading an arbitrarily large body into memory.
        raw = await file.read(settings.max_upload_bytes + 1)
        if len(raw) > settings.max_upload_bytes:
            raise IngestionError(
                f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB limit", 413
            )
        page_count, chunks = await run_in_threadpool(_process, filename, raw)
    except IngestionError as err:
        raise HTTPException(err.status_code, err.message) from None
    finally:
        await file.close()

    if await storage_call(repo.count_documents) >= settings.max_documents:
        raise HTTPException(409, f"Document limit reached ({settings.max_documents})")
    doc = await storage_call(repo.create_document, filename, len(raw), page_count)
    try:
        await storage_call(repo.put_file, doc.id, raw, content_type_for(filename))
        await storage_call(repo.add_chunks, doc.id, chunks)
        await storage_call(repo.mark_ready, doc.id)
    except HTTPException:
        # Never leave a half-indexed document or an orphaned file behind: the ordered delete
        # removes chunks, the stored file and the row.
        try:
            await run_in_threadpool(repo.delete_document, doc.id)
        except Exception:
            logger.warning("cleanup after failed upload also failed")
        raise
    return {**doc.summary(), "chunk_count": len(chunks), "status": "ready", "has_file": True}


@app.get("/api/v1/documents")
async def list_documents(repo: Repository = Depends(get_repository)) -> dict:
    # Finish any deletion that an earlier crash interrupted (runs as the user; no background worker).
    try:
        await run_in_threadpool(repo.finish_pending_deletions)
    except Exception as exc:
        logger.warning("could not finish pending deletions: %s", type(exc).__name__)
    return {"documents": [doc.summary() for doc in await storage_call(repo.list_documents)]}


@app.get("/api/v1/documents/{document_id}")
async def get_document(document_id: str, repo: Repository = Depends(get_repository)) -> dict:
    doc = await storage_call(repo.get_document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc.summary()


@app.get("/api/v1/documents/{document_id}/view")
async def view_document(
    document_id: str,
    response: Response,
    page: int | None = Query(default=None, ge=1),
    repo: Repository = Depends(get_repository),
) -> dict:
    """A short-lived link to the original file. The link is a bearer credential, so it is
    issued only for the caller's own document, expires quickly, is never logged and never cached."""
    doc = await storage_call(repo.get_document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    if page is not None and page > doc.page_count:
        raise HTTPException(422, f"This document has {doc.page_count} page(s).")
    unavailable = "The original file isn't stored for this document. Upload it again to enable this."
    if not doc.has_file:
        raise HTTPException(404, unavailable)
    url = await storage_call(repo.signed_url, document_id)
    if url is None:
        raise HTTPException(404, unavailable)
    response.headers["Cache-Control"] = "no-store"
    return {"url": url, "expires_in": SIGNED_URL_SECONDS, "page": page, "filename": doc.name}


@app.delete("/api/v1/documents/{document_id}", status_code=204)
async def delete_document(document_id: str, repo: Repository = Depends(get_repository)) -> Response:
    removed = await storage_call(
        repo.delete_document, document_id,
        failure="Removal did not finish. The document is hidden and will be cleaned up automatically.",
    )
    if not removed:
        raise HTTPException(404, "Document not found")
    return Response(status_code=204)


class QueryRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=550)]
    document_ids: list[str] | None = Field(default=None, max_length=50)
    top_k: int = Field(default=4, ge=1, le=10)
    mode: Literal["sources_only", "generated"] = "sources_only"  # generation is opt-in


def _evidence(hits: list[Hit]) -> list[dict]:
    # citation_id is the 1-based position: the same number the model was shown.
    return [
        {
            "citation_id": str(rank),
            "chunk_id": hit.chunk.chunk_id,
            "document_id": hit.chunk.document_id,
            "filename": hit.chunk.filename,
            "page_number": hit.chunk.page_number,
            "excerpt": hit.chunk.text,
            "score": hit.score,
        }
        for rank, hit in enumerate(hits, start=1)
    ]


def _reply(
    mode: str, hits: list[Hit], *, answer: str | None = None, insufficient: bool | None = None,
    model: str | None = None, notice: str | None = None,
) -> dict:
    return {
        "answer_mode": mode,
        "answer": answer,
        "insufficient_evidence": (not hits) if insufficient is None else insufficient,
        "evidence": _evidence(hits),
        "model_used": model,
        "request_id": uuid.uuid4().hex,
        "notice": notice,
    }


@app.post("/api/v1/queries")
async def query(body: QueryRequest, repo: Repository = Depends(get_repository)) -> dict:
    settings = get_settings()
    chunks = await storage_call(repo.search_chunks, body.document_ids)
    if chunks is None:
        raise HTTPException(404, "One or more documents were not found")
    if not chunks:
        raise HTTPException(409, "Upload at least one document before asking a question")
    hits = await run_in_threadpool(
        lambda: retrieve(
            body.question, chunks, top_k=body.top_k, min_score=settings.min_relevance_score
        )
    )
    if body.mode == "sources_only" or not hits:
        return _reply("sources_only", hits)  # nothing to ground an answer on: no model call

    client = get_llm_client()
    if client is None:
        return _reply("sources_only", hits, notice="Answer generation is not configured; showing retrieved evidence.")

    # Only what fits the budget is sent AND returned, so every [n] resolves to evidence.
    sent = select_for_context(hits, settings.max_context_chars)
    try:
        raw = await run_in_threadpool(client.complete, SYSTEM_PROMPT, build_user_prompt(body.question, sent))
    except Exception as exc:
        # Log only the error type: messages can contain request details.
        logger.warning("LLM request failed: %s", type(exc).__name__)
        return _reply("sources_only", sent, notice="Answer generation is unavailable right now; showing retrieved evidence.")

    if is_abstention(raw):
        return _reply("generated", sent, answer=raw.strip(), insufficient=True, model=client.model)
    checked = check_citations(raw, len(sent))
    if not checked.cited:
        # An answer with no resolvable citation can't be verified, so don't show it.
        return _reply("sources_only", sent, notice="The generated answer cited no evidence, so it was withheld. Showing retrieved evidence instead.")
    return _reply("generated", sent, answer=checked.text, insufficient=False, model=client.model)
