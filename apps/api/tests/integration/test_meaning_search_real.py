"""Meaning search against the REAL project and the REAL local model (needs migration 20261103000003).

Vectors are private data too, so these check that a user can only ever search, see and write
their own, and that the database function really runs as the caller.
"""
import pytest
from fastapi.testclient import TestClient

from app import main
from app.embeddings import DIMENSION, FastEmbedEmbedder, vector_literal
from supabase_helpers import rest, skip_without_supabase, user_a, user_b  # noqa: F401

pytestmark = [pytest.mark.integration, skip_without_supabase]

client = TestClient(main.app)
SETUP_HINT = "Meaning search is not set up: apply supabase/migrations/20261103000003_embeddings.sql (see docs/m6d-apply.md)."
PAGE = "The system records correctness, execution time and the number of attempts for every coding question."


def bearer(user):
    return {"Authorization": f"Bearer {user.token}"}


def upload(user, name="notes.txt", data=PAGE.encode()):
    res = client.post("/api/v1/documents", files={"file": (name, data)}, headers=bearer(user))
    assert res.status_code == 201, f"{SETUP_HINT} Upload said {res.status_code}: {res.text}"
    return res.json()


def match(user, vector, doc_ids=None, model=None, count=5):
    body = {"p_query_embedding": vector_literal(vector), "p_match_count": count}
    if doc_ids is not None:
        body["p_document_ids"] = doc_ids
    if model is not None:
        body["p_model_id"] = model
    return rest("POST", "rpc/match_chunks", user, json=body)


@pytest.fixture(scope="module")
def embedder():
    return FastEmbedEmbedder("BAAI/bge-small-en-v1.5", __import__("app.config", fromlist=["x"]).get_settings().embedding_cache_dir)


@pytest.fixture(autouse=True)
def clean_up(user_a, user_b):
    yield
    for user in (user_a, user_b):
        client.get("/api/v1/documents", headers=bearer(user))
        for doc in client.get("/api/v1/documents", headers=bearer(user)).json().get("documents", []):
            client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user))
        rest("DELETE", f"documents?user_id=eq.{user.id}", user)


# -------------------------------------------------------------- the real model

def test_the_real_model_ranks_a_paraphrase_above_an_unrelated_sentence(embedder):
    query = embedder.embed_query("What inputs does the model use?")
    near, far = embedder.embed_passages([PAGE, "The medieval cathedral was built over two centuries of stonework."])
    similarity = lambda a, b: sum(x * y for x, y in zip(a, b))  # vectors are normalised
    assert len(query) == DIMENSION
    assert similarity(query, near) > similarity(query, far) + 0.1


# ------------------------------------------------------------ indexing + searching

def test_upload_stores_vectors_and_marks_the_document_semantic(user_a):
    doc = upload(user_a)
    assert doc["semantic"] is True
    row = rest("GET", f"documents?id=eq.{doc['id']}", user_a).json()[0]
    assert row["embedding_model"] == "BAAI/bge-small-en-v1.5"
    chunks = rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json()
    stored = rest("GET", f"embeddings?chunk_id=in.({','.join(c['id'] for c in chunks)})", user_a).json()
    assert len(stored) == len(chunks) == doc["chunk_count"] and all(e["user_id"] == user_a.id for e in stored)


def test_meaning_search_finds_the_page_through_the_whole_stack(user_a):
    upload(user_a)
    res = client.post("/api/v1/queries", json={"question": "Which inputs does the model use?", "retrieval": "embedding"}, headers=bearer(user_a))
    body = res.json()
    assert res.status_code == 200 and body["retrieval"] == "embedding"
    assert body["evidence"] and "correctness" in body["evidence"][0]["excerpt"] and 0 < body["evidence"][0]["score"] <= 1


def test_the_default_gate_lets_an_unrelated_question_abstain_on_this_example(user_a):
    upload(user_a)
    res = client.post("/api/v1/queries", json={"question": "galaxies and nebulae", "retrieval": "embedding"}, headers=bearer(user_a)).json()
    assert res["evidence"] == [] and res["insufficient_evidence"] is True      # an anecdote, not a calibration (see M7)


# --------------------------------------------------------------------- isolation

def test_the_search_function_runs_as_the_caller_so_other_users_get_nothing(user_a, user_b, embedder):
    doc = upload(user_a)
    vector = embedder.embed_query("What inputs does the model use?")
    mine = match(user_a, vector, [doc["id"]])
    assert mine.status_code == 200 and len(mine.json()) >= 1                      # positive control
    assert match(user_b, vector, [doc["id"]]).json() == []                        # B names A's document
    assert match(user_b, vector).json() == []                                     # B names nothing
    assert match(user_b, vector, [doc["id"]], model="BAAI/bge-small-en-v1.5").json() == []


def test_anonymous_callers_cannot_run_the_search_function(user_a, embedder):
    upload(user_a)
    res = rest("POST", "rpc/match_chunks", json={"p_query_embedding": vector_literal(embedder.embed_query("x")), "p_match_count": 3})
    assert res.status_code in (401, 403) and "42501" in res.text


