from app.retrieval import SearchChunk, retrieve


def chunk(cid: str, text: str, doc: str = "d1", page: int = 1) -> SearchChunk:
    return SearchChunk(cid, doc, f"{doc}.pdf", page, text)


CORPUS = [
    chunk("a", "The Random Forest classifier predicts coding question difficulty."),
    chunk("b", "A vegetarian lunch has vegetables and rice."),
    chunk("c", "FastAPI provides web endpoints for Python applications."),
]


def test_relevant_chunk_ranks_first_with_bounded_score():
    hits = retrieve("What classifier predicts difficulty?", CORPUS)
    assert hits[0].chunk.chunk_id == "a"
    assert 0 < hits[0].score <= 1


def test_results_sorted_best_first_and_respect_top_k():
    hits = retrieve("python web classifier", CORPUS, top_k=2, min_score=0.0)
    assert len(hits) == 2
    assert hits[0].score >= hits[1].score


def test_unrelated_question_returns_nothing():
    assert retrieve("galaxies and nebulae", CORPUS) == []


def test_degenerate_inputs_return_empty_not_error():
    assert retrieve("anything", []) == []
    assert retrieve("   ", CORPUS) == []
    assert retrieve("the and of", CORPUS) == []  # only stop words
    assert retrieve("python", CORPUS, top_k=0) == []
    assert retrieve("the", [chunk("x", "the and of")]) == []  # empty vocabulary


def test_min_score_is_a_hard_gate():
    assert retrieve("python", CORPUS, min_score=1.01) == []


def test_ties_keep_original_order():
    twins = [chunk("first", "identical text about widgets"), chunk("second", "identical text about widgets")]
    assert [h.chunk.chunk_id for h in retrieve("widgets", twins)] == ["first", "second"]


def test_deterministic():
    assert retrieve("python web", CORPUS, min_score=0.0) == retrieve("python web", CORPUS, min_score=0.0)
