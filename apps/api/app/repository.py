"""Per-user document storage in Supabase Postgres, accessed AS the signed-in user.

Every call carries that request's own token, so Row Level Security (not our Python
code) decides what a user may touch. The service-role key is never used. The
HTTP connection pool is shared, but identity is passed per call and is never
stored on a shared object, so one request cannot run with another user's rights.
"""
from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from typing import Protocol

import httpx
from fastapi import Depends

from .auth import AuthUser, current_user
from .config import get_settings
from .ingestion import PageChunk
from .retrieval import SearchChunk

logger = logging.getLogger("sourcemind.repository")

PAGE_SIZE = 1000     # rows per read request (the server may cap lower; we follow Content-Range)
INSERT_BATCH = 200   # chunk rows per insert request
DOC_COLUMNS = "id,name,size_bytes,page_count,status,chunks(count)"


@dataclass(frozen=True)
class Document:
    id: str
    name: str
    size_bytes: int
    page_count: int
    status: str
    chunk_count: int

    def summary(self) -> dict:
        return {
            "id": self.id, "name": self.name, "size_bytes": self.size_bytes,
            "page_count": self.page_count, "chunk_count": self.chunk_count, "status": self.status,
        }


class RepositoryError(Exception):
    """The storage layer failed. `status` is the upstream HTTP status, if there was one."""

    def __init__(self, status: int | None = None) -> None:
        super().__init__(f"storage error (status={status})")
        self.status = status

    @property
    def unauthorized(self) -> bool:
        return self.status in (401, 403)


def valid_id(value: str) -> str | None:
    """Canonical uuid string, or None. Also keeps user input out of query filters."""
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        return None


class Repository(Protocol):
    def count_documents(self) -> int: ...
    def create_document(self, name: str, size_bytes: int, page_count: int) -> Document: ...
    def add_chunks(self, document_id: str, chunks: list[PageChunk]) -> None: ...
    def mark_ready(self, document_id: str) -> None: ...
    def list_documents(self) -> list[Document]: ...
    def get_document(self, document_id: str) -> Document | None: ...
    def delete_document(self, document_id: str) -> bool: ...
    def search_chunks(self, document_ids: list[str] | None) -> list[SearchChunk] | None: ...


_http: httpx.Client | None = None
_http_lock = threading.Lock()


def shared_http() -> httpx.Client:
    """Connection pool only. It carries NO credentials; headers are set per request."""
    global _http
    with _http_lock:
        if _http is None:
            _http = httpx.Client(timeout=20)
        return _http


def _document(row: dict) -> Document:
    counted = row.get("chunks") or [{"count": 0}]
    return Document(
        id=row["id"], name=row["name"], size_bytes=row["size_bytes"],
        page_count=row["page_count"], status=row["status"], chunk_count=counted[0]["count"],
    )


