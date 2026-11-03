"""Per-user document storage in Supabase Postgres, accessed AS the signed-in user.

Every call carries that request's own token, so Row Level Security (not our Python
code) decides what a user may touch. Original files live in a PRIVATE storage bucket,
reached the same way, under names made only of ids ("<user id>/<document id>"). The service-role key is never used. The
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
DOC_COLUMNS = "id,name,size_bytes,page_count,status,storage_key,chunks(count)"
BUCKET = "documents"
SIGNED_URL_SECONDS = 60  # a signed link is a bearer credential: keep its life short


@dataclass(frozen=True)
class Document:
    id: str
    name: str
    size_bytes: int
    page_count: int
    status: str
    chunk_count: int
    has_file: bool = False  # whether the original file is stored (older documents have none)

    def summary(self) -> dict:
        # The storage key is internal and never exposed; clients only learn whether a file exists.
        return {
            "id": self.id, "name": self.name, "size_bytes": self.size_bytes,
            "page_count": self.page_count, "chunk_count": self.chunk_count, "status": self.status,
            "has_file": self.has_file,
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
    def put_file(self, document_id: str, data: bytes, content_type: str) -> None: ...
    def signed_url(self, document_id: str, expires_in: int = SIGNED_URL_SECONDS) -> str | None: ...
    def finish_pending_deletions(self) -> int: ...
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
        has_file=bool(row.get("storage_key")),
    )


class SupabaseRepository:
    def __init__(self, user: AuthUser, *, base_url: str, api_key: str, http: httpx.Client | None = None) -> None:
        self._token = user.token
        self._user_id = user.id
        self._root = base_url
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

    def _storage(self, method: str, path: str, *, content: bytes | None = None, json=None,
                 headers: dict | None = None, missing_ok: bool = False) -> httpx.Response | None:
        """Call Supabase Storage as the user. Returns None when the object is missing and `missing_ok`."""
        all_headers = {"apikey": self._key, "Authorization": f"Bearer {self._token}", **(headers or {})}
        try:
            response = self._http.request(
                method, f"{self._root}/storage/v1/{path}", content=content, json=json, headers=all_headers
            )
        except httpx.HTTPError:
            raise RepositoryError(None) from None
        if response.status_code >= 400:
            if missing_ok and _storage_missing(response):
                return None
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
        # The id and storage key are chosen here, before the row exists, because the storage
        # policy only lets a file be uploaded for a document row that already points at it.
        doc_id = str(uuid.uuid4())
        response = self._request(
            "POST", "documents",
            json={
                "id": doc_id, "name": name, "size_bytes": size_bytes, "page_count": page_count,
                "status": "indexing", "storage_key": f"{self._user_id}/{doc_id}",
            },
            prefer="return=representation",
        )
        row = response.json()[0]
        return Document(row["id"], row["name"], row["size_bytes"], row["page_count"], row["status"], 0, True)

    def put_file(self, document_id: str, data: bytes, content_type: str) -> None:
        """Store the original file. Never overwrites ('x-upsert: false'): stored files are immutable."""
        doc_id = valid_id(document_id)
        if doc_id is None:
            raise RepositoryError(None)
        self._storage(
            "POST", f"object/{BUCKET}/{self._user_id}/{doc_id}", content=data,
            headers={"Content-Type": content_type, "x-upsert": "false"},
        )

    def signed_url(self, document_id: str, expires_in: int = SIGNED_URL_SECONDS) -> str | None:
        """A short-lived link to the original file, or None if there is no such file for this user.

        The link is a bearer credential: whoever holds it can read the file until it expires.
        Supabase only issues it if this user's own token passes the storage policy.
        """
        doc_id = valid_id(document_id)
        if doc_id is None:
            return None
        response = self._storage(
            "POST", f"object/sign/{BUCKET}/{self._user_id}/{doc_id}", json={"expiresIn": expires_in}, missing_ok=True
        )
        if response is None:
            return None
        signed = response.json().get("signedURL", "")
        path = signed if signed.startswith("/storage/v1") else f"/storage/v1{signed}"
        url = f"{self._root}{path}"
        return url if url.startswith(f"{self._root}/storage/v1/object/sign/{BUCKET}/") else None

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
        """Remove a document in an order that is safe to retry after a crash (see docs/m6-plan.md).

        1. mark it 'deleting' (hidden from lists and from search)
        2. delete its chunks, so its text is no longer retrievable
        3. delete the stored file (a missing file counts as done)
        4. delete the row
        Every step is idempotent, so calling this again resumes wherever it stopped.
        """
        doc_id = valid_id(document_id)
        if doc_id is None:
            return False
        rows = self._request("GET", "documents", params={"select": "id,status,storage_key", "id": f"eq.{doc_id}"}).json()
        if not rows:
            return False
        if rows[0]["status"] != "deleting":
            self._request("PATCH", "documents", params={"id": f"eq.{doc_id}"}, json={"status": "deleting"}, prefer="return=minimal")
        self._request("DELETE", "chunks", params={"document_id": f"eq.{doc_id}"}, prefer="return=minimal")
        if rows[0].get("storage_key"):
            self._storage("DELETE", f"object/{BUCKET}/{rows[0]['storage_key']}", missing_ok=True)
        self._request("DELETE", "documents", params={"id": f"eq.{doc_id}"}, prefer="return=minimal")
        return True

    def finish_pending_deletions(self) -> int:
        """Resume deletions that were interrupted earlier. Returns how many were completed."""
        stuck = self._read_all("documents", {"select": "id", "status": "eq.deleting"})
        done = 0
        for row in stuck:
            if self.delete_document(row["id"]):
                done += 1
        return done

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


def _storage_missing(response: httpx.Response) -> bool:
    """Supabase Storage reports a missing object as HTTP 404, or HTTP 400 with statusCode '404' in the body."""
    if response.status_code == 404:
        return True
    try:
        return str(response.json().get("statusCode")) == "404"
    except ValueError:
        return False


def _total_rows(response: httpx.Response) -> int | None:
    """Total from 'Content-Range: 0-999/1650' (None when unknown, e.g. '*')."""
    tail = response.headers.get("content-range", "").rpartition("/")[2]
    return int(tail) if tail.isdigit() else None


def get_repository(user: AuthUser = Depends(current_user)) -> Repository:
    """A NEW repository for every request, bound to that request's user."""
    settings = get_settings()
    return SupabaseRepository(user, base_url=settings.supabase_url, api_key=settings.supabase_anon_key)
