"""Turn text into vectors for meaning search, locally.

The default model runs on this machine (ONNX, no PyTorch, no network after the one-time model
download), so document text never leaves it. Everything model-specific lives here behind a small
interface, so tests use a deterministic fake and a hosted provider would be a one-file change.
"""
from __future__ import annotations

import logging
import threading
from typing import Protocol

from .config import get_settings

logger = logging.getLogger("sourcemind.embeddings")

DIMENSION = 384  # must equal the vector size of public.embeddings in the database
BATCH_SIZE = 32


class Embedder(Protocol):
    model_id: str

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingError(Exception):
    """The embedder could not produce vectors (model missing, wrong size, ...)."""


def _as_floats(vector) -> list[float]:
    values = [round(float(x), 6) for x in vector]   # 6 decimals keeps requests small and is plenty
    if len(values) != DIMENSION:
        raise EmbeddingError(f"model returned {len(values)} dimensions, the database expects {DIMENSION}")
    return values


class FastEmbedEmbedder:
    """BAAI/bge-small-en-v1.5 (or another 384-dimension model) via fastembed."""

    def __init__(self, model_id: str, cache_dir: str) -> None:
        self.model_id = model_id
        self._cache_dir = cache_dir
        self._model = None
        self._lock = threading.Lock()  # load once; inference is serialised for safety

    def _load(self):
        if self._model is None:
            try:
                from fastembed import TextEmbedding

                logger.info("loading embedding model %s", self.model_id)
                self._model = TextEmbedding(self.model_id, cache_dir=self._cache_dir)
            except Exception as exc:
                raise EmbeddingError(f"could not load the embedding model ({type(exc).__name__})") from None
        return self._model

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        with self._lock:
            model = self._load()
            try:
                return [_as_floats(v) for v in model.embed(texts, batch_size=BATCH_SIZE)]
            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError(f"embedding failed ({type(exc).__name__})") from None

    def embed_query(self, text: str) -> list[float]:
        with self._lock:
            model = self._load()
            try:
                # Retrieval models are trained with a query-side instruction; fastembed adds it.
                return _as_floats(next(iter(model.query_embed([text]))))
            except EmbeddingError:
                raise
            except Exception as exc:
                raise EmbeddingError(f"embedding failed ({type(exc).__name__})") from None


_embedder: Embedder | None = None
_embedder_lock = threading.Lock()


def get_embedder() -> Embedder | None:
    """The process-wide embedder, or None when meaning search is switched off. Tests replace this."""
    global _embedder
    settings = get_settings()
    if not settings.embeddings_enabled:
        return None
    with _embedder_lock:
        if _embedder is None:
            _embedder = FastEmbedEmbedder(settings.embedding_model, settings.embedding_cache_dir)
        return _embedder


def warm_up() -> None:
    """Load the model in the background at startup so the first upload is not slowed by it."""
    embedder = get_embedder()
    if embedder is None:
        return

    def load() -> None:
        try:
            embedder.embed_query("warm up")
        except Exception as exc:   # never fatal: keyword search still works
            logger.warning("embedding model warm-up failed: %s", type(exc).__name__)

    threading.Thread(target=load, name="embedder-warmup", daemon=True).start()


def vector_literal(values: list[float]) -> str:
    """pgvector's text form, e.g. '[0.1,0.2]', which PostgREST accepts for vector columns."""
    return "[" + ",".join(repr(v) for v in values) + "]"
