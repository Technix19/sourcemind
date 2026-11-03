"""TF-IDF + cosine-similarity retrieval baseline.

Deliberately small and inspectable. Scores are *relative lexical similarity*,
not probabilities and not confidence that an answer exists: a high score means
"shares rare words with the question", nothing more.

Vectorizer settings (documented because results depend on them):
  - English stop words removed
  - unigrams + bigrams
  - sublinear term frequency (1 + log tf), so repeated words don't dominate
  - IDF is fit on the chunks being searched, so a score for the same chunk can
    change when the searched set changes (e.g. when you filter by document).
"""
from __future__ import annotations

from dataclasses import dataclass

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class SearchChunk:
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: SearchChunk
    score: float


def retrieve(
    question: str, chunks: list[SearchChunk], *, top_k: int = 4, min_score: float = 0.05
) -> list[Hit]:
    """Return up to `top_k` chunks scoring at least `min_score`, best first.

    Ties keep the original chunk order, so results are deterministic.
    An empty list means "no sufficiently similar evidence", never an error.
    """
    if not chunks or not question.strip() or top_k < 1:
        return []
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    try:
        matrix = vectorizer.fit_transform(c.text for c in chunks)
        query = vectorizer.transform([question])
    except ValueError:  # empty vocabulary, e.g. nothing but stop words
        return []
    scores = cosine_similarity(query, matrix).ravel()
    order = sorted(range(len(chunks)), key=lambda i: -scores[i])  # stable sort
    return [
        Hit(chunks[i], round(float(scores[i]), 4))
        for i in order[:top_k]
        if scores[i] >= min_score
    ]
