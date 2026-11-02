"""SourceMind API. M1: health check. M2: document upload and chunking."""
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from .config import get_settings
from .ingestion import IngestionError, build_chunks, extract_pages, sanitize_filename
from .store import Document, store

API_VERSION = "0.2.0"

app = FastAPI(title="SourceMind API", version=API_VERSION, docs_url="/api/docs")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    """Readiness probe. Must never expose secrets or sensitive config."""
    return {
        "status": "ok",
        "version": API_VERSION,
        "environment": get_settings().app_env,
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
