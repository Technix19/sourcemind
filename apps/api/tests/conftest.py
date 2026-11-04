"""Shared test fakes.

Offline tests never talk to Supabase. A fake verifier maps the tokens "user-a" and
"user-b" to two users, and an in-memory repository (scoped per user, like Row Level
Security) replaces the database. Integration tests (marker `integration`) opt out
and use the real thing.
"""
import dataclasses
import hashlib
import math
import re
import uuid

import pymupdf
import pytest
from fastapi import Depends

from app import auth, main
from app.auth import AuthUser, current_user
from app.embeddings import DIMENSION, EmbeddingError
from app.ingestion import PageChunk
from app.repository import Document, get_repository, valid_id
from app.retrieval import SearchChunk

USER_A = AuthUser(id=str(uuid.UUID(int=1)), token="user-a")
USER_B = AuthUser(id=str(uuid.UUID(int=2)), token="user-b")
AUTH_A = {"Authorization": "Bearer user-a"}
AUTH_B = {"Authorization": "Bearer user-b"}


class FakeVerifier:
    users = {"user-a": USER_A, "user-b": USER_B}

    def verify(self, token: str) -> AuthUser:
        if token not in self.users:
            raise auth.AuthError("unknown token")
        return self.users[token]


FAKE_MODEL = "fake-model-384"
# A pretend "model" that knows a few paraphrases, so tests can show meaning-style matches
# (e.g. "inputs" ~ "correctness") without downloading anything. It tests plumbing, not quality.
SYNONYMS = {"inputs": "signal", "input": "signal", "features": "signal", "correctness": "signal",
            "signals": "signal", "attempts": "signal", "automobile": "car", "vehicle": "car"}
STOPWORDS = {"the", "a", "an", "of", "and", "is", "are", "to", "in", "for", "which", "what", "does", "do", "how"}


class FakeEmbedder:
    """Deterministic bag-of-hashed-words vectors (normalised), 384 dimensions like the real model."""

    model_id = FAKE_MODEL

    def __init__(self) -> None:
        self.passage_calls: list[list[str]] = []
        self.query_calls: list[str] = []
        self.fail = False

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * DIMENSION
        for token in re.findall(r"[a-z]+", text.lower()):
            token = SYNONYMS.get(token, token)
            if token not in STOPWORDS:
                vec[int(hashlib.md5(token.encode()).hexdigest(), 16) % DIMENSION] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        vec = [x / norm for x in vec]
        return vec if any(vec) else [1.0] + [0.0] * (DIMENSION - 1)

    def embed_passages(self, texts):
        if self.fail:
            raise EmbeddingError("fake embedder failure")
        self.passage_calls.append(list(texts))
        return [self._vector(t) for t in texts]

    def embed_query(self, text):
        if self.fail:
            raise EmbeddingError("fake embedder failure")
        self.query_calls.append(text)
        return self._vector(text)


class InMemoryBackend:
    """All users' data, keyed by user id, so isolation can be tested without a database."""

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Document]] = {}
        self._chunks: dict[str, dict[str, list[PageChunk]]] = {}
        self.files: dict[tuple[str, str], tuple[bytes, str]] = {}   # (user id, document id) -> (bytes, type)
        self.chunk_ids: dict[tuple[str, str], list[str]] = {}       # (user id, document id) -> chunk ids
        self.vectors: dict[tuple[str, str], tuple[str, list[float], str]] = {}   # (user, chunk id) -> (doc, vector, model)
        self.indexed_with: dict[tuple[str, str], str] = {}          # (user, document id) -> embedding model
        self.embedder = FakeEmbedder()
        self.current_model: str | None = FAKE_MODEL                 # None = meaning search switched off

    def repo_for(self, user: AuthUser) -> "InMemoryRepository":
        return InMemoryRepository(self, user.id)

    def chunks_of(self, user_id: str, document_id: str) -> list[PageChunk]:
        return self._chunks.get(user_id, {}).get(document_id, [])


