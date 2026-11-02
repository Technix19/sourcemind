"""Temporary in-memory document store (replaced by Postgres in M6).

Process-global and unscoped by user: fine for a local single-user MVP, and
must not be deployed publicly. Guarded by a lock because FastAPI may run
requests on several threads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from .ingestion import PageChunk


@dataclass(frozen=True)
class Document:
    id: str
    name: str
    size_bytes: int
    page_count: int
    status: str
    chunks: list[PageChunk] = field(default_factory=list, repr=False)

    def summary(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "size_bytes": self.size_bytes,
            "page_count": self.page_count,
            "chunk_count": len(self.chunks),
            "status": self.status,
        }


class DocumentStore:
    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._lock = RLock()

    def add(self, doc: Document, *, limit: int) -> bool:
        """Insert unless the store is full. Check and insert are one atomic step."""
        with self._lock:
            if len(self._docs) >= limit:
                return False
            self._docs[doc.id] = doc
            return True

    def get(self, doc_id: str) -> Document | None:
        with self._lock:
            return self._docs.get(doc_id)

    def list(self) -> list[Document]:
        with self._lock:
            return list(self._docs.values())

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()


store = DocumentStore()
