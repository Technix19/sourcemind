"""Two ways to find evidence, behind one interface and one result shape.

`tfidf`      keyword matching (transparent baseline, runs anywhere)
`embedding`  meaning search with local vectors (finds paraphrases, never scores zero)

Scores are retriever-specific and NOT comparable between the two.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .embeddings import Embedder
from .repository import Repository
from .retrieval import Hit, retrieve


@dataclass(frozen=True)
class SearchOutcome:
    hits: list[Hit]
    empty: bool = False         # there was nothing to search at all (no ready documents)
    notice: str | None = None   # something the user should know about this search


class Retriever(Protocol):
    name: str

    def search(
        self, question: str, repo: Repository, document_ids: list[str] | None, top_k: int, min_score: float
    ) -> SearchOutcome | None: ...   # None: a requested document is not the caller's


class TfidfRetriever:
    name = "tfidf"

    def search(self, question, repo, document_ids, top_k, min_score):
        chunks = repo.search_chunks(document_ids)
        if chunks is None:
            return None
        if not chunks:
            return SearchOutcome([], empty=True)
        return SearchOutcome(retrieve(question, chunks, top_k=top_k, min_score=min_score))


class EmbeddingRetriever:
    name = "embedding"

    def __init__(self, embedder: Embedder) -> None:
        self._embedder = embedder

    def search(self, question, repo, document_ids, top_k, min_score):
        vector = self._embedder.embed_query(question)          # may raise EmbeddingError
        result = repo.match_chunks(vector, document_ids, top_k, self._embedder.model_id)
        if result is None:
            return None
        matches, not_indexed, total = result
        if total == 0:
            return SearchOutcome([], empty=True)
        notice = None
        if not_indexed:
            notice = (
                f"{not_indexed} of {total} document(s) are not indexed for meaning search "
                "(uploaded before it existed, or indexing was unavailable). Upload them again, or use keyword search."
            )
        hits = [Hit(chunk, round(score, 4)) for chunk, score in matches if score >= min_score]
        return SearchOutcome(hits, notice=notice)
