"""PARITY: the evaluation harness must return what the real product returns.

Part of the corpus is uploaded through the real API (real database, real vectors, real model) and
the same queries are run through both. If they ever disagree, the evaluation no longer measures the product.

The queries below are deliberately NOT from the labeled dataset, so this test cannot leak anything about the held-out questions.
"""
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import get_settings
from app.embeddings import FastEmbedEmbedder
from evaluation.arms import EmbeddingArm, TfidfArm, embed_corpus
from evaluation.corpus import CORPUS_DIR, build_chunks, corpus_available, load_pages
from supabase_helpers import rest, skip_without_supabase, user_a  # noqa: F401

pytestmark = [pytest.mark.integration, skip_without_supabase, pytest.mark.skipif(not corpus_available(), reason="run data/evaluation/fetch_corpus.py")]

client = TestClient(main.app)
DOCS = ["nist-ai-rmf", "nist-csf"]    # uploaded in this order; the harness corpus uses the same order
QUERIES = [
    "risk tolerance and acceptable levels of risk",
    "who is responsible for governing AI systems",
    "describing current and target cybersecurity posture",
    "supply chain risk management",
    "how organizations communicate cybersecurity risk to executives",
    "transparency and accountability of automated systems",
    "recovering from an incident",
    "workforce diversity and training",
]
TOP = 5


def bearer(user):
    return {"Authorization": f"Bearer {user.token}"}


@pytest.fixture(scope="module")
def product_library(user_a):
    for doc in DOCS:
        data = (CORPUS_DIR / f"{doc}.pdf").read_bytes()
        res = client.post("/api/v1/documents", files={"file": (f"{doc}.pdf", data)}, headers=bearer(user_a))
        assert res.status_code == 201, res.text
        assert res.json()["semantic"] is True
    yield
    for d in client.get("/api/v1/documents", headers=bearer(user_a)).json()["documents"]:
        client.delete(f"/api/v1/documents/{d['id']}", headers=bearer(user_a))
    rest("DELETE", f"documents?user_id=eq.{user_a.id}", user_a)


@pytest.fixture(scope="module")
def harness():
    chunks = build_chunks(load_pages(DOCS))
    settings = get_settings()
    embedder = FastEmbedEmbedder(settings.embedding_model, settings.embedding_cache_dir)
    vectors = embed_corpus(chunks, embedder)
    return chunks, TfidfArm(chunks), EmbeddingArm(chunks, vectors, embedder)


def ask(user, question, retrieval):
    body = {"question": question, "retrieval": retrieval, "top_k": TOP}
    res = client.post("/api/v1/queries", json=body, headers=bearer(user))
    assert res.status_code == 200, res.text
    return res.json()["evidence"]


@pytest.fixture(autouse=True)
def no_thresholds(monkeypatch):
    monkeypatch.setenv("MIN_RELEVANCE_SCORE", "0.0000001")   # parity concerns RANKING; the gate is tested elsewhere
    monkeypatch.setenv("MIN_EMBEDDING_SCORE", "-1")


def test_the_corpus_the_product_stored_equals_the_corpus_the_harness_built(user_a, product_library, harness):
    chunks, *_ = harness
    stored = rest("GET", "chunks?select=page_number,text&order=document_id,page_number,chunk_index&limit=5000", user_a).json()
    assert len(stored) == len(chunks)
    assert sorted(c["text"] for c in stored) == sorted(c.text for c in chunks)       # identical chunking, character for character


@pytest.mark.parametrize("question", QUERIES)
def test_keyword_search_returns_the_same_chunks_in_the_same_order(user_a, product_library, harness, question):
    _, tfidf, _ = harness
    product = ask(user_a, question, "tfidf")
    ours = tfidf.search(question).ranked[:TOP]
    assert [(e["filename"], e["page_number"], e["excerpt"]) for e in product] == [(f"{r.chunk.doc_id}.pdf", r.chunk.page, r.chunk.text) for r in ours]
    assert [e["score"] for e in product] == pytest.approx([round(r.score, 4) for r in ours], abs=1e-4)


@pytest.mark.parametrize("question", QUERIES)
def test_meaning_search_returns_the_same_chunks_with_the_same_similarity(user_a, product_library, harness, question):
    _, _, embedding = harness
    product = ask(user_a, question, "embedding")
    ours = embedding.search(question).ranked[:TOP]
    assert [(e["filename"], e["page_number"], e["excerpt"]) for e in product] == [(f"{r.chunk.doc_id}.pdf", r.chunk.page, r.chunk.text) for r in ours]
    # the database stores vectors rounded to 6 decimals and returns 4-decimal scores, so allow a hair of rounding
    assert [e["score"] for e in product] == pytest.approx([round(r.score, 4) for r in ours], abs=5e-4)
