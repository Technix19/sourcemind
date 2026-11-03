"""Meaning search through the API, using the fake embedder (plumbing, not model quality)."""
import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import AuthUser, current_user
from app.main import app
from app.repository import RepositoryError, get_repository
from conftest import AUTH_A, AUTH_B, FAKE_MODEL, USER_A, InMemoryRepository

alice = TestClient(app, headers=AUTH_A)
bob = TestClient(app, headers=AUTH_B)

PAGE1 = "The system records correctness, execution time and the number of attempts for every question."
PAGE2 = "A Random Forest classifier is trained on these performance data and selects the next practice level."
PAGE3 = "Limitations: the study used a small sample of forty students."
TEXT = f"{PAGE1}\n\n{PAGE2}\n\n{PAGE3}".encode()


@pytest.fixture(autouse=True)
def permissive_threshold(monkeypatch):
    monkeypatch.setenv("MIN_EMBEDDING_SCORE", "0.05")   # plumbing tests; the default gate has its own test


def upload(client=alice, name="notes.txt", data=TEXT):
    res = client.post("/api/v1/documents", files={"file": (name, data)})
    assert res.status_code == 201, res.text
    return res.json()


def ask(client=alice, **body):
    return client.post("/api/v1/queries", json={"question": "Which inputs does the model use?", **body})


# ------------------------------------------------------------------ indexing

def test_uploading_indexes_every_chunk_for_meaning_search(fake_backend):
    doc = upload()
    assert doc["semantic"] is True
    stored = [v for (uid, _), v in fake_backend.vectors.items() if uid == USER_A.id]
    assert len(stored) == doc["chunk_count"] and all(model == FAKE_MODEL for _, _, model in stored)
    assert fake_backend.embedder.passage_calls and len(fake_backend.embedder.passage_calls[0]) == doc["chunk_count"]
    assert alice.get("/api/v1/documents").json()["documents"][0]["semantic"] is True


def test_the_document_is_marked_with_the_model_that_indexed_it(fake_backend):
    doc = upload()
    assert fake_backend.indexed_with[(USER_A.id, doc["id"])] == FAKE_MODEL


def test_if_the_model_fails_the_document_is_still_indexed_for_keyword_search(fake_backend):
    fake_backend.embedder.fail = True
    doc = upload()
    assert doc["semantic"] is False and doc["status"] == "ready"
    assert fake_backend.vectors == {}
    fake_backend.embedder.fail = False
    assert ask(retrieval="tfidf", question="What limitations does the study have?").json()["evidence"]


def test_with_meaning_search_switched_off_documents_are_keyword_only(fake_backend):
    fake_backend.current_model = None
    doc = upload()
    assert doc["semantic"] is False and fake_backend.embedder.passage_calls == []
    res = ask(retrieval="embedding")
    assert res.status_code == 503 and "turned off" in res.json()["detail"]


def test_a_storage_failure_while_saving_vectors_rolls_the_whole_upload_back(fake_backend):
    class Flaky(InMemoryRepository):
        def add_embeddings(self, *args, **kwargs):
            raise RepositoryError(500)

    app.dependency_overrides[get_repository] = lambda user=Depends(current_user): Flaky(fake_backend, user.id)
    assert alice.post("/api/v1/documents", files={"file": ("n.txt", TEXT)}).status_code == 502
    assert fake_backend.vectors == {} and all(not d for d in fake_backend._docs.values())


def test_deleting_a_document_removes_its_vectors(fake_backend):
    doc = upload()
    assert fake_backend.vectors
    assert alice.delete(f"/api/v1/documents/{doc['id']}").status_code == 204
    assert fake_backend.vectors == {} and fake_backend.indexed_with == {}


# ------------------------------------------------------------------- searching

def test_keyword_is_the_default_and_the_response_says_which_method_was_used():
    upload()
    assert ask().json()["retrieval"] == "tfidf"
    assert ask(retrieval="embedding").json()["retrieval"] == "embedding"


def test_meaning_search_finds_a_paraphrase_that_keyword_search_misses(fake_backend):
    upload(data=PAGE1.encode())
    keyword = ask(retrieval="tfidf").json()
    meaning = ask(retrieval="embedding").json()
    assert keyword["insufficient_evidence"] is True and keyword["evidence"] == []    # "inputs" shares no word with the page
    assert meaning["insufficient_evidence"] is False and "correctness" in meaning["evidence"][0]["excerpt"]
    assert 0 < meaning["evidence"][0]["score"] <= 1