def test_the_composite_key_stops_attaching_a_vector_to_someone_elses_chunk(user_a, user_b, embedder):
    """Uses a chunk that has NO vector yet. (If it already had one, the primary key on chunk_id would
    refuse the insert first, with 23505, and the composite key would never be exercised.)"""
    doc = rest("POST", "documents", user_a, json={"name": "bare.txt", "size_bytes": 5, "page_count": 1}).json()[0]
    chunk = rest("POST", "chunks", user_a, json={"document_id": doc["id"], "page_number": 1, "chunk_index": 0,
                                                 "start_offset": 0, "end_offset": 5, "text": "hello"}).json()[0]
    vec = vector_literal(embedder.embed_query("x"))
    as_b = rest("POST", "embeddings", user_b, json={"chunk_id": chunk["id"], "model_id": "m", "embedding": vec})
    assert as_b.status_code == 409 and "23503" in as_b.text, as_b.text          # (A's chunk, B) is not a real pair
    forged = rest("POST", "embeddings", user_b, json={"chunk_id": chunk["id"], "user_id": user_a.id, "model_id": "m", "embedding": vec})
    assert forged.status_code in (401, 403) and "42501" in forged.text          # RLS: cannot claim to be A
    # Control: the owner can attach one, so the denials above are not just a broken setup.
    assert rest("POST", "embeddings", user_a, json={"chunk_id": chunk["id"], "model_id": "m", "embedding": vec}).status_code == 201
    assert rest("GET", f"embeddings?chunk_id=eq.{chunk['id']}", user_b).json() == []


def test_a_chunk_that_already_has_a_vector_cannot_be_given_another_by_anyone(user_a, user_b, embedder):
    doc = upload(user_a)                                                          # upload stores a vector per chunk
    chunk_id = rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json()[0]["id"]
    vec = vector_literal(embedder.embed_query("x"))
    for user in (user_a, user_b):
        again = rest("POST", "embeddings", user, json={"chunk_id": chunk_id, "model_id": "m", "embedding": vec})
        assert again.status_code == 409 and "23505" in again.text                 # primary key: one vector per chunk
    assert len(rest("GET", f"embeddings?chunk_id=eq.{chunk_id}", user_a).json()) == 1


def test_vectors_are_private_and_immutable(user_a, user_b):
    doc = upload(user_a)
    chunk_id = rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json()[0]["id"]
    assert len(rest("GET", f"embeddings?chunk_id=eq.{chunk_id}", user_a).json()) == 1       # control
    assert rest("GET", f"embeddings?chunk_id=eq.{chunk_id}", user_b).json() == []
    assert rest("DELETE", f"embeddings?chunk_id=eq.{chunk_id}", user_b).json() == []
    edit = rest("PATCH", f"embeddings?chunk_id=eq.{chunk_id}", user_a, json={"model_id": "other"})
    assert edit.status_code in (401, 403) and "42501" in edit.text                # nobody may edit a vector
    assert rest("GET", "embeddings", None).status_code in (401, 403)              # anonymous


# ----------------------------------------------------------- correctness guards

def test_only_ready_documents_and_matching_models_are_searched(user_a, embedder):
    doc = rest("POST", "documents", user_a, json={"name": "manual.txt", "size_bytes": 5, "page_count": 1, "status": "indexing"}).json()[0]
    chunk = rest("POST", "chunks", user_a, json={"document_id": doc["id"], "page_number": 1, "chunk_index": 0,
                                                 "start_offset": 0, "end_offset": 5, "text": PAGE}).json()[0]
    vector = embedder.embed_query("inputs")
    rest("POST", "embeddings", user_a, json={"chunk_id": chunk["id"], "model_id": "model-one", "embedding": vector_literal(vector)})
    assert match(user_a, vector, [doc["id"]]).json() == []                                   # still 'indexing'
    rest("PATCH", f"documents?id=eq.{doc['id']}", user_a, json={"status": "ready"})
    assert len(match(user_a, vector, [doc["id"]], model="model-one").json()) == 1            # ready: found
    assert match(user_a, vector, [doc["id"]], model="a-different-model").json() == []       # vectors of other models never mix


def test_a_vector_of_the_wrong_size_is_refused_by_the_database(user_a):
    doc = rest("POST", "documents", user_a, json={"name": "x.txt", "size_bytes": 5, "page_count": 1}).json()[0]
    chunk = rest("POST", "chunks", user_a, json={"document_id": doc["id"], "page_number": 1, "chunk_index": 0,
                                                 "start_offset": 0, "end_offset": 5, "text": "hello"}).json()[0]
    res = rest("POST", "embeddings", user_a, json={"chunk_id": chunk["id"], "model_id": "m", "embedding": vector_literal([0.1] * 10)})
    assert res.status_code >= 400


def test_documents_stored_before_meaning_search_are_reported_not_silently_skipped(user_a):
    made = rest("POST", "documents", user_a, json={"name": "old.txt", "size_bytes": 5, "page_count": 1}).json()[0]
    listed = client.get("/api/v1/documents", headers=bearer(user_a)).json()["documents"]
    assert [d for d in listed if d["id"] == made["id"]][0]["semantic"] is False
    rest("POST", "chunks", user_a, json={"document_id": made["id"], "page_number": 1, "chunk_index": 0,
                                         "start_offset": 0, "end_offset": 5, "text": "hello"})
    res = client.post("/api/v1/queries", json={"question": "hello there friend", "retrieval": "embedding"}, headers=bearer(user_a)).json()
    assert "not indexed for meaning search" in (res["notice"] or "") and res["evidence"] == []


def test_deleting_a_document_deletes_its_vectors(user_a):
    doc = upload(user_a)
    chunk_ids = [c["id"] for c in rest("GET", f"chunks?document_id=eq.{doc['id']}", user_a).json()]
    assert client.delete(f"/api/v1/documents/{doc['id']}", headers=bearer(user_a)).status_code == 204
    assert rest("GET", f"embeddings?chunk_id=in.({','.join(chunk_ids)})", user_a).json() == []
