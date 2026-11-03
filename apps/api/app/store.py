"""Temporary in-memory document store (replaced by Postgres in M6).

Process-global and unscoped by user: fine for a local single-user MVP, and
must not be deployed publicly. Guarded by a lock because FastAPI may run
requests on several threads.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from .ingestion import PageChunk
from .retrieval import SearchChunk


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

    def search_chunks(self) -> list[SearchChunk]:
        # The chunk id is derived from where the text lives, so it is stable
        # and cannot point at a page that doesn't exist.
        return [
            SearchChunk(
                chunk_id=f"{self.id}-p{c.page_number}-c{c.chunk_index}",
                document_id=self.id,
                filename=self.name,
                page_number=c.page_number,
                text=c.text,
            )
            for c in self.chunks
        ]


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

    def delete(self, doc_id: str) -> bool:
        """Remove a document and its chunks. There is no separate index to go stale."""
        with self._lock:
            return self._docs.pop(doc_id, None) is not None

    def select(self, doc_ids: list[str] | None) -> list[Document] | None:
        """Documents to search (all if `doc_ids` is None); None if any id is unknown."""
        with self._lock:
            if doc_ids is None:
                return list(self._docs.values())
            docs = [self._docs.get(i) for i in dict.fromkeys(doc_ids)]
            return None if any(d is None for d in docs) else docs  # type: ignore[return-value]

    def clear(self) -> None:
        with self._lock:
            self._docs.clear()


store = DocumentStore()
