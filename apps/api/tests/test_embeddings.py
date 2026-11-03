"""The embedder wrapper, without downloading any model."""
import sys
import types

import pytest

from app import embeddings
from app.embeddings import DIMENSION, EmbeddingError, FastEmbedEmbedder, get_embedder, vector_literal, warm_up


class FakeTextEmbedding:
    """Stands in for fastembed.TextEmbedding."""

    instances = 0
    dimension = DIMENSION
    boom = False

    def __init__(self, model_name, cache_dir=None):
        type(self).instances += 1
        self.model_name, self.cache_dir = model_name, cache_dir

    def embed(self, texts, batch_size=32):
        if type(self).boom:
            raise RuntimeError("inference exploded with /secret/path")
        for i, _ in enumerate(texts):
            yield [0.1234567891 * (i + 1)] * type(self).dimension

    def query_embed(self, texts):
        yield [0.5] * type(self).dimension


@pytest.fixture(autouse=True)
def fake_fastembed(monkeypatch):
    FakeTextEmbedding.instances, FakeTextEmbedding.dimension, FakeTextEmbedding.boom = 0, DIMENSION, False
    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=FakeTextEmbedding))
    monkeypatch.setattr(embeddings, "_embedder", None)


def embedder():
    return FastEmbedEmbedder("test-model", "/tmp/cache-dir")


def test_the_model_loads_once_lazily_and_from_the_configured_cache_dir():
    e = embedder()
    assert FakeTextEmbedding.instances == 0                      # nothing loaded at construction
    e.embed_passages(["a"]); e.embed_query("q"); e.embed_passages(["b", "c"])
    assert FakeTextEmbedding.instances == 1
    assert e._model.cache_dir == "/tmp/cache-dir" and e._model.model_name == "test-model"


def test_passages_become_rounded_vectors_of_the_database_size():
    vectors = embedder().embed_passages(["one", "two"])
    assert len(vectors) == 2 and all(len(v) == DIMENSION for v in vectors)
    assert vectors[0][0] == 0.123457                              # rounded to 6 decimals to keep requests small


def test_a_model_with_the_wrong_vector_size_is_refused_before_it_reaches_the_database():
    FakeTextEmbedding.dimension = 768
    with pytest.raises(EmbeddingError, match="768 dimensions"):
        embedder().embed_passages(["x"])
    with pytest.raises(EmbeddingError):
        embedder().embed_query("x")


def test_inference_errors_are_wrapped_and_never_leak_internals():
    FakeTextEmbedding.boom = True
    with pytest.raises(EmbeddingError) as caught:
        embedder().embed_passages(["x"])
    assert "secret" not in str(caught.value) and "RuntimeError" in str(caught.value)


def test_a_model_that_cannot_be_loaded_is_an_embedding_error(monkeypatch):
    class Broken:
        def __init__(self, *a, **k):
            raise OSError("no network and no cache at /home/someone")

    monkeypatch.setitem(sys.modules, "fastembed", types.SimpleNamespace(TextEmbedding=Broken))
    with pytest.raises(EmbeddingError) as caught:
        embedder().embed_query("x")
    assert "/home/someone" not in str(caught.value)


def test_query_vectors_use_the_query_side_of_the_model():
    assert embedder().embed_query("q")[0] == 0.5                  # query_embed, not embed


def test_vector_literal_matches_pgvectors_text_form():
    assert vector_literal([0.5, -1.0, 0.000001]) == "[0.5,-1.0,1e-06]"


def test_embeddings_can_be_switched_off(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "false")
    assert get_embedder() is None
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "true")
    assert get_embedder() is not None


def test_the_process_shares_one_embedder(monkeypatch):
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "true")
    assert get_embedder() is get_embedder()


def test_warm_up_never_raises_even_when_loading_fails(monkeypatch):
    class Broken:
        model_id = "x"

        def embed_query(self, text):
            raise EmbeddingError("no model")

    monkeypatch.setattr(embeddings, "get_embedder", lambda: Broken())
    import time
    warm_up()
    time.sleep(0.2)   # the background thread must swallow the failure
    monkeypatch.setattr(embeddings, "get_embedder", lambda: None)
    warm_up()
