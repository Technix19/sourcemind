import numpy as np
import pytest

from app.retrieval import SearchChunk, retrieve
from conftest import FakeEmbedder
from evaluation.arms import EmbeddingArm, HybridArm, TfidfArm, embed_corpus
from evaluation.corpus import EvalChunk

TEXTS = [
    "The classifier selects the next practice difficulty for each learner.",
    "Sleep needs change throughout the life cycle of a person.",
    "A vegetarian lunch has vegetables and rice.",
    "Practice difficulty depends on correctness and attempts.",
]
CHUNKS = [EvalChunk("d", i + 1, 0, t) for i, t in enumerate(TEXTS)]


def tfidf():
    return TfidfArm(CHUNKS)


def embedding(embedder=None):
    embedder = embedder or FakeEmbedder()
    return EmbeddingArm(CHUNKS, np.asarray(embedder.embed_passages(TEXTS), dtype=np.float32), embedder)


# --------------------------------------------------------------------- keyword

def test_keyword_arm_ranks_the_relevant_chunk_first_and_drops_zero_scores():
    result = tfidf().search("classifier difficulty")
    assert result.ranked[0].chunk.page == 1 and all(r.score > 0 for r in result.ranked)
    assert 3 not in [r.chunk.page for r in result.ranked]            # no shared words: not returned at all
    assert result.gate == {"tfidf": result.ranked[0].score}


def test_keyword_arm_with_nothing_to_match_returns_nothing_not_an_error():
    for question in ("", "   ", "the and of", "zzzz qqqq"):
        result = tfidf().search(question)
        assert result.ranked == [] and result.gate == {"tfidf": 0.0}


def test_keyword_arm_ranking_equals_the_products_ranking():
    """PARITY: the evaluation must measure what ships. Same chunks, same question, same order and scores."""
    question = "which classifier sets practice difficulty and attempts"
    product = retrieve(question, [SearchChunk(f"c{i}", "d", "d", c.page, c.text) for i, c in enumerate(CHUNKS)], top_k=10, min_score=1e-9)
    harness = tfidf().search(question).ranked
    assert [h.chunk.page_number for h in product] == [r.chunk.page for r in harness]
    assert [h.score for h in product] == pytest.approx([round(r.score, 4) for r in harness], abs=1e-4)


# --------------------------------------------------------------------- meaning

def test_embedding_arm_scores_are_cosine_similarities_best_first():
    result = embedding().search("classifier practice difficulty")
    scores = [r.score for r in result.ranked]
    assert scores == sorted(scores, reverse=True) and all(-1.0 <= s <= 1.0 + 1e-6 for s in scores)
    assert result.ranked[0].chunk.page in (1, 4) and result.gate == {"embedding": scores[0]}


def test_embedding_arm_returns_the_requested_number_of_candidates():
    assert len(embedding().search("anything at all", n=2).ranked) == 2


def test_embedding_cache_avoids_recomputing_and_is_keyed_by_content(tmp_path):
    embedder = FakeEmbedder()
    first = embed_corpus(CHUNKS, embedder, cache_dir=tmp_path)
    again = embed_corpus(CHUNKS, embedder, cache_dir=tmp_path)
    assert len(embedder.passage_calls) == 1 and np.array_equal(first, again)
    changed = [EvalChunk("d", 1, 0, "different text")] + CHUNKS[1:]
    embed_corpus(changed, embedder, cache_dir=tmp_path)
    assert len(embedder.passage_calls) == 2                          # new content, new cache entry
    other_model = FakeEmbedder()
    other_model.model_id = "another-model"
    embed_corpus(CHUNKS, other_model, cache_dir=tmp_path)
    assert len(other_model.passage_calls) == 1                       # a different model never reuses vectors


# ---------------------------------------------------------------------- hybrid

def test_reciprocal_rank_fusion_rewards_agreement_between_methods():
    arm = HybridArm(tfidf(), embedding())
    result = arm.search("classifier practice difficulty")
    assert result.ranked[0].chunk.page in (1, 4)
    assert set(result.gate) == {"tfidf", "embedding"}               # both components stay available for abstention
    assert result.ranked == arm.search("classifier practice difficulty").ranked   # deterministic


def test_fusion_scores_follow_the_formula():
    class Fixed:
        name = "fixed"

        def __init__(self, order):
            self.order = order

        def search(self, question, n=50):
            from evaluation.arms import Ranked, SearchResult
            return SearchResult([Ranked(i, CHUNKS[i], 1.0) for i in self.order], {self.name: 1.0})

    fused = HybridArm(Fixed([0, 1]), Fixed([1, 2]), k=60).search("q").ranked
    by_index = {r.index: r.score for r in fused}
    assert by_index[1] == pytest.approx(1 / 62 + 1 / 61)           # rank 2 in one list, rank 1 in the other
    assert by_index[0] == pytest.approx(1 / 61) and by_index[2] == pytest.approx(1 / 62)
    assert [r.index for r in fused] == [1, 0, 2]