class InMemoryRepository:
    def __init__(self, backend: InMemoryBackend, user_id: str) -> None:
        self._b, self._uid = backend, user_id
        self._docs = backend._docs.setdefault(user_id, {})
        self._chunks = backend._chunks.setdefault(user_id, {})

    def _with_count(self, doc: Document) -> Document:
        model = self._b.current_model
        semantic = bool(model) and self._b.indexed_with.get((self._uid, doc.id)) == model
        return dataclasses.replace(doc, chunk_count=len(self._chunks.get(doc.id, [])), semantic=semantic)

    def count_documents(self) -> int:
        return len(self._docs)

    def create_document(self, name, size_bytes, page_count) -> Document:
        doc = Document(str(uuid.uuid4()), name, size_bytes, page_count, "indexing", 0, True)
        self._docs[doc.id] = doc
        self._chunks[doc.id] = []
        return doc

    def put_file(self, document_id, data, content_type) -> None:
        self._b.files[(self._uid, document_id)] = (data, content_type)

    def signed_url(self, document_id, expires_in=60):
        doc_id = valid_id(document_id)
        if (self._uid, doc_id) not in self._b.files:
            return None
        return f"https://files.test/{self._uid}/{doc_id}?token=signed&expires={expires_in}"

    def finish_pending_deletions(self) -> int:
        return 0

    def add_chunks(self, document_id, chunks) -> list[str]:
        self._chunks[document_id].extend(chunks)
        ids = [str(uuid.uuid4()) for _ in chunks]
        self._b.chunk_ids.setdefault((self._uid, document_id), []).extend(ids)
        return ids

    def add_embeddings(self, document_id, chunk_ids, vectors, model_id) -> None:
        assert len(chunk_ids) == len(vectors) and all(len(v) == DIMENSION for v in vectors)
        for chunk_id, vector in zip(chunk_ids, vectors):
            self._b.vectors[(self._uid, chunk_id)] = (document_id, vector, model_id)

    def mark_ready(self, document_id, embedding_model=None) -> None:
        self._docs[document_id] = dataclasses.replace(self._docs[document_id], status="ready")
        if embedding_model:
            self._b.indexed_with[(self._uid, document_id)] = embedding_model

    def match_chunks(self, vector, document_ids, top_k, model_id):
        ready = [d for d in self._docs.values() if d.status == "ready"]
        if document_ids is not None:
            wanted = [valid_id(i) for i in dict.fromkeys(document_ids)]
            ready = [d for d in ready if d.id in wanted]
            if None in wanted or len(ready) != len(wanted):
                return None
        embedded = [d for d in ready if self._b.indexed_with.get((self._uid, d.id)) == model_id]
        scored = []
        for d in embedded:
            for chunk, chunk_id in zip(self._chunks[d.id], self._b.chunk_ids[(self._uid, d.id)]):
                _, vec, model = self._b.vectors[(self._uid, chunk_id)]
                if model == model_id:
                    similarity = sum(a * b for a, b in zip(vector, vec))
                    scored.append((SearchChunk(f"{d.id}-p{chunk.page_number}-c{chunk.chunk_index}", d.id, d.name,
                                               chunk.page_number, chunk.text), similarity))
        scored.sort(key=lambda pair: -pair[1])
        return scored[:top_k], len(ready) - len(embedded), len(ready)

    def list_documents(self):
        return [self._with_count(d) for d in self._docs.values()]

    def get_document(self, document_id):
        doc_id = valid_id(document_id)
        return self._with_count(self._docs[doc_id]) if doc_id in self._docs else None

    def delete_document(self, document_id) -> bool:
        doc_id = valid_id(document_id)
        if doc_id not in self._docs:
            return False
        del self._docs[doc_id]
        self._chunks.pop(doc_id, None)
        self._b.files.pop((self._uid, doc_id), None)
        for chunk_id in self._b.chunk_ids.pop((self._uid, doc_id), []):
            self._b.vectors.pop((self._uid, chunk_id), None)       # vectors go with the document
        self._b.indexed_with.pop((self._uid, doc_id), None)
        return True

    def search_chunks(self, document_ids):
        ready = [d for d in self._docs.values() if d.status == "ready"]
        if document_ids is not None:
            wanted = [valid_id(i) for i in dict.fromkeys(document_ids)]
            ready = [d for d in ready if d.id in wanted]
            if None in wanted or len(ready) != len(wanted):
                return None
        return [
            SearchChunk(f"{d.id}-p{c.page_number}-c{c.chunk_index}", d.id, d.name, c.page_number, c.text)
            for d in ready for c in self._chunks[d.id]
        ]


@pytest.fixture(autouse=True)
def fresh_limits():
    """Limits are process-wide state; every test starts with an empty ledger."""
    from app.limits import limiter
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture(autouse=True)
def fake_backend(request, monkeypatch):
    if request.node.get_closest_marker("integration"):
        yield None
        return
    backend = InMemoryBackend()
    monkeypatch.setattr(auth, "get_verifier", lambda: FakeVerifier())

    def fake_repository(user: AuthUser = Depends(current_user)):
        return backend.repo_for(user)

    monkeypatch.setattr(main, "get_embedder", lambda: backend.embedder if backend.current_model else None)
    main.app.dependency_overrides[get_repository] = fake_repository
    yield backend
    main.app.dependency_overrides.pop(get_repository, None)


def make_pdf(pages: list[str], **save_kwargs) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_text((72, 72), text)
    data = doc.tobytes(**save_kwargs)
    doc.close()
    return data
