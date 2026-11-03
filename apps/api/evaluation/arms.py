"""The retrieval methods being compared, run over the evaluation corpus in memory.

`tfidf` and `embedding` use the SAME code as the product (app.retrieval.TfidfIndex, the same embedder
and the same cosine math as the database function). `hybrid` (reciprocal-rank fusion) exists only
here, as an experiment; it ships only if the numbers justify it.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import numpy as np

from app.retrieval import TfidfIndex

from .corpus import DATA_DIR, EvalChunk

POOL = 50  # candidates considered per method before cutting to top-k


@dataclass(frozen=True)
class Ranked:
    index: int          # position in the corpus chunk list
    chunk: EvalChunk
    score: float        # method-specific; NOT comparable between methods


@dataclass
class SearchResult:
    ranked: list[Ranked]                                   # best first
    gate: dict[str, float] = field(default_factory=dict)   # best raw score per component (for abstention thresholds)
    latency_ms: float = 0.0


class Arm(Protocol):
    name: str

    def search(self, question: str, n: int = POOL) -> SearchResult: ...


class TfidfArm:
    name = "tfidf"

    def __init__(self, chunks: list[EvalChunk]) -> None:
        self._chunks = chunks
        self._index = TfidfIndex(c.text for c in chunks)

    def search(self, question: str, n: int = POOL) -> SearchResult:
        started = time.perf_counter()
        scores = self._index.scores(question) if question.strip() else None
        ranked: list[Ranked] = []
        if scores is not None:
            order = np.argsort(-scores, kind="stable")        # ties keep corpus order, like the product
            ranked = [Ranked(int(i), self._chunks[int(i)], float(scores[i])) for i in order[:n] if scores[i] > 0]
        top = ranked[0].score if ranked else 0.0
        return SearchResult(ranked, {"tfidf": top}, (time.perf_counter() - started) * 1000)


class EmbeddingArm:
    name = "embedding"

    def __init__(self, chunks: list[EvalChunk], vectors: np.ndarray, embedder) -> None:
        self._chunks, self._vectors, self._embedder = chunks, vectors, embedder

    def search(self, question: str, n: int = POOL) -> SearchResult:
        started = time.perf_counter()
        query = np.asarray(self._embedder.embed_query(question), dtype=np.float32)
        sims = self._vectors @ query                           # vectors are unit length, so this is cosine similarity
        order = np.argsort(-sims, kind="stable")
        ranked = [Ranked(int(i), self._chunks[int(i)], float(sims[i])) for i in order[:n]]
        return SearchResult(ranked, {"embedding": ranked[0].score if ranked else 0.0}, (time.perf_counter() - started) * 1000)


class HybridArm:
    """Reciprocal-rank fusion of the two methods (k = 60, the usual default). Experimental, harness-only."""

    name = "hybrid"

    def __init__(self, tfidf: TfidfArm, embedding: EmbeddingArm, k: int = 60) -> None:
        self._tfidf, self._embedding, self._k = tfidf, embedding, k

    def search(self, question: str, n: int = POOL) -> SearchResult:
        started = time.perf_counter()
        a, b = self._tfidf.search(question), self._embedding.search(question)
        fused: dict[int, float] = {}
        chunks: dict[int, EvalChunk] = {}
        for result in (a, b):
            for rank, item in enumerate(result.ranked, start=1):
                fused[item.index] = fused.get(item.index, 0.0) + 1.0 / (self._k + rank)
                chunks[item.index] = item.chunk
        order = sorted(fused, key=lambda i: (-fused[i], i))
        ranked = [Ranked(i, chunks[i], fused[i]) for i in order[:n]]
        return SearchResult(ranked, {**a.gate, **b.gate}, (time.perf_counter() - started) * 1000 + 0.0)


def embed_corpus(chunks: list[EvalChunk], embedder, *, cache_dir: Path | None = None) -> np.ndarray:
    """One unit-length vector per chunk, cached on disk (the model is deterministic, embedding is slow)."""
    cache_dir = cache_dir if cache_dir is not None else DATA_DIR / ".cache"
    key = hashlib.sha256(json.dumps([embedder.model_id, [c.text for c in chunks]]).encode()).hexdigest()[:24]
    cached = cache_dir / f"embeddings-{key}.npy"
    if cached.exists():
        return np.load(cached)
    texts = [c.text for c in chunks]
    vectors = np.asarray(embedder.embed_passages(texts), dtype=np.float32)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(cached, vectors)
    return vectors