class SupabaseRepository:
    def __init__(self, user: AuthUser, *, base_url: str, api_key: str, http: httpx.Client | None = None) -> None:
        self._token = user.token
        self._base = f"{base_url}/rest/v1"
        self._key = api_key
        self._http = http or shared_http()

    # -- plumbing -----------------------------------------------------------
    def _request(self, method: str, table: str, *, params=None, json=None, prefer: str | None = None) -> httpx.Response:
        headers = {"apikey": self._key, "Authorization": f"Bearer {self._token}"}
        if prefer:
            headers["Prefer"] = prefer
        try:
            response = self._http.request(method, f"{self._base}/{table}", params=params, json=json, headers=headers)
        except httpx.HTTPError:
            raise RepositoryError(None) from None
        if response.status_code >= 400:
            raise RepositoryError(response.status_code)
        return response

    def _read_all(self, table: str, params: dict) -> list[dict]:
        """Read every row, page by page. A single request silently stops at the server's row cap."""
        rows: list[dict] = []
        while True:
            response = self._request(
                "GET", table, params={**params, "limit": PAGE_SIZE, "offset": len(rows)}, prefer="count=exact"
            )
            page = response.json()
            rows.extend(page)
            total = _total_rows(response)
            if not page or (total is not None and len(rows) >= total) or (total is None and len(page) < PAGE_SIZE):
                return rows

    # -- documents ----------------------------------------------------------
    def count_documents(self) -> int:
        return len(self._read_all("documents", {"select": "id", "status": "neq.deleting"}))

    def create_document(self, name: str, size_bytes: int, page_count: int) -> Document:
        response = self._request(
            "POST", "documents",
            json={"name": name, "size_bytes": size_bytes, "page_count": page_count, "status": "indexing"},
            prefer="return=representation",
        )
        row = response.json()[0]
        return Document(row["id"], row["name"], row["size_bytes"], row["page_count"], row["status"], 0)

    def add_chunks(self, document_id: str, chunks: list[PageChunk]) -> None:
        rows = [
            {
                "document_id": document_id, "page_number": c.page_number, "chunk_index": c.chunk_index,
                "start_offset": c.start, "end_offset": c.end, "text": c.text,
            }
            for c in chunks
        ]
        for i in range(0, len(rows), INSERT_BATCH):
            self._request("POST", "chunks", json=rows[i : i + INSERT_BATCH], prefer="return=minimal")

    def mark_ready(self, document_id: str) -> None:
        self._request("PATCH", "documents", params={"id": f"eq.{document_id}"}, json={"status": "ready"}, prefer="return=minimal")

    def list_documents(self) -> list[Document]:
        rows = self._read_all("documents", {"select": DOC_COLUMNS, "status": "neq.deleting", "order": "created_at.asc"})
        return [_document(r) for r in rows]

    def get_document(self, document_id: str) -> Document | None:
        doc_id = valid_id(document_id)
        if doc_id is None:
            return None
        rows = self._request("GET", "documents", params={"select": DOC_COLUMNS, "id": f"eq.{doc_id}", "status": "neq.deleting"}).json()
        return _document(rows[0]) if rows else None

    def delete_document(self, document_id: str) -> bool:
        doc_id = valid_id(document_id)
        if doc_id is None:
            return False
        rows = self._request("DELETE", "documents", params={"id": f"eq.{doc_id}"}, prefer="return=representation").json()
        return bool(rows)

    # -- retrieval input ----------------------------------------------------
    def search_chunks(self, document_ids: list[str] | None) -> list[SearchChunk] | None:
        """Chunks of the caller's READY documents; None if any requested id is not theirs."""
        wanted: list[str] | None = None
        if document_ids is not None:
            canonical = [valid_id(i) for i in dict.fromkeys(document_ids)]
            if any(c is None for c in canonical):
                return None
            wanted = [c for c in canonical if c is not None]
        params = {"select": "id,name", "status": "eq.ready", "order": "created_at.asc"}
        if wanted is not None:
            params["id"] = f"in.({','.join(wanted)})"
        docs = self._read_all("documents", params)
        if wanted is not None and len(docs) != len(wanted):
            return None
        if not docs:
            return []
        names = {d["id"]: d["name"] for d in docs}
        rank = {d["id"]: n for n, d in enumerate(docs)}
        rows = self._read_all("chunks", {
            "select": "document_id,page_number,chunk_index,text",
            "document_id": f"in.({','.join(names)})",
            "order": "document_id.asc,page_number.asc,chunk_index.asc",
        })
        rows.sort(key=lambda r: (rank[r["document_id"]], r["page_number"], r["chunk_index"]))
        return [
            SearchChunk(
                chunk_id=f"{r['document_id']}-p{r['page_number']}-c{r['chunk_index']}",
                document_id=r["document_id"], filename=names[r["document_id"]],
                page_number=r["page_number"], text=r["text"],
            )
            for r in rows
        ]


def _total_rows(response: httpx.Response) -> int | None:
    """Total from 'Content-Range: 0-999/1650' (None when unknown, e.g. '*')."""
    tail = response.headers.get("content-range", "").rpartition("/")[2]
    return int(tail) if tail.isdigit() else None


def get_repository(user: AuthUser = Depends(current_user)) -> Repository:
    """A NEW repository for every request, bound to that request's user."""
    settings = get_settings()
    return SupabaseRepository(user, base_url=settings.supabase_url, api_key=settings.supabase_anon_key)