def test_meaning_results_keep_the_same_evidence_shape_as_keyword_results():
    upload()
    keyword = ask(retrieval="tfidf", question="classifier practice level").json()["evidence"][0]
    meaning = ask(retrieval="embedding", question="classifier practice level").json()["evidence"][0]
    assert set(keyword) == set(meaning)
    assert meaning["chunk_id"].count("-p") == 1 and meaning["page_number"] == 1


def test_the_default_relevance_gate_makes_meaning_search_abstain_on_unrelated_questions(monkeypatch):
    monkeypatch.delenv("MIN_EMBEDDING_SCORE")
    upload()
    res = ask(retrieval="embedding", question="galaxies and nebulae").json()
    assert res["insufficient_evidence"] is True and res["evidence"] == []


def test_the_relevance_gate_is_a_hard_threshold(monkeypatch):
    upload()
    monkeypatch.setenv("MIN_EMBEDDING_SCORE", "0.999")
    assert ask(retrieval="embedding", question="classifier practice level").json()["evidence"] == []


def test_documents_without_vectors_are_reported_not_silently_skipped(fake_backend):
    upload(name="indexed.txt", data=PAGE1.encode())
    fake_backend.embedder.fail = True
    upload(name="keyword-only.txt", data=PAGE2.encode())
    fake_backend.embedder.fail = False
    res = ask(retrieval="embedding").json()
    assert "1 of 2 document(s) are not indexed for meaning search" in res["notice"]
    assert {e["filename"] for e in res["evidence"]} == {"indexed.txt"}          # only the indexed one can match


def test_when_no_document_has_vectors_the_answer_is_empty_with_an_explanation(fake_backend):
    fake_backend.embedder.fail = True
    upload()
    fake_backend.embedder.fail = False
    res = ask(retrieval="embedding").json()
    assert res["evidence"] == [] and res["insufficient_evidence"] is True and "not indexed" in res["notice"]


def test_a_meaning_search_failure_is_a_503_and_keyword_search_still_works(fake_backend):
    upload()
    fake_backend.embedder.fail = True
    res = ask(retrieval="embedding")
    assert res.status_code == 503 and "unavailable" in res.json()["detail"] and "fake embedder" not in res.text
    assert ask(retrieval="tfidf", question="classifier practice level").status_code == 200


def test_no_documents_at_all_is_409_for_both_methods():
    assert ask(retrieval="tfidf").status_code == 409
    assert ask(retrieval="embedding").status_code == 409


def test_unknown_retrieval_methods_are_rejected():
    assert ask(retrieval="magic").status_code == 422


def test_restricting_to_chosen_documents_works_for_meaning_search():
    a = upload(name="a.txt", data=PAGE1.encode())
    b = upload(name="b.txt", data=PAGE1.encode())
    only_b = ask(retrieval="embedding", document_ids=[b["id"]]).json()["evidence"]
    assert only_b and {e["document_id"] for e in only_b} == {b["id"]}
    assert ask(retrieval="embedding", document_ids=[a["id"], "not-a-uuid"]).status_code == 404


def test_generated_answers_work_on_top_of_meaning_search(monkeypatch):
    class Model:
        model = "m"

        def complete(self, system, user):
            return "It uses signals [1]."

    monkeypatch.setattr("app.main.get_llm_client", lambda: Model())
    upload(data=PAGE1.encode())
    res = ask(retrieval="embedding", mode="generated").json()
    assert res["answer_mode"] == "generated" and res["retrieval"] == "embedding" and res["answer"] == "It uses signals [1]."


# -------------------------------------------------------------------- isolation

def test_one_users_vectors_never_answer_another_users_question():
    doc = upload(alice, data=PAGE1.encode())
    assert ask(bob, retrieval="embedding").status_code == 409                     # Bob has nothing
    assert ask(bob, retrieval="embedding", document_ids=[doc["id"]]).status_code == 404
    upload(bob, name="bobs.txt", data=PAGE3.encode())
    res = ask(bob, retrieval="embedding", question="Which inputs does the model use?", ).json()
    assert all(e["filename"] == "bobs.txt" for e in res["evidence"])
