"""SourceMind API. M1 health, M2 upload/chunking, M3 retrieval/delete, M4 optional answers."""
import logging
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, StringConstraints
from starlette.concurrency import run_in_threadpool

from .answering import (
    SYSTEM_PROMPT, build_user_prompt, check_citations, is_abstention, select_for_context,
)
from .config import get_settings
from .ingestion import IngestionError, build_chunks, extract_pages, sanitize_filename
from .llm import generation_available, get_llm_client
from .retrieval import Hit, retrieve
from .store import Document, store

API_VERSION = "0.4.0"
logger = logging.getLogger("sourcemind")

app = FastAPI(title="SourceMind API", version=API_VERSION, docs_url="/api/docs")

# Only the configured frontend origin may call the API from a browser. No wildcard,
# and no cookies/credentials: there is no auth yet (M6).
app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_origin],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type"],
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


@app.post("/api/v1/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)) -> dict:
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

    doc = Document(
        id=uuid4().hex, name=filename, size_bytes=len(raw),
        page_count=page_count, status="ready", chunks=chunks,
    )
    if not store.add(doc, limit=settings.max_documents):
        raise HTTPException(409, f"Document limit reached ({settings.max_documents})")
    return doc.summary()


@app.get("/api/v1/documents")
def list_documents() -> dict:
    return {"documents": [doc.summary() for doc in store.list()]}


@app.get("/api/v1/documents/{document_id}")
def get_document(document_id: str) -> dict:
    doc = store.get(document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    return doc.summary()


@app.delete("/api/v1/documents/{document_id}", status_code=204)
def delete_document(document_id: str) -> Response:
    if not store.delete(document_id):
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
        "request_id": uuid4().hex,
        "notice": notice,
    }


@app.post("/api/v1/queries")
async def query(body: QueryRequest) -> dict:
    settings = get_settings()
    docs = store.select(body.document_ids)
    if docs is None:
        raise HTTPException(404, "One or more documents were not found")
    chunks = [chunk for doc in docs for chunk in doc.search_chunks()]
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
